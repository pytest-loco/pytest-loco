"""Integration tests for document-level DSL processing."""

from typing import TYPE_CHECKING

import pytest
import yaml

from pytest_loco.core import DocumentParser
from pytest_loco.extensions import Actor, Attribute, Checker, Schema

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from pytest_mock import MockType
    from yaml import SafeLoader


@pytest.mark.parametrize('content', (
    pytest.param((
        'spec: template\n'
        'title: Test template\n'
        'params:\n'
        '  - name: apiToken\n'
        '    required: yes\n'
        '    secret: yes\n'
    ), id='simple template'),
    pytest.param((
        'spec: case\n'
        'title: Test case\n'
        'metadata:\n'
        '  author: Tester\n'
        '  version: 1.0\n'
        'params:\n'
        '  - name: userName\n'
        '    values:\n'
        '    - alice\n'
        '    - bob\n'
        '    - charlie\n'
    ), id='case'),
    pytest.param((
        'spec: step\n'
        'title: Test case\n'
        'action: echo\n'
        'message: Hello, Wold!\n'
        'expect:\n'
        '  - title: Must starts with "Hello"\n'
        '    value: !var result\n'
        '    startsWith: Hello\n'
    ), id='step with spec'),
    pytest.param((
        'spec: step\n'
        'title: Test case\n'
        'action: echo\n'
        'message: Hello, Wold!\n'
        'expect:\n'
        '  - title: Must starts with "Hello"\n'
        '    value: !var result\n'
        '    startsWith: Hello\n'
        '  - title: Must equals as is\n'
        '    value: !var result\n'
        '    equals: Hello, Wold!\n'
    ), id='step without spec'),
))
def test_document_parser(content: str, patch_entrypoints: 'Callable[..., MockType]',
                            loader: 'type[SafeLoader]') -> None:
    """Validate document model generation for supported DSL document types."""
    patch_entrypoints()

    parser = DocumentParser(loader, strict=True, auto_attach=False)

    parser.add_actor(Actor(
        actor=lambda params: {'result': params['message']},
        name='echo',
        parameters=Schema(
            message=Attribute(base=str),
        ),
    ))
    parser.add_checker(Checker(
        checker=lambda value, params: value == params['equals'],
        name='equals',
        field=Attribute(base=str),
    ))
    parser.add_checker(Checker(
        checker=lambda value, params: value.startswith(params['startsWith']),
        name='startsWith',
        field=Attribute(base=str),
    ))

    parser.attach()

    model = parser.build()

    assert model is not None

    document = yaml.load(content, Loader=loader)

    assert model.model_validate(document) is not None
