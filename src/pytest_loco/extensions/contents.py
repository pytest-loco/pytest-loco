"""Declarative content types, encoders, decoders, and transformers.

This module defines high-level DSL abstractions for working with structured
content. It provides declarative definitions for:

- content encoders (serialization),
- content decoders (deserialization),
- optional transformation steps applied during decoding,
- logical content types combining encoder and decoder behavior.

All definitions are declarative and are compiled into runtime Pydantic models
derived from `BaseContent`. Execution logic is delegated to user-provided
callables bound as class-level runners.
"""

from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Union

from pydantic import Field, RootModel, create_model

from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.schema import BaseContent, ContentRunner

from .parameters import Attribute, ParametersMixin

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

if TYPE_CHECKING:
    from pytest_loco.values import RuntimeValue


class ContentEncoder(ParametersMixin, SchemaModel):
    """Declarative definition of a content encoder.

    A content encoder describes how a runtime value is serialized into
    a specific external representation (for example: JSON, YAML, text).

    The encoder itself is declarative and is compiled into a subclass
    of `BaseContent` used during execution.
    """

    encoder: ContentRunner = Field(
        title='Encoder function',
        description=(
            'Callable implementing the encoding logic. '
            'Receives the resolved source value and a dictionary of '
            'resolved parameters. Returns an encoded value.'
        ),
    )

    def build_format_field(self, format_name: str) -> 'Any':  # noqa: ANN401
        """Build discriminator field for the content format.

        Args:
            format_name: Identifier of the content format.

        Returns:
            Annotated literal type bound to the given format name.
        """
        return Annotated[
            Literal[format_name], Field(
                validation_alias='format',
                title='Content format type',
            ),
        ]

    def build_runner(self) -> tuple['Any', ContentRunner]:
        """Build runner definition for the generated content model.

        Returns:
            Tuple suitable for `create_model` assigning the encoder as a class-level runner.
        """
        return ClassVar[ContentRunner], staticmethod(self.encoder)

    def build_fields(self, format_name: str) -> dict[str, 'Any']:
        """Build field definitions for the encoder runtime model.

        Args:
            format_name: Identifier of the content format.

        Returns:
            Mapping of field names to Pydantic-compatible types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return {
            'format_type': self.build_format_field(format_name),
            'runner': self.build_runner(),
            **self.parameters.build(exclude={
                *BaseContent.model_fields.keys(),
                'format',
                'runner',
            }),
        }

    def build(self, format_name: str) -> type[RootModel[BaseContent]]:
        """Build a dynamic Pydantic model representing the encoder.

        Args:
            format_name: Identifier of the format.

        Returns:
            Dynamically created subclass of `BaseContent` with fields for parameters
            and the main encoded value, and runner set to `encoder`.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        base = create_model(f'{format_name}_Base_Encoder', __base__=BaseContent, **self.build_fields(format_name))

        #: Using RootModel for compatability.
        return create_model(f'{format_name}_Encoder', __base__=RootModel, root=Union[(base,)])  # noqa: UP007


class ContentTransformer(ParametersMixin, SchemaModel):
    """Declarative definition of a content transformer.

    A transformer wraps an existing `BaseContent` model and applies an
    additional transformation step to the decoded value.

    The transformer is identified by a discriminator field that also
    serves as the primary transformation input.
    """

    transformer: ContentRunner = Field(
        title='Transformer function',
        description=(
            'Callable implementing the transformation logic. '
            'Receives the decoded value and transformer-specific parameters.'
        ),
    )

    name: Variable = Field(
        title='Discriminator field name',
        description=(
            'Name of the discriminator field identifying the transformer. '
            'This field also holds the primary input value for transformation.'
        ),
    )

    field: Attribute = Field(
        title='Discriminator field schema',
        description=(
            'Schema describing the discriminator field type, constraints, '
            'and metadata. Serves as both identifier and primary input.'
        ),
    )

    def build_wrapper(self, base: type[BaseContent]) -> tuple['Any', ContentRunner]:
        """Wrap the base runner with transformer logic.

        Args:
            base: Base content model being wrapped.

        Returns:
            Tuple assigning a wrapped runner callable.
        """
        def wrapper(value: 'RuntimeValue',
                    params: 'Mapping[str, RuntimeValue]') -> 'RuntimeValue':
            """Apply base runner and transformer sequentially."""
            transformer_params = {
                key: params[key]
                for key in (self.name, *self.parameters.root.keys())
            }
            base_params = {
                key: value
                for key, value in params.items()
                if key not in transformer_params
            }

            return self.transformer(
                base.runner(value, base_params),
                transformer_params,
            )

        return ClassVar[ContentRunner], staticmethod(wrapper)

    def build_fields(self, base: type[BaseContent]) -> dict[str, 'Any']:
        """Build field definitions for the transformer model.

        Args:
            base: Base content model being wrapped.

        Returns:
            Mapping of field names to Pydantic-compatible types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return {
            self.name: self.field.build(field_name=self.name),
            'runner': self.build_wrapper(base),
            **self.parameters.build(exclude={
                *base.model_fields.keys(),
                self.name,
                'format',
                'runner',
            }),
        }

    def build(self, base: type[BaseContent]) -> type[BaseContent]:
        """Build a dynamic Pydantic model representing the transformer.

        Args:
            base: Base model of the decoder.

        Returns:
            Dynamically created subclass of `BaseContent` with fields for parameters
            and the main decode value, and runner set to `transformer`.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return create_model(
            f'{self.name}_{base.__name__}_Transformer',
            __base__=base,
            **self.build_fields(base),
        )


class ContentDecoder(ParametersMixin, SchemaModel):
    """Declarative definition of a content decoder.

    A content decoder describes how encoded data is deserialized into
    an internal representation. Decoders may optionally define a set
    of transformers applied after decoding.
    """

    decoder: ContentRunner = Field(
        title='Decoder function',
        description=(
            'Callable implementing decoding logic. '
            'Receives encoded data and returns decoded value.'
        ),
    )

    transformers: list[ContentTransformer] = Field(
        default_factory=list,
        title='Optional transformers',
        description=(
            'Optional list of transformers applied after decoding. '
            'At most one transformer may be selected in DSL usage.'
        ),
    )

    def build_format_field(self, format_name: str) -> 'Any':  # noqa: ANN401
        """Build Pydantic field type for the `format_type` field.

        Args:
            format_name: Identifier of the format.

        Returns:
            Literal type with the format name.
        """
        return Annotated[
            Literal[format_name], Field(
                validation_alias='format',
                title='Content format type',
            ),
        ]

    def build_runner(self) -> tuple['Any', ContentRunner]:
        """Build runner definition for the decoder model.

        Returns:
            Tuple suitable for `create_model` assigning the decoder as a class-level runner.
        """
        return ClassVar[ContentRunner], staticmethod(self.decoder)

    def build_fields(self, format_name: str) -> dict[str, 'Any']:
        """Build field definitions for the decoder base model.

        Args:
            format_name: Identifier of the content format.

        Returns:
            Mapping of field names to Pydantic-compatible types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return {
            'format_type': self.build_format_field(format_name),
            'runner': self.build_runner(),
            **self.parameters.build(exclude={
                *BaseContent.model_fields.keys(),
                'format',
                'runner',
            }),
        }

    def build(self, format_name: str) -> type[RootModel[BaseContent]]:
        """Build a dynamic Pydantic model representing the decoder.

        Args:
            format_name: Identifier of the format.

        Returns:
            Dynamically created subclass of `BaseContent` with fields for parameters
            and the main decoded value, and runner set to `decoder`.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        base = create_model(f'{format_name}_Base_Decoder', __base__=BaseContent, **self.build_fields(format_name))

        variants = [base]

        forbidden: set[str] = set()
        for transformer in self.transformers:
            aliases = transformer.field.aliases
            if transformer and forbidden.intersection(aliases):
                raise ValueError(f'aliases for transformer `{format_name}.{transformer.name}` is not unique in schema')
            if transformer.name in forbidden:
                raise ValueError(f'attribute `{format_name}.{transformer.name}` is not unique in schema')

            forbidden.add(transformer.name)
            forbidden.update(aliases)

            variants.append(transformer.build(base))

        return create_model(
            f'{format_name}_Decoder',
            __base__=RootModel,
            root=Union[tuple(variants)],  # noqa: UP007
        )


class ContentType(SchemaModel):
    """Declarative definition of a logical content type.

    A content type groups together encoder and decoder definitions
    under a single logical name. It describes both metadata and
    runtime behavior of structured content.
    """

    name: Variable = Field(
        title='Content type name',
        description='Unique identifier of the content type.',
    )

    encoder: ContentEncoder | None = Field(
        default=None,
        title='Encoder',
        description='Optional encoder definition for this content type.',
    )
    decoder: ContentDecoder | None = Field(
        default=None,
        title='Decoder',
        description='Optional decoder definition for this content type.',
    )

    def build_decoder(self) -> type[RootModel[BaseContent]] | None:
        """Create a runtime decoder model for this content type.

        If a decoder definition is provided, this method compiles it into
        a fully configured Pydantic model suitable for YAML deserialization
        via the `!load` instruction.

        Returns:
            A Pydantic model representing the decoder, or None if
            no decoder is defined for this content type.
        """
        if self.decoder:
            return self.decoder.build(self.name)

        return None

    def build_encoder(self) -> type[RootModel[BaseContent]] | None:
        """Create a runtime encoder model for this content type.

        If an encoder definition is provided, this method compiles it into
        a fully configured Pydantic model suitable for YAML serialization
        via the `!dump` instruction.

        Returns:
            A Pydantic model representing the encoder, or None if
            no encoder is defined for this content type.
        """
        if self.encoder:
            return self.encoder.build(self.name)

        return None
