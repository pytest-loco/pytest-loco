"""Built-in DSL instructions for comments and template inclusion.

This module defines runtime DSL actors that do not directly affect
execution logic but influence DSL structure and composition.
"""

from typing import TYPE_CHECKING

from pytest_loco.extensions import Actor

if TYPE_CHECKING:
    from collections.abc import Mapping

if TYPE_CHECKING:
    from pytest_loco.values import RuntimeValue


def _noop(params: 'Mapping[str, RuntimeValue]') -> 'RuntimeValue':  # noqa: ARG001
    """A logic-neutral DSL instruction that acts as a syntactic placeholder.

    This instruction accepts any parameters but performs no processing,
    effectively serving as a 'pass' statement within the DSL execution
    flow. It is used for intermediate calculations where the syntax
    requires an action, or as a temporary placeholder for future logic.

    Args:
        params: Instruction parameters (collected but intentionally ignored).

    Returns:
        Always returns `None`.
    """
    return None


noop = Actor(actor=_noop, name='empty')
