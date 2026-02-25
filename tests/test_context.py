"""Tests for context."""

import pytest

from pytest_loco.builtins.lookups import VariableLookup
from pytest_loco.context import ContextDict
from pytest_loco.schema.contexts import ContextMixin
from pytest_loco.values import normalize


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


@pytest.mark.parametrize('isolated', (True, False))
def test_context_mixin_resolver(isolated: bool) -> None:
    """Test ContextMixin resolver for some contexts."""
    local_context = {'localVar': True}
    global_context = {'globalVar': True}

    expected_value = local_context.copy()
    if not isolated:
        expected_value.update(global_context)

    context_model = ContextMixin.model_validate({'vars': local_context})

    actual_value = context_model.resolve_context(global_context, isolate=isolated)
    assert actual_value == expected_value


@pytest.mark.parametrize('isolated', (True, False))
def test_context_mixin_empty_resolver(isolated: bool) -> None:
    """Test ContextMixin resolver for empty contexts."""
    global_context = {'globalVar': True}

    expected_value = {}
    if not isolated:
        expected_value.update(global_context)

    context_model = ContextMixin.model_validate({})

    actual_value = context_model.resolve_context(global_context, isolate=isolated)
    assert actual_value == expected_value


def test_non_string_keys_context_resolver() -> None:
    """Test that non-string keys in context raise an error."""
    resolver = ContextDict({})
    with pytest.raises(TypeError, match=r'^Can not use 42 as mapping key$'):
        resolver.resolve({42: 'value'})


def test_none_context_normalize_as_empty() -> None:
    """Test that `None` is treated as empty context."""
    assert normalize(lambda ctx: ctx.get('var', 'default'), None) == 'default'
