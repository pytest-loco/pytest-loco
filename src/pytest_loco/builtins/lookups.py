"""Runtime value and variable resolution utilities.

This module provides core helpers for resolving declarative DSL values
into concrete runtime data. It supports:

- Recursive resolution of nested structures
- Deferred evaluation via callables
- Safe variable lookup using dotted paths
- Unsafe variable lookup using lambda expressions
"""

from typing import TYPE_CHECKING

from pytest_loco.errors import DSLRuntimeError, DSLSchemaError
from pytest_loco.names import VARIABLE_PATTERN

if TYPE_CHECKING:
    from pydantic import SecretStr

if TYPE_CHECKING:
    from pytest_loco.values import RuntimeValue


class VariableLookup:
    """Resolver for dotted-path variable access.

    Resolves values from nested data structures (dicts and lists)
    using a dot-separated path notation.

    The resolver is intentionally tolerant: any missing key, invalid
    index, or type mismatch results in `None` instead of raising
    an exception. This behavior is designed for use in declarative DSLs,
    where unresolved variables should fail gracefully.
    """

    def __init__(self, path: str) -> None:
        """Initialize the resolver with a dotted path.

        Args:
            path: Dot-separated path describing how to traverse
                a nested structure. Each segment represents either:
                - a dictionary key
                - a list index (if the segment is numeric)

        Raises:
            DSLSchemaError: If the provided path is not valid.
        """
        self.path = path.strip().split('.')

        if not VARIABLE_PATTERN.match(self.path[0]):
            raise DSLSchemaError('Invalid variable path')

    def __call__(self, context: dict[str, 'RuntimeValue']) -> 'RuntimeValue':
        """Resolve the variable path against a context."""
        return self.resolve(context)

    def resolve(self, val: 'RuntimeValue', depth: int = 1) -> 'RuntimeValue':
        """Resolve the variable path against a value.

        Traverses the provided value according to the configured path.
        Resolution stops early if a segment cannot be applied.

        Args:
            val: Current value being resolved.
            depth: Current depth of traversal (used internally).

        Returns:
            The resolved value if the full path is valid, otherwise `None`.
        """
        if val is None or depth > len(self.path):
            return val

        key = self.path[depth - 1]
        if not key:
            return None

        next_val = None
        if key.isdecimal() and isinstance(val, (list, tuple)):
            index = int(key)
            if 0 <= index < len(val):
                next_val = val[index]
        elif isinstance(val, dict):
            next_val = val.get(key)
        else:
            return None

        return self.resolve(next_val, depth + 1)


class SecretLookup(VariableLookup):
    """Variable resolver that safely extracts secret values.

    This resolver extends `VariableLookup` and unwraps values of type
    `SecretStr`, returning their underlying secret value. Non-secret
    values are intentionally ignored to prevent accidental disclosure.
    """

    def __call__(self, context: dict[str, 'RuntimeValue']) -> 'RuntimeValue':
        """Resolve and unwrap a secret value from the context.

        Args:
            context: Execution context used for variable resolution.

        Returns:
            The underlying secret string if the resolved value is a
            `SecretStr`, otherwise `None`.

        Notes:
            Returning `None` for non-secret values is a deliberate
            fail-closed behavior to avoid leaking sensitive data.
        """
        value = super().resolve(context)

        if hasattr(value, 'get_secret_value'):
            secret: SecretStr = value
            return secret.get_secret_value()

        return value


class LambdaLookup:
    """Deferred resolver based on a lambda expression.

    This resolver compiles a Python lambda expression from a string
    and evaluates it against a provided execution context at runtime.

    The expression is evaluated using `eval` with disabled builtins
    and access only to the provided context mapping.

    Notes:
        - Only expressions are supported (no statements).
        - This is not a full sandbox. Any callable or object present
          in the context can be invoked by the expression.
        - Intended for controlled DSL usage, not for untrusted input.
    """

    def __init__(self, body: str) -> None:
        """Compile a lambda expression body.

        Args:
            body: A string representing the body of a lambda expression.

        Raises:
            DSLSchemaError: If the expression is syntactically invalid or
                cannot be compiled as a lambda expression.
        """
        try:
            self.runner = compile(f'lambda: {body}', filename='<input>', mode='eval')
        except SyntaxError as error:
            raise DSLSchemaError('Invalid syntax for lambda body') from error

    def __call__(self, context: dict[str, 'RuntimeValue']) -> 'RuntimeValue':
        """Evaluate the compiled lambda expression with a context."""
        return self.resolve(context)

    def resolve(self, context: dict[str, 'RuntimeValue']) -> 'RuntimeValue':
        """Evaluate the compiled lambda expression.

        The expression is evaluated using `eval` with:
            - disabled builtins
            - the provided context as local variables

        Args:
            context: Mapping used as the local namespace for evaluation.

        Returns:
            Result of the evaluated expression.

        Raises:
            DSLRuntimeError: If the expression cannot be evaluated
                to a callable or if evaluation fails.
        """
        if not isinstance(context, dict):
            raise DSLRuntimeError('Invalid context on lambda call')

        try:
            runner = eval(self.runner, {**context, '__builtins__': None})  # noqa: S307
            return runner()

        except Exception as error:
            raise DSLRuntimeError('Error during lambda expression evaluation') from error
