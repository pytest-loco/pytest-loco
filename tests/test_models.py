"""Tests for core document and model schemas."""

from typing import TYPE_CHECKING

import pydantic
import pytest

from pytest_loco.jsonschema import SchemaGenerator
from pytest_loco.models import SchemaModel
from pytest_loco.schema import BaseAction, Case, Template
from pytest_loco.values import Deferred

if TYPE_CHECKING:
    from re import Pattern


@pytest.mark.parametrize('content, except_message', (
    pytest.param(
        {
            'spec': 'template',
            'title': 'A test template',
            'description': 'Template description',
            'vars': {
                'baseUrl': 'https://api.example.com',
                'timeout': 300,
                'headers': {
                    'user-agent': 'pytest-loco/1.0',
                },
            },
        },
        None,
        id='template with vars',
    ),
    pytest.param(
        {
            'spec': 'template',
            'title': 'A test template',
            'envs': [{
                'name': 'TEST_VAR',
                'description': 'A test variable',
                'default': 'test',
            }],
        },
        None,
        id='template with envs',
    ),
    pytest.param(
        {
            'spec': 'template',
            'title': 'A test template',
            'params': [{
                'name': 'apiToken',
                'required': True,
                'secret': True,
            }],
        },
        None,
        id='template with params definition',
    ),
    pytest.param(
        {
            'spec': 'template',
            'title': 'A test template',
            'metadata': {
                'author': 'Tester',
                'version': '1.0',
            },
        },
        r'^1 validation error',
        id='template with metadata',
    ),
    pytest.param(
        {
            'spec': 'template',
            'title': 'A test template',
            'params': [{
                'name': 'userName',
                'values': [
                    'alice',
                    'bob',
                    'charlie',
                ],
            }],
        },
        r'^1 validation error',
        id='template with valued params',
    ),
))
def test_template_model(content: dict, except_message: 'Pattern | None') -> None:
    """Validate template model schema."""
    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            Template.model_validate(content)
        return

    Template.model_validate(content)


@pytest.mark.parametrize('content, except_message', (
    pytest.param(
        {
            'spec': 'case',
            'title': 'A test case',
            'description': 'Case description',
            'vars': {
                'baseUrl': 'https://api.example.com',
                'timeout': 300,
                'headers': {
                    'user-agent': 'pytest-loco/1.0',
                },
            },
        },
        None,
        id='case with vars',
    ),
    pytest.param(
        {
            'spec': 'case',
            'title': 'A test case',
            'envs': [{
                'name': 'TEST_VAR',
                'description': 'A test variable',
                'default': 'test',
            }],
        },
        None,
        id='case with envs',
    ),
    pytest.param(
        {
            'spec': 'case',
            'title': 'A test case',
            'params': [{
                'name': 'apiToken',
                'required': True,
                'secret': True,
            }],
        },
        r'^2 validation errors for Case',
        id='case with params definition',
    ),
    pytest.param(
        {
            'spec': 'case',
            'title': 'A test case',
            'metadata': {
                'author': 'Tester',
                'version': '1.0',
            },
        },
        None,
        id='case with metadata',
    ),
    pytest.param(
        {
            'spec': 'case',
            'title': 'A test case',
            'params': [{
                'name': 'userName',
                'values': [
                    'alice',
                    'bob',
                    'charlie',
                ],
            }],
        },
        None,
        id='case with simple valued params',
    ),
))
def test_case_model(content: dict, except_message: 'Pattern | None') -> None:
    """Validate case model schema."""
    if except_message is not None:
        with pytest.raises(pydantic.ValidationError, match=except_message):
            Case.model_validate(content)
        return

    Case.model_validate(content)


@pytest.mark.parametrize('content', (
    pytest.param(
        {
            'spec': 'step',
            'title': 'A test step',
            'description': 'Step description',
            'action': 'debug',
            'vars': {
                'baseUrl': 'https://api.example.com',
                'timeout': 300,
                'headers': {
                    'user-agent': 'pytest-loco/1.0',
                },
            },
        },
        id='step with vars',
    ),
    pytest.param(
        {
            'spec': 'step',
            'title': 'A test step',
            'description': 'Step description',
            'action': 'builtin.debug',
            'vars': {
                'baseUrl': 'https://api.example.com',
                'timeout': 300,
                'headers': {
                    'user-agent': 'pytest-loco/1.0',
                },
            },
        },
        id='step with action module',
    ),
))
def test_step_model(content: dict) -> None:
    """Validate step model schema."""
    BaseAction.model_validate(content)


@pytest.mark.parametrize('kind, content', (
    pytest.param(
        BaseAction,
        {
            'spec': 'step',
            'title': 'A test step',
            'description': 'Step description',
            'action': 'debug',
        },
        id='step with discriminator',
    ),
    pytest.param(
        BaseAction,
        {
            'title': 'A test step',
            'description': 'Step description',
            'action': 'debug',
        },
        id='step without discriminator',
    ),
    pytest.param(
        Case,
        {
            'spec': 'case',
            'title': 'A test case',
            'description': 'Case description',
        },
        id='case',
    ),
    pytest.param(
        Template,
        {
            'spec': 'template',
            'title': 'A test template',
            'description': 'template description',
        },
        id='template',
    ),
))
def test_document_root_model(kind: type, content: dict) -> None:
    """Validate document model discrimination."""
    class Document(pydantic.RootModel):
        """A simple document model for testing."""
        root: Case | Template | BaseAction

    document = Document.model_validate(content)

    assert isinstance(document.root, kind)


def test_aliases_extension_required() -> None:
    """Test that `x-aliases` extension generate required updates."""
    schema = (
        pydantic.create_model(
            'TestModel',
            __base__=SchemaModel,
            test=(str, pydantic.Field(
                json_schema_extra={
                    'x-aliases': ['test', 'testField'],
                },
            )),
        )
        .model_json_schema(
            schema_generator=SchemaGenerator,
        )
    )

    assert schema == {
        'additionalProperties': False,
        'oneOf': [
            {'not': {'anyOf': [{'required': ['testField']}]}, 'required': ['test']},
            {'not': {'anyOf': [{'required': ['test']}]}, 'required': ['testField']},
        ],
        'properties': {
            'test': {
                'title': 'Test',
                'type': 'string',
                'x-aliases': ['test', 'testField'],
            },
            'testField': {
                'title': 'Test',
                'type': 'string',
                'x-aliases': ['test', 'testField'],
            },
        },
        'title': 'TestModel',
        'type': 'object',
    }


def test_aliases_extension_optional() -> None:
    """Test that `x-aliases` extension not generate optional updates."""
    schema = (
        pydantic.create_model(
            'TestModel',
            __base__=SchemaModel,
            test1=(str, ...),
            test2=(str | None, pydantic.Field(
                default=None,
                json_schema_extra={
                    'x-aliases': ['test2', 'testField'],
                },
            )),
        )
        .model_json_schema(
            schema_generator=SchemaGenerator,
        )
    )

    assert schema == {
        'additionalProperties': False,
        'properties': {
            'test1': {
                'title': 'Test1',
                'type': 'string',
            },
            'test2': {
                'anyOf': [{'type': 'string'}, {'type': 'null'}],
                'default': None,
                'title': 'Test2',
                'x-aliases': ['test2', 'testField'],
            },
            'testField': {
                'anyOf': [{'type': 'string'}, {'type': 'null'}],
                'default': None,
                'title': 'Test2',
                'x-aliases': ['test2', 'testField'],
            },
        },
        'required': ['test1'],
        'title': 'TestModel',
        'type': 'object',
    }


def test_aliases_extension_empty() -> None:
    """Test that `x-aliases` extension not generate on empty aliases."""
    schema = (
        pydantic.create_model(
            'TestModel',
            __base__=SchemaModel,
            test=(str | None, pydantic.Field(
                default=None,
            )),
        )
        .model_json_schema(
            schema_generator=SchemaGenerator,
        )
    )

    assert schema == {
        'additionalProperties': False,
        'properties': {
            'test': {
                'anyOf': [{'type': 'string'}, {'type': 'null'}],
                'default': None,
                'title': 'Test',
            },
        },
        'title': 'TestModel',
        'type': 'object',
    }


def test_ref_extension() -> None:
    """Test that `x-ref` extension generate reference schema."""
    schema = (
        pydantic.create_model(
            'TestModel',
            __base__=SchemaModel,
            test=(str | None, pydantic.Field(
                default=None,
                json_schema_extra={
                    'x-ref': 'TestRef',
                },
            )),
        )
        .model_json_schema(
            schema_generator=SchemaGenerator,
        )
    )

    assert schema == {
        '$defs': {
            'TestRef': {
                'anyOf': [{'type': 'string'}, {'type': 'null'}],
                'default': None,
                'x-ref': 'TestRef',
            },
        },
        'additionalProperties': False,
        'properties': {
            'test': {'$ref': '#/$defs/TestRef', 'title': 'Test'},
        },
        'title': 'TestModel',
        'type': 'object',
    }


def test_deffered_extension() -> None:
    """Test that `Deferred` type generate runtime value schema."""
    schema = (
        pydantic.create_model(
            'TestModel',
            __base__=SchemaModel,
            test=(Deferred[str], ...),
        )
        .model_json_schema(
            schema_generator=SchemaGenerator,
        )
    )

    assert schema == {
        '$defs': {
            'DeferredCallable_str_': {
                'description': 'Runtime value',
            },
            'Deferred_str_': {
                'anyOf': [
                    {'type': 'string'},
                    {'$ref': '#/$defs/DeferredCallable_str_'},
                    {
                        'items': {'$ref': '#/$defs/Deferred_str_'},
                        'type': 'array',
                    },
                    {
                        'additionalProperties': {'$ref': '#/$defs/Deferred_str_'},
                        'type': 'object',
                    },
                ],
            },
        },
        'additionalProperties': False,
        'properties': {
            'test': {
                '$ref': '#/$defs/Deferred_str_',
            },
        },
        'required': ['test'],
        'title': 'TestModel',
        'type': 'object',
    }
