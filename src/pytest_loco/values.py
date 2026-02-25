"""Core type definitions for the DSL runtime.

This module defines the foundational type system used by the DSL execution
engine. It distinguishes between fully resolved DSL values and deferred
values that must be evaluated against an execution context at runtime.

It also provides utilities for recursively normalizing arbitrary runtime
objects into strict DSL-compatible values.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import SecretStr

#: Scalars represent fully resolved, atomic values that do not
#: participate in deferred evaluation and can be consumed directly
#: by runtime logic.
type Scalar = date | datetime | timedelta | str | bytes | int | float | bool | SecretStr

#: A value is considered resolved if it contains no deferred
#: computations and can be safely consumed by encoders, decoders,
#: checkers, and other runtime components.
type Value = Scalar | Sequence['Value'] | Mapping[str, 'Value'] | None

#: A value in runtime represents any Python object received from
# external libraries, user-defined code, or YAML loaders prior to
# normalization into a strict `Value`.
type RuntimeValue = Any

#: Deferred values form a recursive structure that is resolved
#: eagerly and deeply by the execution engine before use.
type DeferredCallable[T] = Callable[[Mapping[str, RuntimeValue]], T]
type Deferred[T] = T | DeferredCallable[T] | Sequence['Deferred[T]'] | Mapping[str, 'Deferred[T]']

MAPPINGS = (dict,)
SCALARS = (date, datetime, timedelta, str, bytes, int, float, bool, SecretStr)
SEQUENCES = (list, tuple, set)


def _normalize_key(value: RuntimeValue) -> str:
    """Validate and normalize a mapping key.

    Ensures that mapping keys conform to DSL requirements.

    Args:
        value: Candidate mapping key.

    Returns:
        The validated key as a string.

    Raises:
        TypeError: If the provided key is not a string.
    """
    if not isinstance(value, str):
        raise TypeError(f'Can not use {value!r} as mapping key')

    return value


def normalize(value: RuntimeValue, context: dict[str, Value] | None = None) -> Value:
    """Recursively normalize a runtime value into a DSL `Value`.

    This function converts arbitrary Python objects into strictly
    typed DSL-compatible values. Deferred callables are evaluated
    against the provided context before normalization continues.

    Args:
        value: Runtime value to normalize.
        context: Optional execution context used to resolve deferred
            callables. If not provided, an empty context is used.

    Returns:
        A fully normalized DSL-compatible value.

    Raises:
        TypeError: If the value type is unsupported.
    """
    if value is None:
        return None

    if isinstance(value, SCALARS):
        return value

    if isinstance(value, MAPPINGS):
        return {
           _normalize_key(key): normalize(item, context)
           for key, item in value.items()
        }

    if isinstance(value, SEQUENCES):
        return [
            normalize(item, context)
            for item in value
        ]

    if callable(value):
        if context is None:
            context = {}
        return normalize(value(context), context)

    raise TypeError(f'{value!r} has unsupported type')
