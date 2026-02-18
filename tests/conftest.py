"""Tests configurations and fixtures."""

from importlib.metadata import EntryPoint, EntryPoints
from typing import TYPE_CHECKING

import pytest
import yaml

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from pytest_mock import MockerFixture, MockType

if TYPE_CHECKING:
    from pytest_loco.extensions import Plugin


@pytest.fixture
def loader() -> type[yaml.SafeLoader]:
    """Provide an isolated YAML SafeLoader class for tests.

    Creates a dedicated subclass of `yaml.SafeLoader` to ensure that
    YAML constructors registered during a test do not leak into other
    tests or affect global loader state.

    The returned loader class can be safely extended with custom
    constructors (via `add_constructor`) without interfering with
    PyYAML's default behavior or other test cases.

    Returns:
        A subclass of `yaml.SafeLoader` suitable for isolated DSL parsing.
    """
    class Loader(yaml.SafeLoader):
        pass

    return Loader


@pytest.fixture
def patch_entrypoints(mocker: 'MockerFixture') -> 'Callable[[Plugin, Exception], MockType]':
    """Provide a factory for mocking `importlib.metadata.entry_points`.

    Returns a callable that patches `entry_points()` to simulate
    discovery of plugins in the `loco_plugins` entry point group.

    The returned factory allows configuring:
    - a successfully loadable plugin,
    - or an exception raised during plugin loading,
    - or an empty entry point list.

    This fixture is intended for testing plugin discovery and error
    handling logic without relying on real installed entry points.
    """
    def patch(*plugins: 'Plugin', raises: Exception | None = None) -> 'MockType':
        """Patch `entry_points` with a controlled plugin configuration.

        Args:
            plugins: Plugin objects to be returned by `EntryPoint.load()`.
                If empty, no entry points are registered.
            raises: Exception to raise when `EntryPoint.load()` is called.
                Used to simulate plugin load failures.

        Returns:
            A mock patch object produced by `mocker.patch` that replaces
            `importlib.metadata.entry_points` for the duration of the test.
        """
        entrypoints = []
        for plugin in plugins:
            ep = mocker.Mock(spec=EntryPoint)
            ep.group = 'loco_plugins'
            ep.name = 'tests'
            ep.value = 'tests.plugins:test'
            ep.load.return_value = plugin
            if raises is not None:
                ep.load.side_effect = raises
            entrypoints.append(ep)

        return mocker.patch(
            'importlib.metadata.entry_points',
            return_value=EntryPoints(entrypoints),
        )

    return patch
