"""Tests for action and check runners."""

from collections.abc import Callable  # noqa: TC003
from typing import Any, ClassVar

import pytest

from pytest_loco.builtins.lookups import VariableLookup
from pytest_loco.extensions import Actor, Attribute, Checker, Schema
from pytest_loco.schema import BaseAction, BaseCheck


@pytest.mark.parametrize('var', (True, False))
def test_base_check_runner(var: bool) -> None:
    """Execute a custom check runner with and without inversion."""
    def check(value: bool, params: dict) -> bool:
        return value ^ params.get('invert', False)

    class CustomCheck(BaseCheck):
        invert: bool | Callable = False
        runner: ClassVar[Callable[[Any, dict], Any]] = staticmethod(check)

    direct_check = CustomCheck.model_validate({
        'value': VariableLookup('var'),
    })
    invert_check = CustomCheck.model_validate({
        'value': VariableLookup('var'),
        'invert': True,
    })

    assert direct_check({'var': var}) == var
    assert invert_check({'var': var}) == (not var)


def test_base_action_runner() -> None:
    """Execute a custom action runner with post-execution checks."""
    def step(params: dict) -> str:
        return 'Hello, {name}!'.format(**params)

    class CustomAction(BaseAction):
        name: str | Callable = '<username>'
        runner: ClassVar[Callable[[dict], dict]] = staticmethod(step)

    instance = CustomAction.model_validate({
        'action': 'test.action',
        'name': VariableLookup('userName'),
    })

    context = instance({'userName': 'Alice'})

    assert context['result'] == 'Hello, Alice!'


@pytest.mark.parametrize('var, pattern, invert, except_value', (
    pytest.param(True, True, False, True, id='direct'),
    pytest.param(True, True, True, False, id='invert'),
    pytest.param(True, False, False, False, id='shadow invert'),
))
def test_declarative_check_runner(var: bool, pattern: bool, invert: bool, except_value: bool) -> None:
    """Execute a declaratively defined check."""
    def check(value: bool, params: dict) -> bool:
        real_value = value ^ params.get('invert', False)
        expected_value = params.get('eqBool', True)
        return expected_value == real_value

    model = Checker(
        checker=check,
        name='eqBool',
        field=Attribute(
            base=bool,
            title='Boolean value to compare',
            default=True,
        ),
        parameters=Schema(
            invert=Attribute(
                base=bool,
                title='Match inverted value',
                default=False,
            ),
        ),
    ).build()

    instance = model.model_validate({
        'eqBool': pattern,
        'value': VariableLookup('var'),
        'invert': invert,
    })

    assert instance({'var': var}) == except_value


def test_declarative_action_runner() -> None:
    """Execute a declaratively defined action with schema-based parameters."""
    action_model = Actor(
        actor=lambda params: 'Hello, {name}!'.format(**params),
        name='test',
        parameters=Schema(
            name=Attribute(
                base=str,
                title='Username for greetings',
                aliases=['name', 'username'],
                required=True,
            ),
        ),
    ).build()

    instance = action_model.model_validate({
        'action': 'test',
        'username': VariableLookup('userName'),
    })

    context = instance({'userName': 'Alice'})

    assert context['result'] == 'Hello, Alice!'
