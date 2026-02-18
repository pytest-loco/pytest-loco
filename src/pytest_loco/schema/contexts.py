"""Base context operation definitions.

This module defines the mixin for declarative context-processing
operations used in the DSL, such as definition of local context.
"""

from pydantic import Field

from pytest_loco.context import ContextDict
from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.values import Deferred, Value  # noqa: TC001


class ContextMixin(SchemaModel):
    """Mixin providing local execution context variables.

    Adds a declarative mapping of local variables that are resolved
    against the current execution context and may be merged by the
    execution engine into the active context scope.

    The mixin does not define how or when the context is applied;
    it only declares and resolves the variables it contributes.
    """

    context: dict[Variable, Deferred[Value]] = Field(
        default_factory=dict,
        validation_alias='vars',
        title='Local context',
        description=(
            'Local context variables provided to block. '
            'These variables are added to the execution context and can be '
            'referenced by subsequent steps.'
        ),
        json_schema_extra={
            'x-ref': 'ContextVariables',
        },
    )

    def resolve_context(self, values: dict[str, Value], *,
                        isolate: bool = False) -> ContextDict:
        """Resolve local context variables against the execution context.

        Resolves all deferred values declared in the local context using
        the provided execution context. The returned mapping contains
        only the resolved local variables and does not modify the input
        context.

        Args:
            values: Current execution context.
            isolate: If true, return only predefined context values.

        Returns:
            A new context with resolved local context variables.

        Raises:
            Any exception raised during deferred value resolution.
        """
        if isolate and not self.context:
            return ContextDict()

        globals_ = ContextDict(values)
        if not self.context:
            return globals_

        locals_: dict[str, Value] = {}
        if not isolate:
            locals_.update(globals_)

        locals_.update(globals_.resolve(self.context))

        return ContextDict(locals_)
