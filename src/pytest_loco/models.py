"""Base Pydantic models for DSL elements.

This module defines the foundational model classes used by all DSL structures.
It enforces immutability and strict schema validation to guarantee that
parsed scenarios are deterministic, explicit, and safe to execute.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic import GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core.core_schema import CoreSchema


ALIASES_FIELD = 'x-aliases'
REQUIRED_FIELD = 'required'


class SchemaModel(BaseModel):
    """Base immutable model for all DSL elements.

    This class serves as the root for all Pydantic models representing
    DSL constructs such as steps, actions, expectations, and metadata.

    Design principles enforced by this model:
        - Immutability: DSL elements cannot be modified after creation.
          This ensures deterministic execution and prevents side effects
          during scenario processing.
        - Strict schema validation: unknown or extra fields are rejected
          to avoid silent errors caused by typos or invalid DSL extensions.

    All DSL models must inherit from this class.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
        extra='forbid',
    )

    @classmethod
    def _update_object(cls, schema: 'JsonSchemaValue') -> 'JsonSchemaValue | None':
        """Expand object JSON schema with alias-aware variants.

        This method inspects a JSON schema generated for a Pydantic model and
        detects object properties that declare alternative names via the
        `x-aliases` extension key.

        Args:
            schema: A JSON schema dictionary.

        Returns:
            A modified JSON schema containing a definition with all
            alias variants if alias definitions are present. Returns `None`
            if no alias expansion is required or if the schema is not an object.
        """
        properties = schema.get('properties', {})
        if schema.get('type') != 'object' or not properties:
            return None

        aliases = {
            field_name: sorted({
                field_name,
                *field_schema[ALIASES_FIELD],
            })
            for field_name, field_schema in properties.items()
            if ALIASES_FIELD in field_schema
        }
        if not aliases:
            return None

        requirements = []
        required = set(schema.get(REQUIRED_FIELD, ()))

        for field_name, field_aliases in aliases.items():
            for alias in field_aliases:
                properties[alias] = properties[field_name]
                if field_name in required:
                    requirements.append(cls._alias_requirements(field_aliases, alias))
            if field_name in required:
                required.discard(field_name)

        return {
            **schema,
            'required': sorted(required),
            'oneOf': [
                *schema.get('oneOf', ()),
                *requirements,
            ],
        }

    @staticmethod
    def _alias_requirements(aliases: list[str], alias: str) -> 'JsonSchemaValue':
        """Iterate over generated alias requrements.

        Args:
            aliases: A list of aliases available for field.
            alias: The current alias.

        Returns:
            A generated JSON schema containing a definition with
            alias and its exlusions list.
        """
        index = aliases.index(alias)

        return {
            REQUIRED_FIELD: [alias],
            'not': {'anyOf': [
                {REQUIRED_FIELD: [value]}
                for value in aliases[:index] + aliases[index + 1:]
            ]},
        }

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: 'CoreSchema',
                                     handler: 'GetJsonSchemaHandler') -> 'JsonSchemaValue':
        """Hook into generating the model's JSON schema with aliases.

        Args:
            core_schema: A `pydantic-core` CoreSchema.
            handler: Call into Pydantic's internal JSON schema generation.

        Returns:
            A JSON schema, as a Python object.
        """
        schema = super().__get_pydantic_json_schema__(core_schema, handler)
        if update := cls._update_object(schema):
            return update

        return schema

class DescribedMixin(SchemaModel):
    """Mixin providing element self-documentation.

    Extends the base schema model with optional metadata fields intended
    for documentation, reporting, and user interfaces.

    The fields defined in this model do not affect execution semantics
    and are used purely for descriptive purposes.
    """

    title: str | None = Field(
        default=None,
        title='Title',
        description='Short human-readable title of the DSL element. ',
        json_schema_extra={
            'x-ref': 'DescribedModelTitle',
        },
    )

    description: str | None = Field(
        default=None,
        title='Description',
        description=(
            'Detailed human-readable description of the DSL element.'
        ),
        json_schema_extra={
            'x-ref': 'DescribedModelDescription',
        },
    )


class SettingsModel(BaseSettings):
    """Base immutable model for DSL runtime settings.

    This class serves as the root for all settings models responsible for
    resolving runtime configuration (for example, environment variables,
    CI-provided values, or local overrides).

    Design principles enforced by this model:
        - Immutability: resolved settings cannot be modified after creation.
          This guarantees consistent behavior during scenario execution.
        - Tolerant schema handling: unknown or extra fields are ignored.
          This allows the surrounding environment to contain unrelated
          variables without breaking DSL configuration resolution.

    All DSL runtime settings models must inherit from this class.
    """

    model_config =  SettingsConfigDict(
        frozen=True,
        extra='ignore',
    )
