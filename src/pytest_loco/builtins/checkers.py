"""Built-in comparison checkers for pytest-loco DSL.

This module defines a set of core comparison checkers used in DSL
assertions, including equality, inequality, and ordering comparisons.

The checkers support both strict and partial matching semantics for
scalars, sequences, and mappings.
"""

# ruff: noqa: S101

from contextlib import suppress
from itertools import product
from re import IGNORECASE, MULTILINE, UNICODE, findall
from typing import TYPE_CHECKING

from pytest_loco.errors import DSLRuntimeError
from pytest_loco.extensions import Attribute, Checker, Schema
from pytest_loco.values import MAPPINGS, SCALARS, SEQUENCES

if TYPE_CHECKING:
    from collections.abc import Mapping

if TYPE_CHECKING:
    from pytest_loco.values import RuntimeValue


def _exact_match(actual: 'RuntimeValue', expected: 'RuntimeValue') -> bool:
    """Perform strict equality comparison.

    Args:
        actual: Actual value produced by execution.
        expected: Expected value defined in DSL.

    Returns:
        True if values are strictly equal.

    Raises:
        AssertionError: If values differ or types do not match.
    """
    assert isinstance(actual, type(expected))
    assert actual == expected

    return True


def _seq_partial_match(actual: 'RuntimeValue', expected: 'RuntimeValue') -> bool:
    """Perform partial match for sequences.

    A partial sequence match succeeds if *each expected element*
    matches *at least one* element in the actual sequence.

    Args:
        actual: Actual sequence value.
        expected: Expected sequence value.

    Returns:
        True if the partial match succeeds.

    Raises:
        AssertionError: If inputs are not sequences.
    """
    assert isinstance(actual, SEQUENCES)
    assert isinstance(expected, SEQUENCES)

    matches = 0
    for actual_item, expected_item in product(actual, expected):
        with suppress(AssertionError):
            matches += 1 if _partial_match(actual_item, expected_item) else 0

    return matches >= len(expected)


def _map_partial_match(actual: 'RuntimeValue', expected: 'RuntimeValue') -> bool:
    """Perform partial match for mappings.

    A mapping partially matches if all keys from the expected mapping
    exist in the actual mapping and their corresponding values match
    recursively.

    Args:
        actual: Actual mapping value.
        expected: Expected mapping value.

    Returns:
        True if the partial match succeeds.

    Raises:
        AssertionError: If inputs are not mappings or keys are missing.
    """
    assert isinstance(actual, MAPPINGS)
    assert isinstance(expected, MAPPINGS)

    result = True
    for key, value in expected.items():
        assert key in actual
        result &= _partial_match(actual[key], value)

    return result


def _partial_match(actual: 'RuntimeValue', expected: 'RuntimeValue') -> bool:
    """Recursively perform partial matching.

    Matching strategy depends on the type of the expected value.

    Args:
        actual: Actual value.
        expected: Expected value.

    Returns:
        True if values match according to partial matching rules.

    Raises:
        DSLRuntimeError: If the expected value type is unsupported.
    """
    if isinstance(expected, SCALARS):
        return _exact_match(actual, expected)

    if isinstance(expected, SEQUENCES):
        return _seq_partial_match(actual, expected)

    if isinstance(expected, MAPPINGS):
        return _map_partial_match(actual, expected)

    raise DSLRuntimeError(f'Unsupported type {expected.__class__!r}')  # pragma: no cover


def _eq(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Equality checker implementation.

    Args:
        value: Actual value.
        params: Checker parameters.

    Returns:
        True if the check passes.
    """
    expected = params.get('match')
    check = (
        _partial_match
        if params.get('partial_match', False)
        else _exact_match
    )

    return check(value, expected)


def _neq(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Inequality checker implementation.

    Args:
        value: Actual value.
        params: Checker parameters.

    Returns:
        True if the check passes.
    """
    expected = params.get('not_match')
    check = (
        _partial_match
        if params.get('partial_match', False)
        else _exact_match
    )

    try:
        return not check(value, expected)
    except AssertionError:
        return True


def _cmp(actual: 'RuntimeValue', expected: 'RuntimeValue',
         swap: bool = False, inclusive: bool = False) -> bool:
    """Base implementation for comparisons."""
    if expected is None or actual is None:
        return actual is expected and inclusive

    assert isinstance(actual, type(expected))

    if swap:
        actual, expected = expected, actual

    assert actual < expected or (inclusive and actual == expected)

    return True


def _lt(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Less-than checker."""
    return _cmp(value, params.get('less_than'))


def _lte(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Less-than-or-equal checker."""
    return _cmp(value, params.get('less_than_or_equal'), inclusive=True)


def _gt(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Greater-than checker."""
    return _cmp(value, params.get('greater_than'), swap=True)


def _gte(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Greater-than-or-equal checker."""
    return _cmp(value, params.get('greater_than_or_equal'), swap=True, inclusive=True)


def _regex(value: 'RuntimeValue', params: 'Mapping[str, RuntimeValue]') -> bool:
    """Regex match checker."""
    pattern = params.get('regex')
    if not isinstance(pattern, str):
        return False

    flags = UNICODE
    if params.get('ignore_case'):
        flags |= IGNORECASE
    if params.get('multiline'):
        flags |= MULTILINE

    matches = findall(pattern, value, flags)

    return len(matches) > 0


eq = Checker(
    checker=_eq,
    name='match',
    field=Attribute(
        aliases=['eq', 'equal'],
        required=True,
        title='Expected value',
        description='Value that must match the actual result.',
    ),
    parameters=Schema({
        'partial_match': Attribute(
            base=bool,
            aliases=['partialMatch'],
            default=False,
            title='Partial comparison mode',
            description=(
                'If true, performs recursive partial matching '
                'instead of strict equality comparison.'
            ),
        ),
    }),
)

neq = Checker(
    checker=_neq,
    name='not_match',
    field=Attribute(
        aliases=['notMatch', 'ne', 'notEqual'],
        required=True,
        title='Forbidden value',
        description='Value that must not match the actual result.',
    ),
    parameters=Schema({
        'partial_match': Attribute(
            base=bool,
            aliases=['partialMatch'],
            default=False,
            title='Partial comparison mode',
            description=(
                'If true, performs recursive partial matching '
                'instead of strict equality comparison.'
            ),
        ),
    }),
)

lt = Checker(
    checker=_lt,
    name='less_than',
    field=Attribute(
        aliases=['lt', 'lessThan'],
        required=True,
        title='Upper bound',
        description='Actual value must be less than this value.',
    ),
)

lte = Checker(
    checker=_lte,
    name='less_than_or_equal',
    field=Attribute(
        aliases=['lte', 'lessThanOrEqual'],
        required=True,
        title='Upper bound (inclusive)',
        description='Actual value must be less than or equal to this value.',
    ),
)

gt = Checker(
    checker=_gt,
    name='greater_than',
    field=Attribute(
        aliases=['gt', 'greaterThan'],
        required=True,
        title='Lower bound',
        description='Actual value must be greater than this value.',
    ),
)

gte = Checker(
    checker=_gte,
    name='greater_than_or_equal',
    field=Attribute(
        aliases=['gte', 'greaterThanOrEqual'],
        required=True,
        title='Lower bound (inclusive)',
        description='Actual value must be greater than or equal to this value.',
    ),
)

regex = Checker(
    checker=_regex,
    name='regex',
    field=Attribute(
        aliases=['reMatch', 'regexMatch'],
        required=True,
        title='Regex pattern',
        description='Actual value must be match to this pattern.',
    ),
    parameters=Schema({
        'ignore_case': Attribute(
            base=bool,
            aliases=['ignoreCase'],
            default=False,
            title='Ignore case mode',
            description='If true, performs case-insensitive matching.',
        ),
        'multiline': Attribute(
            base=bool,
            default=False,
            title='Multiline mode',
            description='If true, performs multiline matching.',
        ),
    }),
)
