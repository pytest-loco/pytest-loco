"""Tests for the checkers plugin system."""

from typing import TYPE_CHECKING

import pytest

from pytest_loco.core import DocumentParser
from pytest_loco.errors import PluginError, PluginWarning
from pytest_loco.extensions import Attribute, Checker, Plugin

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from pytest_mock import MockType


def test_base_loading(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test loading multiple checkers from a plugin and executing them."""
    patch_entrypoints(Plugin(name='test', checkers=[
        Checker(
            name='eq',
            checker=lambda val, params: val == params['eq'],
            field=Attribute(base=int),
        ),
        Checker(
            name='zero',
            checker=lambda val, params: val == 0 if params['zero'] else val != 0,
            field=Attribute(base=bool),
        ),
    ]))

    parser = DocumentParser(None, auto_attach=False)
    model = parser.build_checks(list(parser.checkers.values()))

    assert model is not None

    equal = model.model_validate({'eq': 42, 'value': 42})
    non_zero = model.model_validate({'zero': False, 'value': 42})

    assert callable(equal.root)
    assert callable(non_zero.root)

    assert equal.root({}) is True
    assert non_zero.root({}) is True


def test_one_checker_in_union(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test behavior when the parser contains a single checker."""
    patch_entrypoints()

    parser = DocumentParser(None, auto_attach=False)
    parser.add_checker(Checker(
        name='always',
        checker=lambda val, params: params['always'],  # noqa: ARG005
        field=Attribute(base=bool),
    ))

    for key in parser.checkers:
        assert key.startswith('builtins')

    model = parser.build_checks(list(parser.checkers.values()))

    assert model is not None

    always_true = model.model_validate({'always': True, 'value': 42})
    always_false = model.model_validate({'always': False, 'value': 42})

    assert callable(always_true.root)
    assert callable(always_false.root)

    assert always_true.root({}) is True
    assert always_false.root({}) is False


def test_checkers_shadowing(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test checker name shadowing with non-strict behavior."""
    patch_entrypoints()

    parser = DocumentParser(None, auto_attach=False)
    parser.add_checker(Checker(
        name='always',
        checker=lambda val, params: params['always'],  # noqa: ARG005
        field=Attribute(base=bool),
    ))

    with pytest.warns(PluginWarning, match=r'is shadowing an existing$'):
        parser.add_checker(Checker(
            name='always',
            checker=lambda val, params: not params['always'],  # noqa: ARG005
            field=Attribute(base=bool),
        ))

    model = parser.build_checks(list(parser.checkers.values()))

    assert model is not None

    always_true = model.model_validate({'always': True, 'value': 42})
    always_false = model.model_validate({'always': False, 'value': 42})

    assert callable(always_true.root)
    assert callable(always_false.root)

    assert always_true.root({}) is False
    assert always_false.root({}) is True


def test_checkers_strict_shadowing(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test checker name shadowing in strict mode."""
    patch_entrypoints()

    parser = DocumentParser(None, strict=True, auto_attach=False)
    parser.add_checker(Checker(
        name='always',
        checker=lambda val, params: params['always'],  # noqa: ARG005
        field=Attribute(base=bool),
    ))

    with pytest.raises(PluginError, match=r'is shadowing an existing$'):
        parser.add_checker(Checker(
            name='always',
            checker=lambda val, params: not params['always'],  # noqa: ARG005
            field=Attribute(base=bool),
        ))
