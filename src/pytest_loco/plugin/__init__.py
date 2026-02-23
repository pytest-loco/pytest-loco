"""Pytest plugin for collecting and executing YAML-based DSL specifications.

This module integrates the `pytest-loco` DSL with pytest by:
- registering custom command-line options;
- configuring a shared `DocumentParser` instance;
- collecting YAML files as executable test specifications.

YAML files matching the pattern `test_*.yml` or `test_*.yaml` are
automatically collected and parsed into pytest test items.
"""

from re import match
from typing import TYPE_CHECKING

from yaml import Loader, SafeLoader

from .spec import TestSpec

if TYPE_CHECKING:
    from pathlib import Path

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Node


def pytest_addoption(parser: 'Parser') -> None:
    """Register pytest command-line options for pytest-loco.

    Args:
        parser: Pytest argument parser.
    """
    parser.addoption(
        '--loco-unsafe-yaml',
        action='store_true',
        dest='loco_unsafe_yaml',
        default=False,
        help=(
            'Allow loading YAML files using the unsafe PyYAML Loader. '
            'This enables execution of arbitrary Python objects and '
            'should only be used with trusted test specifications.'
        ),
    )
    parser.addoption(
        '--loco-relaxed',
        action='store_true',
        dest='loco_relaxed',
        default=False,
        help=(
            'Disable strict DSL validation. '
            'Field rewriting and shadowing, third-party plugin loading errors '
            'will not cause test collection or execution to fail.'
        ),
    )
    parser.addoption(
        '--loco-allow-lambda',
        action='store_true',
        dest='loco_allow_lambda',
        default=False,
        help=(
            'Allow usage of inline lambda expressions inside DSL documents. '
            'This may reduce safety and reproducibility of test specifications.'
        ),
    )


def pytest_configure(config: 'Config') -> None:
    """Configure pytest-loco integration.

    This hook initializes a shared `DocumentParser` instance and
    attaches it to the pytest configuration object as `config.loco_parser`.

    Args:
        config: Pytest configuration object.
    """
    loader: type[Loader | SafeLoader] = SafeLoader
    if config.getoption('--loco-unsafe-yaml'):
        loader = Loader

    from pytest_loco.core import DocumentParser  # noqa: PLC0415

    config.loco_parser = DocumentParser(  # type: ignore[attr-defined]
        loader,
        allow_lambda=config.getoption('--loco-allow-lambda', default=False),
        strict=not config.getoption('--loco-relaxed', default=False),
        auto_build=True,
    )


def pytest_collect_file(parent: 'Node', file_path: 'Path') -> TestSpec | None:
    """Collect YAML DSL specification files.

    Files matching the pattern `test_*.yml` or `test_*.yaml` are treated
    as executable DSL specifications and collected using `TestSpec`.

    Args:
        parent: Parent pytest collection node.
        file_path: Path to the file being considered.

    Returns:
        A `TestSpec` collector if the file matches the DSL pattern, otherwise ``None``.
    """
    if match(r'^test_.+\.ya?ml$', file_path.name):
        return TestSpec.from_parent(
            parent,
            path=file_path,
        )

    return None
