"""Runtime value resolution utilities for the DSL.

This module defines core value types and a context object responsible for
resolving deferred (lazy) values into fully evaluated DSL values.
"""

from typing import TYPE_CHECKING, Any, overload

from pytest_loco.values import Deferred, Value, normalize

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class ContextDict(dict[str, Value]):
    """Execution context for resolving deferred DSL values.

    The context acts as a mapping of variable names to deferred values.
    It provides a recursive resolver that evaluates callables and nested
    structures into fully resolved DSL values.

    Context instances are expected to be immutable in practice, although
    this is not strictly enforced at the type level.
    """

    @overload
    def resolve[T: Value](self, value: 'Mapping[str, Deferred[T]]') -> 'Mapping[str, T]':
        ...  # pragma: no cover

    @overload
    def resolve[T: Value](self, value: 'Sequence[Deferred[T]]') -> 'Sequence[T]':
        ...  # pragma: no cover

    @overload
    def resolve[T: Value](self, value: Deferred[T]) -> T | None:
        ...  # pragma: no cover


    def resolve(self, value: Any) -> Any:
        """Resolve a deferred value into a fully evaluated value.

        Args:
            value: A deferred value to resolve.

        Returns:
            A fully resolved DSL value or `None`.

        Raises:
            Any exception raised by deferred callables.
        """
        return normalize(value, self)
