"""Base action definitions for the DSL.

Defines the foundational schema for executable DSL actions. An action represents
a single scenario step that performs an operation, may produce result values,
and can contribute data to the execution context.

Actions are executed by the scenario engine via a bound runner callable. Input
parameters and local context variables are resolved before execution. The runner
returns a result mapping that is stored under a configured output variable and
may be selectively exported for use by subsequent steps.

This module is declarative and does not implement execution orchestration or
side-effect handling. Concrete action behavior is provided by external runners
and plugins.
"""

from collections.abc import Callable, Mapping
from typing import ClassVar, Literal

from pydantic import Field, FilePath, RootModel

from pytest_loco.context import ContextDict
from pytest_loco.models import DescribedMixin, SchemaModel
from pytest_loco.names import Action, Variable  # noqa: TC001
from pytest_loco.values import Deferred, RuntimeValue, Value, normalize

from .checks import BaseCheck  # noqa: TC001
from .contexts import ContextMixin

#: The runner receives input parameters and returns a dictionary
#: of produced values. The returned values are not automatically
#: injected into the execution context and must be explicitly
#: exported if they are intended for later use.
type ActionRunner = Callable[[Mapping[str, RuntimeValue]], RuntimeValue]


class BaseAction(ContextMixin, DescribedMixin, SchemaModel):
    """Base class for executable actions.

    Represents a concrete executable step that performs an operation
    with observable side effects or produces result values.

    The actual execution logic is delegated to a class-level runner
    callable. Actions may declare expectations and export selected
    values into the execution context.
    """

    #: Internal specification marker. Always `step` for executable actions.
    spec: Literal['step'] = 'step'
    #: Action identifier resolved by the execution engine..
    action: Action

    #: Callable implementing the action logic.
    runner: ClassVar[ActionRunner]

    expect: list[RootModel[BaseCheck]] = Field(
        default_factory=list,
        title='Action expectations',
        description=(
            'List of checks that must pass after the action execution.\n'
            'Each check validates some aspect of the action result or '
            'side effects. All expectations are evaluated to determine '
            'the success or failure of the step.'
        ),
    )

    output: Variable = Field(
        default='result',
        title='Result variable',
        description=(
            'Name of the variable under which the action result '
            'context will be stored.\n'
            'The stored value may later be referenced '
            'or selectively exported into the execution context.'
        ),
        json_schema_extra={
            'x-ref': 'ActionOutput',
        },
    )

    export: dict[Variable, Deferred[Value]] = Field(
        default_factory=dict,
        title='Exported variables',
        description=(
            'Mapping of variable names to values derived from '
            'the action result.\n'
            'Exported variables are merged into the execution '
            'context and become available to subsequent steps.'
        ),
        json_schema_extra={
            'x-ref': 'ActionExports',
        },
    )

    def __call__(self, context: dict[str, Value]) -> dict[str, Value]:
        """Execute the action.

        Resolves local context variables, executes the action runner,
        and stores the produced result under the configured output name.

        Args:
            context: Current execution context.

        Returns:
            A mapping containing a single entry with the action result
            context stored under the configured output variable name.
        """
        locals_ = ContextDict(
            self.resolve_context(context),
        )

        result = type(self).runner(
            locals_.resolve(self.model_dump(
                exclude={
                    'spec',
                    'action',
                    'context',
                    'expect',
                    'export',
                },
            )),
        )

        return {
            self.output: normalize(result),
        }


class IncludeAction(BaseAction):
    """DSL action for including and executing external template files.

    The `include` action loads a DSL template from an external file,
    parses it using the active DSL parser, and executes its contents
    within the current execution context.

    The included template is executed as an isolated test plan, but
    inherits the caller's context by resolving parameters. Any values
    exported by the template are merged back into the current context.
    """

    spec: Literal['step'] = 'step'
    action: Literal['include'] = 'include'

    filepath: FilePath = Field(
        validation_alias='file',
        title='Template file path',
        description=(
            'Path to a DSL template file to include.\n'
            'The file must exist, be readable, and contain a valid '
            'DSL template definition. The template will be parsed '
            'and executed at runtime.'
        ),
    )

    def __call__(self, context: dict[str, Value]) -> dict[str, Value]:
        """Execute the action.

        Resolves local context variables and return it as is.

        Args:
            context: Current execution context.

        Returns:
            A mapping containing a entries of the action context.
        """
        return self.resolve_context(context, isolate=True)
