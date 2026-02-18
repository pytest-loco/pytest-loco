"""Examples of custom Instruction definitions.

This module demonstrates how to define a custom YAML constructor
that produces a callable instruction resolver.

The example shows how to:
- parse scalar YAML nodes,
- validate input types,
- return a deferred callable that resolves values using runtime context,
- integrate with PyYAML error reporting.
"""

from typing import TYPE_CHECKING

from yaml.constructor import ConstructorError

from pytest_loco.extensions import Instruction

if TYPE_CHECKING:
    from collections.abc import Callable

if TYPE_CHECKING:
    from yaml import BaseLoader, nodes

if TYPE_CHECKING:
    from pytest_loco.context import Value


def format_constructor(loader: 'BaseLoader',
                       node: 'nodes.ScalarNode') -> 'Callable[[dict[str, Value]], Value]':
    """Create a context-aware formatter resolver from a YAML scalar.

    This constructor expects a string scalar and produces a callable
    that formats the string using values from the runtime context.

    The returned callable is executed later with a context dictionary
    and applies `str.format(**context)` to the original scalar value.

    Args:
        loader: YAML loader instance.
        node: Scalar YAML node containing the format string.

    Returns:
        A callable that accepts a context dictionary and returns the formatted value.

    Raises:
        ConstructorError: If the YAML node value is not a string.

    Notes:
        - Formatting errors (e.g. missing keys) are raised at runtime
          when the returned callable is executed.
        - This constructor is intended as an example of integrating
          YAML parsing with deferred instruction resolution.
    """
    value = loader.construct_scalar(node)
    if not isinstance(value, str):
        raise ConstructorError(
            context='while constructing the format resolver',
            context_mark=node.start_mark,
            problem=f'expected string, got {value!r}',
            problem_mark=node.start_mark,
        )

    return lambda ctx: value.format(**ctx)


fmt = Instruction(
    name='fmt',
    constructor=format_constructor,
)
