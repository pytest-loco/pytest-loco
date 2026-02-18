"""Declarative schema utilities for dynamic model construction.

This module provides primitives for defining declarative schemas that
can be compiled into Pydantic-compatible models at runtime.

It is primarily used to describe extension parameters, attributes, and
structured inputs in the DSL, enabling plugin-driven and data-driven
schema composition without static model definitions.
"""

from functools import partial  # noqa: I001
from types import GenericAlias, UnionType
from typing import Annotated, Any, Self, TypeAliasType
from typing import _BaseGenericAlias  # type: ignore[attr-defined]

from pydantic import AliasChoices, Field, RootModel, model_validator

from pytest_loco.models import DescribedMixin, SchemaModel
from pytest_loco.names import Variable
from pytest_loco.values import Deferred, Value

#: Using fragile construct and should be considered a temporary workaround.
#: It relies on private API and is intended only for the transition
#: period until the typing ecosystem consistently unifies these types
type BaseType = type | GenericAlias | TypeAliasType | UnionType | _BaseGenericAlias


class Attribute(DescribedMixin, SchemaModel):
    """Declarative attribute definition for dynamic schema construction.

    Represents a single attribute (field) definition that can be compiled
    into a Pydantic-compatible annotated type. Attributes describe both
    the structural type of a value and its semantic metadata, such as
    title, description, aliases, defaults, and validation constraints.
    """

    base: BaseType = Field(
        default=Deferred,
        title='Base type',
        description=(
            'Underlying Python type of the attribute value. '
            'This type is used as the primary runtime and validation type '
            'when constructing the schema.'
        ),
    )

    aliases: list[Variable] = Field(
        default_factory=list,
        title='Attribute aliases',
        description=(
            'Alternative names that may be used to reference this attribute '
            'in input data. Aliases are resolved transparently during parsing.'
        ),
    )

    examples: list[Value] | None = Field(
        default=None,
        min_length=1,
        title='Example values',
        description=(
            'Representative example values for the attribute. '
            'Used for documentation, schema introspection, and tooling.'
        ),
    )

    default: Value = Field(
        default=None,
        title='Default value',
        description=(
            'Default value of the attribute. '
            'Used when the attribute is optional and not explicitly provided.'
        ),
    )

    required: bool = Field(
        default=False,
        title='Required flag',
        description=(
            'Indicates whether the attribute must be explicitly provided. '
            'Required attributes must not define a default value.'
        ),
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

        raise ValueError('specified both a default value and a required constraint')

    @staticmethod
    def _extend_schema_aliases(schema: dict[str, Any],
                               aliases: AliasChoices | None = None) -> None:
        """Extends schema aliases."""
        if not aliases:
            return None

        schema['x-aliases'] = [
            alias
            for alias in aliases.choices
            if isinstance(alias, str)
        ]

    def build(self, *, field_name: str | None = None) -> Any:  # noqa: ANN401
        """Build an annotated field type for this attribute.

        Constructs a Pydantic-compatible `Annotated` type that encodes
        the attribute base type together with its validation rules,
        metadata, aliases, and default/required behavior.

        Args:
            field_name: Optional canonical field name used to extend aliases.

        Returns:
            An `Annotated` type representing the configured attribute.
        """
        aliases = None

        if self.aliases:
            aliases = (
                AliasChoices(field_name, *self.aliases)
                if field_name
                else AliasChoices(*self.aliases)
            )

        field_type: BaseType = Deferred | None
        if self.base and self.base not in (Deferred, Value):
            field_type = self.base | Deferred | None

        return Annotated[
            field_type, Field(
                default=... if self.required else self.default,
                validation_alias=aliases,
                title=self.title,
                description=self.description,
                examples=self.examples,
                json_schema_extra=partial(
                    self._extend_schema_aliases,
                    aliases=aliases,
                ),
            ),
        ]


class Schema(RootModel[dict[Variable, Attribute]]):
    """Declarative schema composed of named attributes.

    Represents a collection of attribute definitions that together form
    a logical schema. The schema can be compiled into a mapping suitable
    for dynamic Pydantic model creation.
    """

    root: dict[Variable, Attribute] = Field(
        default_factory=dict,
        title='Schema attributes',
        description='Mapping of attribute names to their declarative definitions.',
    )

    def build(self, exclude: set[str] | None = None) -> dict[str, type[Any]]:
        """Compile the schema into Pydantic-compatible field definitions.

        Builds annotated field types for each attribute and validates
        uniqueness of attribute names and aliases.

        Args:
            exclude: Fields excluded from the schema (forbidden).
                For example, base-model builtins fields.

        Returns:
            A mapping of attribute names to Pydantic-compatible annotated types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        if not exclude:
            exclude = set()

        schema = {}
        for name, attribute in self.root.items():
            if attribute.aliases and exclude.intersection(attribute.aliases):
                raise ValueError(f'aliases for attribute `{name}` is not unique in schema')
            if name in exclude:
                raise ValueError(f'attribute `{name}` is not unique in schema')

            exclude.add(name)
            exclude.update(attribute.aliases)

            schema[name] = attribute.build(field_name=name)

        return schema


class ParametersMixin(SchemaModel):
    """Mixin providing declarative parameter schema support.

    Allows an extension or DSL element to declare an additional
    parameter schema that can be compiled into a runtime model.

    This mixin is purely declarative and does not define how parameters
    are applied or resolved.
    """

    parameters: Schema = Field(
        default_factory=Schema,
        title='Extension parameters schema',
        description=(
            'Optional declarative schema defining additional parameters '
            'accepted by this extension. These parameters are validated '
            'and passed to the underlying runtime callable when present.'
        ),
    )
