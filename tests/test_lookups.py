"""Tests for context and variable resolvers."""

from typing import Any

import pydantic
import pytest

from pytest_loco.builtins.lookups import LambdaLookup, SecretLookup, VariableLookup
from pytest_loco.errors import DSLRuntimeError, DSLSchemaError


@pytest.mark.parametrize('path, context, expected', (
    pytest.param(
        'simpleVar',
        {'simpleVar': 42},
        42,
        id='simple name',
    ),
    pytest.param(
        'objVar.field',
        {'objVar': {'field': 42}},
        42,
        id='dotted path on mapping',
    ),
    pytest.param(
        'objVar.lstField.1.field',
        {'objVar': {'lstField': ['ignore this', {'field': 42}]}},
        42,
        id='dotted path on sequence',
    ),
))
def test_defined_variable_resolver(path: str, context: dict[str, Any],
                                   expected: Any) -> None:
    """Resolve a variable using a dotted path."""
    resolver = VariableLookup(path)

    assert resolver(context) == expected


@pytest.mark.parametrize('path', (
    pytest.param('_var', id='non-variable start with underscore'),
    pytest.param('0var', id='non-variable start with digit'),
))
def test_invalid_path_variable_resolver(path: str) -> None:
    """Handle variable resolution with an invalid path segment."""
    with pytest.raises(DSLSchemaError, match=r'^Invalid variable path'):
        VariableLookup(path)


def test_empty_part_variable_resolver() -> None:
    """Handle variable resolution with an empty path segment."""
    expected_value = 42
    context = {'obj': {'lst': ['ignore this', {'var': expected_value}]}}
    path = 'obj.lst..1.var'

    resolver = VariableLookup(path)
    resolved = resolver.resolve(context)

    assert resolved is None


def test_undefined_variable_resolver() -> None:
    """Handle resolution of non-existent variables."""
    context = {'obj': {'lst': ['ignore this']}}
    path = 'obj.lst.1.var'

    resolver = VariableLookup(path)
    resolved = resolver.resolve(context)

    assert resolved is None


def test_scalar_container_variable_resolver() -> None:
    """Handle resolution of variables on scalar container."""
    context = {'obj': 42}
    path = 'obj.var.field'

    resolver = VariableLookup(path)
    resolved = resolver.resolve(context)

    assert resolved is None


@pytest.mark.parametrize('path, context, expected', (
    pytest.param(
        'simpleVar',
        {'simpleVar': pydantic.SecretStr('secret')},
        'secret',
        id='simple name',
    ),
    pytest.param(
        'objVar.field',
        {'objVar': {
            'field': pydantic.SecretStr('secret')},
        },
        'secret',
        id='dotted path on mapping',
    ),
    pytest.param(
        'objVar.lstField.1.field',
        {'objVar': {
            'lstField': [
                'ignore this',
                {'field': pydantic.SecretStr('secret')},
            ],
        }},
        'secret',
        id='dotted path on sequence',
    ),
))
def test_defined_secret_resolver(path: str, context: dict[str, Any],
                                 expected: Any) -> None:
    """Resolve a secret variable using a dotted path."""
    resolver = SecretLookup(path)

    assert resolver(context) == expected


@pytest.mark.parametrize('path', (
    pytest.param('_var', id='non-variable start with underscore'),
    pytest.param('0var', id='non-variable start with digit'),
))
def test_invalid_path_secret_resolver(path: str) -> None:
    """Handle secret variable resolution with an invalid path segment."""
    with pytest.raises(DSLSchemaError, match=r'^Invalid variable path'):
        SecretLookup(path)


def test_empty_part_secret_resolver() -> None:
    """Handle secret variable resolution with an empty path segment."""
    context = {'obj': {
        'lst': [
            'ignore this',
            {'var': pydantic.SecretStr('secret')},
        ],
    }}
    path = 'obj.lst..1.var'

    resolver = SecretLookup(path)
    resolved = resolver.resolve(context)

    assert resolved is None


def test_undefined_secret_resolver() -> None:
    """Handle resolution of non-existent secret variables."""
    context = {'obj': {'lst': ['ignore this']}}
    path = 'obj.lst.1.var'

    resolver = SecretLookup(path)
    resolved = resolver.resolve(context)

    assert resolved is None


def test_simple_value_secret_resolver() -> None:
    """Handle resolution of non-secret secret variables."""
    expected = 42
    context = {'obj': {'var': expected}}
    path = 'obj.var'

    resolver = SecretLookup(path)
    resolved = resolver.resolve(context)

    assert resolved == expected


@pytest.mark.parametrize('context', (
    pytest.param('string', id='str'),
    pytest.param(42, id='int'),
    pytest.param(42.0, id='float'),
    pytest.param(True, id='bool'),
    pytest.param([0, 1], id='list'),
    pytest.param((0, 1), id='tuple'),
))
def test_malformed_context_lambda_resolver(context: 'Any') -> None:
    """Handle resolution of lambda on malformed context."""
    resolver = LambdaLookup('var')

    with pytest.raises(DSLRuntimeError, match=r'^Invalid context on lambda call$'):
        resolver.resolve(context)
