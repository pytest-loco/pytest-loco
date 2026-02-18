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

from .case import TestCase

if TYPE_CHECKING:
    from collections.abc import Iterable

if TYPE_CHECKING:
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
        with self.path.open('rt', encoding='utf-8') as content:
            header, steps = self.config.loco_parser.parse_file(content, expect='case')  # type: ignore[attr-defined]

        yield from self.parametrize(header, steps)

    def parametrize(self, header: 'Case | None',
                    steps: tuple['BaseAction', ...]) -> 'Iterable[TestCase]':
        """Generate parameterized pytest test cases.

        This method assumes that the provided `Case` defines one or more
        parameters. A separate `TestCase` instance is produced for each
        combination of parameter values.

        Args:
            header: Validated DSL case header with declared parameters.
            steps: Tuple of validated DSL steps to execute.

        Yields:
            `TestCase` instances parameterized with concrete values.
        """
        for values in self.prepare_params(header):
            yield TestCase.from_parent(
                self,
                name=self.path.stem,
                header=header,
                steps=steps,
                params=values,
                parser=self.config.loco_parser,  # type: ignore[attr-defined]
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
        if not header or not header.params:
            yield {}
        else:
            names = tuple(param.name for param in header.params)
            for values in product(*(param.values for param in header.params)):
                yield dict(zip(names, values, strict=True))
