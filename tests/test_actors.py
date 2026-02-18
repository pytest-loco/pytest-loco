"""Tests for the actors plugin system."""

from typing import TYPE_CHECKING

import pytest

from pytest_loco.core import DocumentParser
from pytest_loco.errors import PluginError, PluginWarning
from pytest_loco.extensions import Actor, Attribute, Plugin, Schema

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from pytest_mock import MockType


def test_base_loading(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test loading multiple actors from a plugin and executing them."""
    patch_entrypoints(Plugin(name='test', actors=[
        Actor(
            name='returnValue',
            actor=lambda params: params['valueToReturn'],
            parameters=Schema(
                valueToReturn=Attribute(base=int),
            ),
        ),
        Actor(
            name='returnConstant',
            actor=lambda params: 42,  # noqa: ARG005
        ),
    ]))

    parser = DocumentParser(None, auto_attach=False)
    model = parser.build_actions(
        list(parser.actors.values()),
    )

    assert model is not None

    ret_val = model.model_validate({
        'action': 'test.returnValue',
        'valueToReturn': 42,
    })
    ret_const = model.model_validate({
        'action': 'test.returnConstant',
        'output': 'constResult',
    })

    assert callable(ret_val.root)
    assert callable(ret_const.root)

    assert ret_val.root({}) == {'result': 42}
    assert ret_const.root({}) == {'constResult': 42}


def test_actors_shadowing(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test actor name shadowing with non-strict behavior."""
    patch_entrypoints()

    parser = DocumentParser(None, auto_attach=False)

    parser.add_actor(Actor(
        name='increment',
        actor=lambda params: params['incValue'] + 1,
        parameters=Schema(
            incValue=Attribute(base=int),
        ),
    ))

    with pytest.warns(PluginWarning, match=r'is shadowing an existing$'):
        parser.add_actor(Actor(
            name='increment',
            actor=lambda params: params['incValue'] + 2,
            parameters=Schema(
                incValue=Attribute(base=int),
            ),
        ))

    model = parser.build_actions(
        list(parser.actors.values()),
    )

    assert model is not None

    inc_val = model.model_validate({
        'action': 'increment',
        'incValue': 41,
    })

    assert callable(inc_val.root)

    assert inc_val.root({}) == {'result': 41 + 2}


def test_actors_strict_shadowing(patch_entrypoints: 'Callable[..., MockType]') -> None:
    """Test actor name shadowing in strict mode."""
    patch_entrypoints()

    parser = DocumentParser(None, strict=True, auto_attach=False)

    parser.add_actor(Actor(
        name='increment',
        actor=lambda params: params['incValue'] + 1,
        parameters=Schema(
            incValue=Attribute(base=int),
        ),
    ))

    with pytest.raises(PluginError, match=r'is shadowing an existing$'):
        parser.add_actor(Actor(
            name='increment',
            actor=lambda params: params['incValue'] + 2,
            parameters=Schema(
                incValue=Attribute(base=int),
            ),
        ))
