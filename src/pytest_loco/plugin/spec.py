"""Pytest integration for YAML-based DSL specifications.

This module defines a custom pytest file collector that treats YAML
files as executable DSL specifications.

Each collected file is parsed using a preconfigured `DocumentParser`
and converted into one or more `TestCase` instances.

If a DSL `Case` defines parameters, the collector automatically
generates a separate pytest test case for each combination of
parameter values.
"""

from itertools import product
from typing import TYPE_CHECKING

import pytest

from pytest_loco.errors import WRAP_VERBOSITY_LIMIT, DSLError

from .case import TestCase

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

if TYPE_CHECKING:
    from pytest_loco.core import DocumentParser
    from pytest_loco.schema import BaseAction, Case
    from pytest_loco.values import Value


class TestSpec(pytest.File):
    """Pytest file collector for DSL specification files.

    This collector:
    - parses a DSL YAML document using `DocumentParser`;
    - detects an optional `Case` header;
    - expands parameterized cases into multiple pytest test items.

    Each resulting execution plan is wrapped into a `TestCase` item.
    """

    __test__ = False

    def collect(self) -> 'Iterable[TestCase]':
        """Collect pytest test cases from a DSL specification file.

        The method parses the YAML file into DSL documents, determines
        whether the first document is a `Case` header, and generates
        pytest test cases accordingly.

        If the case defines parameters, multiple test cases are produced.
        Otherwise, a single test case is emitted.

        Returns:
            Iterable of `TestCase` instances for pytest execution.

        Raises:
            ValueError: If the DSL document is malformed and the parser
                operates in strict mode.
        """
        parser: DocumentParser | None = getattr(self.config, 'loco_parser', None)
        if not parser:
            return

        with self.path.open('rt', encoding='utf-8') as content:
            header, steps = parser.parse_file(content, expect='case')

        yield from self.parametrize(parser, header, steps)  # type: ignore[arg-type]

    def parametrize(self, parser: 'DocumentParser', header: 'Case | None',
                    steps: tuple['BaseAction', ...]) -> 'Iterable[TestCase]':
        """Generate parameterized pytest test cases.

        This method assumes that the provided `Case` defines one or more
        parameters. A separate `TestCase` instance is produced for each
        combination of parameter values.

        Args:
            parser: DSL document parser.
            header: Validated DSL case header with declared parameters.
            steps: Tuple of validated DSL steps to execute.

        Yields:
            `TestCase` instances parameterized with concrete values.
        """
        for i, values in enumerate(self.prepare_params(header)):
            name = self.path.stem
            if values:
                name = f'{name}[combination={i}]'

            yield TestCase.from_parent(
                self,
                header=header,
                steps=steps,
                params=values,
                name=name,
                parser=parser,
            )

    @staticmethod
    def prepare_params(header: 'Case | None') -> 'Iterable[dict[str, Value]]':
        """Prepare params from a DSL specification file.

        Returns empty, if the DSL specification file is empty
        or the DSL specification file is template.

        Args:
            header: Header of the DSL specification file.

        Returns:
            Combinations tuple of params.
        """
        params = getattr(header, 'params', ())

        names = tuple(param.name for param in params)
        for values in product(*(param.values for param in params)):
            yield dict(zip(names, values, strict=True))

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException],
                     style: 'Any' = None) -> 'Any':  # noqa: ANN401
        """Return a representation of a collection failure.

        Args:
            excinfo: Exception information for the failure.
            style: Traceback style.

        Returns:
            String or terminal representation for the error.
        """
        if not style:
            style = self.config.getoption('tbstyle', 'auto')
            if style == 'auto':
                style = 'short'

        verbosity = self.config.get_verbosity()

        if verbosity < WRAP_VERBOSITY_LIMIT and isinstance(excinfo.value, DSLError):
            if excinfo.value.context and not excinfo.value.context.get('filename'):
                excinfo.value.context['filename'] = self.path.as_posix()
            isatty = False
            if reporter := self.config.pluginmanager.get_plugin('terminalreporter'):
                isatty = bool(reporter.isatty)
            return excinfo.value.repr(isatty, verbosity)

        return super().repr_failure(excinfo)
