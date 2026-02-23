"""DSL models for parameters, test cases, and templates.

This module defines the core declarative elements of the DSL for
test automation. Each element supports declarative context,
environment variables, parameter resolution, and metadata to drive
scenario execution.
"""

from typing import Literal

from pydantic import Field

from pytest_loco.context import ContextDict
from pytest_loco.models import DescribedMixin, SchemaModel
from pytest_loco.names import VARIABLE_PATTERN, Variable
from pytest_loco.values import Value  # noqa: TC001

from .contexts import ContextMixin
from .inputs import EnvironmentMixin, ParametersMixin


class Parameter(DescribedMixin, SchemaModel):
    """Parameter definition for data-driven execution.

    Describes a single named parameter and its possible values.
    Parameters are used to drive combinatorial execution of scenarios
    or templates by providing multiple input values.

    Each value represents either a concrete value.
    """

    name: str = Field(
        pattern=VARIABLE_PATTERN,
        title='Parameter name',
        description=(
            'Identifier of the parameter.\n'
            'The name is used to reference the parameter value '
            'in expressions, templates, and step definitions.'
        ),
        json_schema_extra={
            'x-ref': 'ParameterName',
        },
    )

    values: list[Value] = Field(
        default_factory=list,
        min_length=1,
        title='Parameter values',
        description='List of possible values for the parameter.',
    )


class Case(ContextMixin, EnvironmentMixin, DescribedMixin, SchemaModel):
    """Executable test case definition.

    Represents a concrete, executable test case in the DSL.
    A case defines its execution context, environment requirements,
    optional parameters, and metadata used for reporting and integration.

    A case is the primary unit of execution. It may be executed directly
    or expanded and orchestrated by higher-level processors.
    """

    #: Internal specification marker. Always `case` for executable case.
    spec: Literal['case']

    metadata: dict[Variable, Value] = Field(
        default_factory=dict,
        title='Case metadata',
        description=(
            'Additional metadata associated with the test case.'
        ),
    )

    params: list[Parameter] = Field(
        default_factory=list,
        title='Case parameters',
        description=(
            'Definition of parameters used to drive data-driven '
            'execution of the test case.\n'
            'Parameters define the input space and control '
            'combinatorial execution of the case.'
        ),
    )

    def __call__(self, params: dict[str, Value]) -> dict[str, Value]:
        """Resolve the execution context for the case.

        Args:
            params: Parameter values to apply for this execution.

        Returns:
            Mapping of context values including parameters and environment variables.
        """
        _locals = ContextDict({
            'params': params,
            'meta': self.metadata,
            'envs': self.resolve_environment(),
        })

        return {
            **_locals.resolve(self.context),
            **_locals,
        }


class Template(ContextMixin, EnvironmentMixin, DescribedMixin, ParametersMixin, SchemaModel):
    """Reusable template definition.

    Represents a reusable, non-executable building block of the DSL.
    A template defines shared context variables, environment requirements,
    and parameter schema that can be reused by executable scenarios.

    Templates are not executed directly. Instead, they are invoked or
    instantiated by other DSL constructs, contributing validated context,
    parameters, and environment data to the execution flow.
    """

    #: Internal specification marker. Always `template` for executable template.
    spec: Literal['template']

    def __call__(self, params: dict[str, Value]) -> dict[str, Value]:
        """Resolve the context for the template.

        Args:
            params: Parameter values to apply when instantiating the template.

        Returns:
            Mapping of context values including parameters and environment variables.
        """
        _locals = ContextDict({
            'params': self.resolve_parameters(params),
            'envs': self.resolve_environment(),
        })

        return {
            **_locals.resolve(self.context),
            **_locals,
        }
