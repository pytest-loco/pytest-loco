"""Pytest plugin for collecting and executing YAML-based DSL specifications.

This module integrates the `pytest-loco` DSL with pytest by:
- registering custom command-line options;
- configuring a shared `DocumentParser` instance;
- collecting YAML files as executable test specifications.

YAML files matching the pattern `test_*.yml` or `test_*.yaml` are
automatically collected and parsed into pytest test items.
"""

from re import match
from typing import TYPE_CHECKING, Any

from pytest import UsageError
from yaml import Loader, SafeLoader

from pytest_loco.core import DocumentParser
from pytest_loco.errors import DSLBuildError

from .spec import TestSpec

if TYPE_CHECKING:
    from pathlib import Path


def pytest_addoption(parser: Any) -> None:  # noqa: ANN401
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


def pytest_configure(config: Any) -> None:  # noqa: ANN401
    """Configure pytest-loco integration.

    This hook initializes a shared `DocumentParser` instance and
    attaches it to the pytest configuration object as `config.loco_parser`.

    Args:
        config: Pytest configuration object.
    """
    loader: type[Loader | SafeLoader] = SafeLoader
    if config.getoption('--loco-unsafe-yaml'):
        loader = Loader

    try:
        config.loco_parser = DocumentParser(
            loader,
            allow_lambda=config.getoption('--loco-allow-lambda', default=False),
            strict=not config.getoption('--loco-relaxed', default=False),
            auto_build=True,
        )

    except DSLBuildError as error:
        raise UsageError('Can not load the `pytest-loco` plugins.') from error


def pytest_collect_file(parent: Any, file_path: 'Path') -> TestSpec | None:  # noqa: ANN401
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
        return TestSpec.from_parent(parent, path=file_path)

    return None
