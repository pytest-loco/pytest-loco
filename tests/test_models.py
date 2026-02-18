"""Tests for core document and model schemas."""

from typing import TYPE_CHECKING

import pydantic
import pytest

from pytest_loco.schema import BaseAction, Case, Template

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
