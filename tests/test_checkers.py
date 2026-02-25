"""Tests for the checkers plugin system."""

# ruff: noqa: SLF001

from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from pytest_loco.builtins import checkers
from pytest_loco.core import DocumentParser
from pytest_loco.errors import PluginError, PluginWarning
from pytest_loco.extensions import Attribute, Checker, Plugin

if TYPE_CHECKING:
    from collections.abc import Callable
    from re import Pattern
    from typing import Any

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


@pytest.mark.parametrize('f, param, actual, expected, result', (
    pytest.param(checkers._lt, 'less_than', 42, 42, False, id='LT: equal'),
    pytest.param(checkers._lt, 'less_than', 42, 0, False, id='LT: false comparison'),
    pytest.param(checkers._lt, 'less_than', 0, 42, True, id='LT: true comparison'),
    pytest.param(checkers._lt, 'less_than', None, 42, False, id='LT: None and value'),
    pytest.param(checkers._lt, 'less_than', 42, None, False, id='LT: value and None'),
    pytest.param(checkers._lt, 'less_than', 42, 0.0, False, id='LT: different types'),
    pytest.param(checkers._lte, 'less_than_or_equal', 42, 42, True, id='LTE: equal'),
    pytest.param(checkers._lte, 'less_than_or_equal', 42, 0, False, id='LTE: false comparison'),
    pytest.param(checkers._lte, 'less_than_or_equal', 0, 42, True, id='LTE: true comparison'),
    pytest.param(checkers._lte, 'less_than_or_equal', None, 42, False, id='LTE: None and value'),
    pytest.param(checkers._lte, 'less_than_or_equal', 42, None, False, id='LTE: value and None'),
    pytest.param(checkers._lte, 'less_than_or_equal', 42, 0.0, False, id='LTE: different types'),
    pytest.param(checkers._gt, 'greater_than', 42, 42, False, id='GT: equal'),
    pytest.param(checkers._gt, 'greater_than', 42, 0, True, id='GT: false comparison'),
    pytest.param(checkers._gt, 'greater_than', 0, 42, False, id='GT: true comparison'),
    pytest.param(checkers._gt, 'greater_than', None, 42, False, id='GT: None and value'),
    pytest.param(checkers._gt, 'greater_than', 42, None, False, id='GT: value and None'),
    pytest.param(checkers._gt, 'greater_than', 42, 0.0, False, id='GT: different types'),
    pytest.param(checkers._gte, 'greater_than_or_equal', 42, 42, True, id='GTE: equal'),
    pytest.param(checkers._gte, 'greater_than_or_equal', 42, 0, True, id='GTE: false comparison'),
    pytest.param(checkers._gte, 'greater_than_or_equal', 0, 42, False, id='GTE: true comparison'),
    pytest.param(checkers._gte, 'greater_than_or_equal', None, 42, False, id='GTE: None and value'),
    pytest.param(checkers._gte, 'greater_than_or_equal', 42, None, False, id='GTE: value and None'),
    pytest.param(checkers._gte, 'greater_than_or_equal', 42, 0.0, False, id='GTE: different types'),
))
def test_builtin_comparators(f: 'Callable[[Any, Any], bool]', param: str,
                             actual: 'Any', expected: 'Any', result: bool) -> None:
    """Test the built-in comparison checker with various inputs."""
    real_result = False
    with suppress(AssertionError):
        real_result = f(actual, {param: expected})

    assert real_result == result


@pytest.mark.parametrize('actual, expected, result', (
    pytest.param(42, 42, True, id='EQ: equal'),
    pytest.param(42, 0, False, id='EQ: not equal'),
    pytest.param({'a': 1, 'b': 2}, {'a': 1, 'b': 2}, True, id='EQ: dict equal'),
    pytest.param({'a': 1, 'b': 2}, {'a': 1}, False, id='EQ: dict not equal'),
    pytest.param([42, 0], [42, 0], True, id='EQ: list equal'),
    pytest.param([42, 0], [42, 1], False, id='EQ: list not equal'),
))
def test_exact_match(actual: 'Any', expected: 'Any', result: bool) -> None:
    """Test the exact match checker."""
    real_result = False
    with suppress(AssertionError):
        real_result = checkers._eq(actual, {'match': expected, 'partial_match': False})

    assert real_result == result


@pytest.mark.parametrize('actual, expected, result', (
    pytest.param(42, 42, False, id='NEQ: equal'),
    pytest.param(42, 0, True, id='NEQ: not equal'),
    pytest.param({'a': 1, 'b': 2}, {'a': 1, 'b': 2}, False, id='NEQ: dict equal'),
    pytest.param({'a': 1, 'b': 2}, {'a': 1}, True, id='NEQ: dict not equal'),
    pytest.param([42, 0], [42, 0], False, id='NEQ: list equal'),
    pytest.param([42, 0], [42, 1], True, id='NEQ: list not equal'),
))
def test_exact_not_match(actual: 'Any', expected: 'Any', result: bool) -> None:
    """Test the exact not match checker."""
    real_result = False
    with suppress(AssertionError):
        real_result = checkers._neq(actual, {'not_match': expected, 'partial_match': False})

    assert real_result == result


@pytest.mark.parametrize('actual, expected, result', (
    pytest.param({'a': 1, 'b': 2}, {'a': 1}, True, id='Partial EQ: dict partial match'),
    pytest.param({'a': 1, 'b': 2}, {'a': 2}, False, id='Partial EQ: dict partial not match'),
    pytest.param([42, 0], [42], True, id='Partial EQ: list partial match'),
    pytest.param([42, 0], [95], False, id='Partial EQ: list partial not match'),
))
def test_partial_match(actual: 'Any', expected: 'Any', result: bool) -> None:
    """Test the partial match checker."""
    real_result = False
    with suppress(AssertionError):
        real_result = checkers._eq(actual, {'match': expected, 'partial_match': True})

    assert real_result == result


@pytest.mark.parametrize('pattern, result', (
    pytest.param(r'', True, id='Regex: empty pattern'),
    pytest.param(r'^Hello\sworld$', True, id='Regex: full match'),
    pytest.param(r'^Hello$', False, id='Regex: not matching'),
    pytest.param(r'^Hello', True, id='Regex: starts with'),
    pytest.param(r'world$', True, id='Regex: ends with'),
    pytest.param(None, False, id='Regex: none pattern'),
    pytest.param(42, False, id='Regex: wrong type pattern'),
))
def test_regex_match(pattern: 'Pattern | str', result: bool) -> None:
    """Test the regex match checker."""
    assert result == checkers._regex('Hello world', {'regex': pattern})


def test_regex_multiline_match() -> None:
    """Test the regex match checker with multiline strings."""
    assert checkers._regex('Hello\nWorld', {'regex': r'^World$', 'multiline': True})
    assert not checkers._regex('Hello\nWorld', {'regex': r'^World$', 'multiline': False})


def test_regex_ignorecase_match() -> None:
    """Test the regex match checker with ignore case flag."""
    assert checkers._regex('HELLO WORLD', {'regex': r'^hello world$', 'ignore_case': True})
    assert not checkers._regex('HELLO WORLD', {'regex': r'^hello world$', 'ignore_case': False})
