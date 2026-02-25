"""Definitions of input parameters for DSL scenarios and runtime configuration.

This module provides declarative models for describing input parameters
(environment variables and scenario parameters) and utilities to compile
these definitions into concrete Pydantic models used at runtime.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import Field, RootModel, SecretStr, ValidationError, create_model, model_validator

from pytest_loco.errors import DSLRuntimeError
from pytest_loco.models import SchemaModel, SettingsModel
from pytest_loco.names import VARIABLE_PATTERN
from pytest_loco.values import Value  # noqa: TC001

type TypeName = Literal['str', 'int', 'float', 'bool', 'object', 'list']


class InputDefinition(SchemaModel):
    """Definition of a single input parameter.

    Describes a named input that can be provided by a user, environment,
    or calling scenario. An input may be required or optional, may define
    a default value, and can be marked as secret to prevent accidental
    exposure in logs, reports, or error messages.
    """

    name: str = Field(
        pattern=VARIABLE_PATTERN,
        title='Input name',
        description=(
            'Unique identifier of the input parameter.\n'
            'Used to reference the input value in expressions, templates, and '
            'variable lookups. Must start with a letter and contain only letters, '
            'digits, and underscores.'
        ),
        json_schema_extra={
            'x-ref': 'InputName',
        },
    )
    description: str | None = Field(
        default=None,
        title='Input description',
        description='Human-readable description of the input parameter.',
        json_schema_extra={
            'x-ref': 'InputDescription',
        },
    )

    value_type: TypeName = Field(
        default='str',
        validation_alias='type',
        title='Input type',
        description='Data type of the input parameter.',
        json_schema_extra={
            'x-ref': 'InputType',
        },
    )

    default: Value = Field(
        default=None,
        title='Default value',
        description=(
            'Default value of the input parameter.\n'
            'Used when the input is not explicitly provided. '
            'Must not be specified for required inputs.'
        ),
        json_schema_extra={
            'x-ref': 'InputDefaultValue',
        },
    )
    required: bool = Field(
        default=False,
        title='Required flag',
        description=(
            'Indicates whether the input parameter must be explicitly provided '
            'by the user or calling scenario.\n'
            'Required inputs must not define a default value.'
        ),
        json_schema_extra={
            'x-ref': 'InputRequiredFlag',
        },
    )

    secret: bool = Field(
        default=False,
        title='Secret flag',
        description=(
            'Marks the input parameter as sensitive.\n'
            'Secret inputs are masked in logs, reports, and error messages.'
        ),
        json_schema_extra={
            'x-ref': 'InputSecretFlag',
        },
    )

    @model_validator(mode='after')
    def check_default_required(self) -> Self:
        """Check combination of `required` and `default`.

        Combination of `required` and `default` is redundant or logically conflicting.
        The primary use case for a `default` is to provide a fallback for an optional field.
        If a value truly must be explicitly set by the user or client, it should be marked
        as `required` without a default value.

        Returns:
            Self.

        Raises:
            ValueError: If specified both a `default` value and a `required` constraint.
        """
        if not self.required or self.default is None:
            return self

        raise ValueError('Specified both a default value and a required constraint')

    @model_validator(mode='after')
    def check_secret_type(self) -> Self:
        """Validate compatibility of `secret` flag and input type.

        Secret inputs are currently supported only for string values, as they
        rely on masking mechanisms specific to textual data.

        Returns:
            Self.

        Raises:
            ValueError: If `secret` is specified for a non-string type.
        """
        if not self.secret or self.value_type == 'str':
            return self

        raise ValueError('Specified secret on non-string type')


class BaseInputsDefinition(RootModel[list[InputDefinition]]):
    """Base collection of input definitions.

    Represents an ordered list of input definitions that can be compiled
    into a concrete Pydantic model for runtime validation.
    """

    root: list[InputDefinition] = Field(
        default_factory=list,
        min_length=1,
        title='Input definitions',
        description='List of input parameter definitions.',
    )

    @staticmethod
    def build_field_type(definition: InputDefinition) -> type[Any]:  # noqa: PLR0911
        """Resolve Python type for an input definition.

        Args:
            definition: Input definition to resolve.

        Returns:
            A Python type corresponding to the input definition.

        Raises:
            ValueError: If type is not supported.
        """
        match definition.value_type:
            case 'str':
                if definition.secret:
                    return SecretStr
                return str
            case 'int':
                return int
            case 'float':
                return float
            case 'bool':
                return bool
            case 'object':
                return dict
            case 'list':
                return list

        raise ValueError('Unsupported type')  # pragma: no cover

    def build_fields(self) -> dict[str, Any]:
        """Build Pydantic field definitions from input definitions.

        Returns:
            A mapping suitable for passing to `pydantic.create_model`,
            where keys are field names and values are annotated field types.
        """
        fields = {}
        for definition in self.root:
            if definition.name in fields:  # pragma: no cover
                # NOTE: Shadowing input definitions is currently undefined behavior.
                # This should be turned into a validation error in future revisions
                pass
            field_type = self.build_field_type(definition)
            field_info = Field(
                default=... if definition.required else definition.default,
                description=definition.description,
                title=definition.name,
            )
            fields[definition.name] = Annotated[field_type | None, field_info]

        return fields


class EnvironmentDefinition(BaseInputsDefinition):
    """Definition of environment-based input parameters.

    Represents inputs expected to be resolved from environment variables
    or other external configuration sources.
    """

    def build(self) -> type[SettingsModel]:
        """Create a Pydantic settings model from environment definitions.

        Returns:
            A dynamically created `SettingsModel` subclass representing the
            environment configuration schema.
        """
        return create_model('EnvironmentSettings', __base__=SettingsModel, **self.build_fields())


class ParametersDefinition(BaseInputsDefinition):
    """Definition of scenario parameters.

    Represents inputs expected to be provided explicitly when invoking
    a scenario or reusable template.
    """

    def build(self) -> type[SchemaModel]:
        """Create a Pydantic model from parameter definitions.

        Returns:
            A dynamically created `SchemaModel` subclass representing the
            scenario parameters schema.
        """
        return create_model('Parameters', __base__=SchemaModel, **self.build_fields())


class EnvironmentMixin(SchemaModel):
    """Mixin providing environment resolving for DSL execution.

    This mixin is responsible for transforming a declarative
    `EnvironmentDefinition` into a validated runtime environment
    dictionary that can be injected into the execution context.

    The environment is always exposed under the `env` key and is
    derived from a dynamically generated Pydantic settings model.
    """

    environment: EnvironmentDefinition = Field(
        default_factory=EnvironmentDefinition,
        validation_alias='envs',
        title='Environment definition',
        description=(
            'Definition of environment-based inputs required by the template.\n'
            'Describes external configuration values, such as environment '
            'variables or secrets, that must be provided at execution time.'
        ),
    )

    def resolve_environment(self) -> dict[str, Value]:
        """Resolve execution environment from an environment definition.

        Returns:
            A dictionary with validated environment data, or an empty
            dictionary if no definition was supplied.

        Raises:
            DSLSchemaError: If the environment definition exists but
                fails validation or cannot be instantiated.
        """
        if not self.environment or not self.environment.root:
            return {}

        environment_model = self.environment.build()
        try:
            environment = environment_model()
        except ValidationError as base:
            raise DSLRuntimeError('Can not get required environment params') from base

        return environment.model_dump()


class ParametersMixin(SchemaModel):
    """Mixin providing parameters resolving for DSL execution.

    This mixin is responsible for transforming a declarative
    `ParametersDefinition` into a validated runtime parameters
    dictionary that can be injected into the execution context.

    The parameters is always exposed under the `params` key and is
    derived from a dynamically generated Pydantic settings model.
    """

    params: ParametersDefinition = Field(
        default_factory=ParametersDefinition,
        title='Parameters definition',
        description=(
            'Definition of parameters that must or may be provided when the '
            'template is invoked. Parameters define the input contract of the '
            'template and control its data-driven behavior.'
        ),
    )

    def resolve_parameters(self, values: dict[str, Value]) -> dict[str, Value]:
        """Resolve execution parameters from an parameters definition.

        Args:
            values: Raw parameters context.

        Returns:
            A dictionary of validated parameter values. If no definition or
            context is provided, an empty dictionary is returned.

        Raises:
            DSLRuntimeError: If parameters validation fails.
        """
        if not self.params or not self.params.root:
            return {}

        try:
            return self.params.build().model_validate(values).model_dump()
        except ValidationError as base:
            raise DSLRuntimeError('Can not get required params') from base
