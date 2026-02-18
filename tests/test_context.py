"""Tests for context."""

import pytest

from pytest_loco.builtins.lookups import VariableLookup
from pytest_loco.context import ContextDict


def test_mapping_context_resolver() -> None:
    """Resolve mapping using provided context."""
    resolver = ContextDict({'var': 10})
    resolved = resolver.resolve({
        'value': lambda ctx: ctx['var'] * 2,
        'static': 'static_value',
    })

    assert resolved == {
        'value': 20,
        'static': 'static_value',
    }


def test_self_context_resolver() -> None:
    """Resolve context mapping using provided context."""
    resolver = ContextDict({'var': 10})
    resolved = resolver.resolve(ContextDict({
        'value': lambda ctx: ctx['var'] * 2,
        'static': 'static_value',
    }))

    assert resolved == {
        'value': 20,
        'static': 'static_value',
    }


@pytest.mark.parametrize('value', (
    pytest.param([1, 2, lambda ctx: ctx['var'] * 2, 4.0], id='list'),
    pytest.param((1, 2, lambda ctx: ctx['var'] * 2, 4.0), id='tuple'),
    pytest.param({1, 2, lambda ctx: ctx['var'] * 2, 4.0}, id='set'),
))
def test_iterable_context_resolver(value: list | tuple | set) -> None:
    """Resolve iterable containers."""
    resolver = ContextDict({'var': 10})
    resolved = resolver.resolve(value)

    assert sorted(resolved, key=str) == sorted([1, 2, 20, 4.0], key=str)


@pytest.mark.parametrize('value', (
    pytest.param(42, id='int'),
    pytest.param(42.6, id='float'),
    pytest.param('test', id='str'),
    pytest.param(False, id='false'),
    pytest.param(True, id='true'),
    pytest.param(None, id='none'),
))
def test_scalars_context_resolver(value: int | float | str | bool | None) -> None:
    """Resolve scalar values inside containers."""
    resolver = ContextDict({'var': value})

    assert resolver.resolve(VariableLookup('var')) == value

def test_usupported_type_context_resolver() -> None:
    """Resolve scalar values inside containers."""
    class NewType:
        def __init__(self, value: str) -> None:
            self.value = value

    resolver = ContextDict({})

    with pytest.raises(TypeError, match=r'has unsupported type$'):
        resolver.resolve(NewType(20))
