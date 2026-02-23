"""Declarative DSL plugin definition.

This module defines the top-level declarative container used to describe
DSL extensions provided by a pytest-loco plugin.

A plugin aggregates multiple independent DSL elements, including:
- actors (actions with execution logic),
- checkers (value validation rules),
- content types (encoding, decoding, transformation),
- and custom YAML instructions.

The plugin model itself is purely declarative. It contains no execution
logic and is consumed by the plugin loader during initialization to
register all provided DSL extensions in a structured and validated form.
"""

from pydantic import Field

from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.schema import YAMLLoader, YAMLNode

from .actors import Actor
from .checkers import Checker
from .contents import ContentDecoder, ContentEncoder, ContentTransformer, ContentType
from .instructions import Instruction
from .parameters import Attribute, Schema

__all__ = (
    'Actor',
    'Attribute',
    'Checker',
    'ContentDecoder',
    'ContentEncoder',
    'ContentTransformer',
    'ContentType',
    'Instruction',
    'Plugin',
    'Schema',
    'YAMLLoader',
    'YAMLNode',
)


class Plugin(SchemaModel):
    """Declarative container for DSL plugin extensions.

    A plugin represents a logical namespace that groups together all DSL
    elements contributed by an extension module.

    Plugin instances are declarative descriptions only. They do not
    execute logic themselves, but are consumed by the plugin loader to:
    - register actions, checks, content handlers, and instructions;
    - validate schema consistency;
    - detect naming conflicts and compatibility issues.

    All contained elements are optional, allowing plugins to provide
    partial DSL extensions.
    """

    name: Variable = Field(
        title='Plugin namespace',
        description=(
            'Logical namespace of the plugin. '
            'Used for identification, diagnostics, and conflict detection. '
            'Typically corresponds to the plugin package or domain name.'
        ),
    )

    version: int = Field(
        default=1,
        title='DSL version',
        description=(
            'Version of the plugin DSL contract. '
            'Used to track compatibility between plugins and the DSL runtime. '
            'This is not a semantic version of the plugin implementation.'
        ),
    )

    actors: list[Actor] = Field(
        default_factory=list,
        title='Actors',
        description=(
            'Declarative action definitions provided by the plugin. '
            'Each actor describes an executable DSL action and its parameters.'
        ),
    )

    checkers: list[Checker] = Field(
        default_factory=list,
        title='Checkers',
        description=(
            'Declarative checker definitions provided by the plugin. '
            'Checkers define reusable validation rules applied to values '
            'during execution.'
        ),
    )

    content_types: list[ContentType] = Field(
        default_factory=list,
        title='Content types',
        description=(
            'Custom content type definitions, including encoders, decoders, '
            'and transformers used for value serialization and conversion.'
        ),
    )

    instructions: list[Instruction] = Field(
        default_factory=list,
        title='Instructions',
        description=(
            'Custom YAML instruction definitions provided by the plugin. '
            'Instructions extend YAML syntax with domain-specific constructs.'
        ),
    )
