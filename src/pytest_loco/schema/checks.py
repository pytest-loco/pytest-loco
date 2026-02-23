"""Base check definitions for DSL expectations.

This module defines the base class for declarative value checks used in
expectations during scenario execution.
"""

from collections.abc import Callable, Mapping
from typing import ClassVar

from pydantic import Field

from pytest_loco.context import ContextDict
from pytest_loco.errors import DSLRuntimeError
from pytest_loco.models import DescribedMixin, SchemaModel
from pytest_loco.values import Deferred, RuntimeValue, Value

#: The runner receives a resolved target value and a mapping of resolved
#: check parameters, and must return True if the check passes or False
#: otherwise.
type CheckRunner = Callable[[RuntimeValue, Mapping[str, RuntimeValue]], bool]


class BaseCheck(DescribedMixin, SchemaModel):
    """Base class for declarative value checks.

    Represents a check that validates a resolved value against a specific
    condition. The actual validation logic is provided by a class-level
    runner callable.

    Checks are typically used within expectations to assert properties
    of values produced during scenario execution.
    """

    #: Callable implementing the check logic.
    runner: ClassVar[CheckRunner]

    value: Deferred[Value] = Field(
        title='Target value',
        description=(
            'Value to be validated by the check.\n'
            'The value is resolved against the execution context before '
            'the check is executed.'
        ),
        json_schema_extra={
            'x-ref': 'CheckTargetValue',
        },
    )

    def __call__(self, context: dict[str, Value]) -> bool:
        """Execute the check against the provided context.

        The target value and check parameters are resolved against the
        execution context before invoking the runner.

        Args:
            context: Execution context providing variable values.

        Returns:
            True if the check passes, False otherwise.

        Raises:
            Any exception raised during value resolution or by the runner.
        """
        if not __debug__:
            raise DSLRuntimeError('can not run in optimized mode')

        locals_ = ContextDict(context)

        return type(self).runner(
            locals_.resolve(self.value),
            locals_.resolve(
                self.model_dump(exclude={
                    'value',
                }),
            ),
        )
