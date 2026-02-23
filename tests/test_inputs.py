"""Tests for inputs definitions."""

import os
import re
from typing import TYPE_CHECKING, get_args

import pydantic
import pytest

from pytest_loco.schema.inputs import EnvironmentDefinition, InputDefinition, ParametersDefinition

if TYPE_CHECKING:
    from re import Pattern

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize('name, except_message', (
    pytest.param('testVar0', None, id='lower camel case'),
    pytest.param('TestVar', None, id='upper camel case'),
    pytest.param('test_var_0', None, id='lower snake case'),
    pytest.param('TEST_VAR', None, id='upper snake case'),
    pytest.param('test-var', r'^1 validation error', id='kebab case'),
    pytest.param('test.var', r'^1 validation error', id='dot notation'),
    pytest.param('_v', r'^1 validation error', id='starts with underscore'),
    pytest.param('0v', r'^1 validation error', id='starts with digit'),
    pytest.param('', r'^1 validation error', id='empty string'),
))
def test_input_definition_name(name: str, except_message: 'Pattern | None') -> None:
    """Validate allowed and forbidden input definition names."""
    values = {
        'name': name,
        'description': 'A test variable',
    }

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            InputDefinition.model_validate(values)
        return

    definition = InputDefinition.model_validate(values)

    assert definition.name == name


@pytest.mark.parametrize('value_type, except_message', (
    pytest.param('str', None, id='string type'),
    pytest.param('int', None, id='integer type'),
    pytest.param('float', None, id='float type'),
    pytest.param('bool', None, id='bool type'),
    pytest.param('number', r'^1 validation error', id='unsupported type'),
    pytest.param('', r'^1 validation error', id='empty'),
))
def test_input_definition_type(value_type: str, except_message: 'Pattern | None') -> None:
    """Validate supported input definition types."""
    values = {
        'name': 'TEST_VAR',
        'description': 'A test variable',
        'type': value_type,
    }

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            InputDefinition.model_validate(values)
        return

    definition = InputDefinition.model_validate(values)

    assert definition.value_type == value_type


@pytest.mark.parametrize('default_value, required, except_message', (
    pytest.param('default', None, None, id='default value provided, required unspecified'),
    pytest.param('default', False, None, id='default value provided, not required'),
    pytest.param('default', True, r'^1 validation error', id='default value provided, required true'),
    pytest.param(None, True, None, id='no default value, required'),
    pytest.param(None, False, None, id='no default value, not required'),
))
def test_input_definition_default_required(default_value: str | None, required: bool | None,
                                           except_message: 'Pattern | None') -> None:
    """Validate interaction between default and required flags."""
    values = {'name': 'TEST_VAR', 'description': 'A test variable', 'type': 'str'}
    if default_value is not None:
        values['default'] = default_value
    if required is not None:
        values['required'] = required  # type: ignore

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            InputDefinition.model_validate(values)
        return

    definition = InputDefinition.model_validate(values)

    assert definition.default == default_value
    assert definition.required == (required if required is not None else False)


@pytest.mark.parametrize('value', (
    pytest.param(None, id='value unspecified'),
    pytest.param('non-default value', id='valid value'),
))
def test_environment_definition_default(value: str | None, mocker: 'MockerFixture') -> None:
    """Verify environment variables with default values."""
    environment = {}
    if value is not None:
        environment['TEST_VAR'] = value

    mocker.patch.dict(os.environ, environment)

    definition = EnvironmentDefinition.model_validate([{
        'name': 'TEST_VAR',
        'default': 'default value',
    }])

    settings = definition.build()
    settings_instance = settings()

    assert (value if value is not None else 'default value') == settings_instance.TEST_VAR


@pytest.mark.parametrize('value_type, model_type, secret', (
    pytest.param('str', str, False, id='string type'),
    pytest.param('str', pydantic.SecretStr, True, id='secret string type'),
    pytest.param('int', int, False, id='integer type'),
    pytest.param('float', float, False, id='float type'),
    pytest.param('bool', bool, False, id='bool type'),
))
def test_environment_definition_types(value_type: str, model_type: type,
                                      secret: bool, mocker: 'MockerFixture') -> None:
    """Verify environment variable handling with any types."""
    mocker.patch.dict(os.environ, {'TEST_VAR': 'secret value'})

    definition = EnvironmentDefinition.model_validate([{
        'name': 'TEST_VAR',
        'type': value_type,
        'secret': secret and value_type == 'str',
    }])

    fields = definition.build_fields()
    type_args = get_args(fields['TEST_VAR'])

    assert type_args[0] == model_type | None


@pytest.mark.parametrize('value, except_message', (
    pytest.param('non-default value', None, id='non-default value'),
    pytest.param(None, r'^1 validation error', id='empty value'),
))
def test_environment_definition_required(value: str | None, except_message: 'Pattern | None',
                                         mocker: 'MockerFixture') -> None:
    """Verify required environment variables."""
    environment = {}
    if value is not None:
        environment['TEST_VAR'] = value

    mocker.patch.dict(os.environ, environment)

    definition = EnvironmentDefinition.model_validate([{
        'name': 'TEST_VAR',
        'required': True,
    }])

    settings = definition.build()

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            settings()
        return

    settings_instance = settings()

    assert value == settings_instance.TEST_VAR


def test_environment_definition_secret(mocker: 'MockerFixture') -> None:
    """Verify secret environment variable handling."""
    mocker.patch.dict(os.environ, {'TEST_VAR': 'secret value'})

    definition = EnvironmentDefinition.model_validate([{
        'name': 'TEST_VAR',
        'secret': True,
        'required': True,
    }])

    settings = definition.build()
    settings_instance = settings()

    assert 'secret value' not in repr(settings_instance)
    assert re.match(r'^SecretStr\(\'\*+\'\)$', repr(settings_instance.TEST_VAR))
    assert re.match(r'^\*+$', str(settings_instance.TEST_VAR))
    assert settings_instance.TEST_VAR.get_secret_value() == 'secret value'


@pytest.mark.parametrize('value_type, except_message', (
    pytest.param('str', None, id='string type'),
    pytest.param('int', r'1 validation error', id='integer type'),
    pytest.param('float', r'1 validation error', id='float type'),
    pytest.param('bool', r'1 validation error', id='bool type'),
))
def test_environment_definition_secret_type(value_type: str, except_message: 'Pattern | None',
                                            mocker: 'MockerFixture') -> None:
    """Verify secret environment variable handling with any types."""
    mocker.patch.dict(os.environ, {'TEST_VAR': 'secret value'})

    values = [{
        'name': 'TEST_VAR',
        'type': value_type,
        'secret': True,
    }]

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            EnvironmentDefinition.model_validate(values)
        return

    EnvironmentDefinition.model_validate(values)


@pytest.mark.parametrize('value', (
    pytest.param(None, id='value unspecified'),
    pytest.param('non-default value', id='valid value'),
))
def test_parameters_definition_default(value: str | None) -> None:
    """Verify parameter definitions with default values."""
    data = {}
    if value is not None:
        data['value'] = value

    definition = ParametersDefinition.model_validate([{
        'name': 'value',
        'default': 'default value',
    }])

    model = definition.build()
    model_instance = model(**data)

    assert (value if value is not None else 'default value') == model_instance.value  # type: ignore


@pytest.mark.parametrize('value, except_message', (
    pytest.param('non-default value', None, id='non-default value'),
    pytest.param(None, r'^1 validation error', id='empty value'),
))
def test_parameters_definition_required(value: str | None, except_message: 'Pattern | None') -> None:
    """Verify required parameter definitions."""
    data = {}
    if value is not None:
        data['value'] = value

    definition = ParametersDefinition.model_validate([{
        'name': 'value',
        'required': True,
    }])

    model = definition.build()

    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            model(**data)
        return

    model_instance = model(**data)

    assert value == model_instance.value  # type: ignore
