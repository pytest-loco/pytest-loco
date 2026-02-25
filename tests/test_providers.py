"""Tests for plugin loading and execution."""

from typing import TYPE_CHECKING

import pydantic
import pytest
import yaml

from pytest_loco.core import DocumentParser
from pytest_loco.errors import PluginError, PluginWarning
from pytest_loco.extensions import Plugin
from tests.examples.contents import json
from tests.examples.plugins import example

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from pytest_mock import MockType


def test_base_loading(patch_entrypoints: 'Callable[..., MockType]',
                      loader: type[yaml.SafeLoader]) -> None:
    """Verify successful loading of instructions and content types from entrypoints."""
    patch_entrypoints(example)

    DocumentParser(loader, auto_attach=True, auto_build=True)

    contents = '!dump\n  format: json\n  source:\n    message: !fmt "Hello, {userName}!"\n'
    encoder = yaml.load(contents, Loader=loader)

    assert callable(encoder)
    assert encoder({'userName': 'Alice'}) == '{"message": "Hello, Alice!"}'


def test_fail_on_invalid_content_schema(patch_entrypoints: 'Callable[..., MockType]',
                                        loader: type[yaml.SafeLoader]) -> None:
    """Verify failure on invalid content schema."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)

    parser.add_content_type(json)
    parser.attach()

    contents = '!dump\n  format: json\n  source: !var value\n  unknown: yes'
    with pytest.raises(yaml.error.MarkedYAMLError, match=r'^while constructing the content resolver'):
        yaml.load(contents, Loader=loader)


def test_loading_with_empty_entrypoint(patch_entrypoints: 'Callable[..., MockType]',
                                       loader: type[yaml.SafeLoader]) -> None:
    """Verify behavior when plugins provide no instructions or content types."""
    patch_entrypoints(Plugin(name='empty'))

    DocumentParser(loader, auto_build=True)

    contents = '!dump\n  format: json\n  source:\n    message: !fmt "Hello, {userName}!"\n'
    with pytest.raises(yaml.error.MarkedYAMLError, match=r'^could not determine a constructor for the tag \'!dump\''):
        yaml.load(contents, Loader=loader)


def test_loading_skip_with_failed_entrypoint(patch_entrypoints: 'Callable[..., MockType]',
                                             loader: type[yaml.SafeLoader]) -> None:
    """Verify skipping of plugins that fail during loading."""
    patch_entrypoints(None, raises=SyntaxError)
    with pytest.warns(PluginWarning, match=r'^Failed to load entrypoint'):
        DocumentParser(loader, auto_build=True)


def test_loading_fail_with_failed_entrypoint(patch_entrypoints: 'Callable[..., MockType]',
                                             loader: type[yaml.SafeLoader]) -> None:
    """Verify failing of plugins that fail during loading with strict mode."""
    patch_entrypoints(None, raises=SyntaxError)
    with pytest.raises(PluginError, match=r'^Failed to load entrypoint'):
        DocumentParser(loader, strict=True)


def test_loading_skip_with_not_valid_entrypoint(patch_entrypoints: 'Callable[..., MockType]',
                                                loader: type[yaml.SafeLoader]) -> None:
    """Verify skipping of plugins that fail validation during loading with strict mode."""
    try:
        pydantic.TypeAdapter(int).validate_python('error')
    except pydantic.ValidationError as exception:
        error = exception

    patch_entrypoints(None, raises=error)
    with pytest.warns(PluginWarning, match=r'^Failed to validate entrypoint'):
        DocumentParser(loader, strict=False)


def test_loading_fail_with_not_valid_entrypoint(patch_entrypoints: 'Callable[..., MockType]',
                                                loader: type[yaml.SafeLoader]) -> None:
    """Verify failing of plugins that fail validation during loading with strict mode."""
    try:
        pydantic.TypeAdapter(int).validate_python('error')
    except pydantic.ValidationError as exception:
        error = exception

    patch_entrypoints(None, raises=error)
    with pytest.raises(PluginError, match=r'^Failed to validate entrypoint'):
        DocumentParser(loader, strict=True)


def test_loading_skip_with_invalid_provider(patch_entrypoints: 'Callable[..., MockType]',
                                            loader: type[yaml.SafeLoader]) -> None:
    """Verify handling of invalid instruction providers."""
    patch_entrypoints({})
    with pytest.warns(PluginWarning, match=r'object is not a plugin$'):
        DocumentParser(loader, auto_build=True)


def test_loading_fail_with_invalid_provider(patch_entrypoints: 'Callable[..., MockType]',
                                            loader: type[yaml.SafeLoader]) -> None:
    """Verify failing on invalid instruction providers with strict mode."""
    patch_entrypoints({})
    with pytest.raises(PluginError, match=r'object is not a plugin$'):
        DocumentParser(loader, strict=True)
