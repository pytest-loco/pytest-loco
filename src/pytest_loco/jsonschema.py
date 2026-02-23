"""JSON Schema management."""

from functools import cache
from json import dumps
from typing import TYPE_CHECKING

from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from yaml import SafeLoader

from pytest_loco.core import DocumentParser

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic_core import core_schema as core


class SchemaGenerator(GenerateJsonSchema):
    """Custom JSON Schema generator for pytest-loco models.

    Overrides schema generation for callable runtime values. In the
    pytest-loco DSL, callables represent runtime-evaluated expressions,
    which do not have a fixed static type. For JSON Schema purposes,
    they are represented as unconstrained values.
    """

    @classmethod
    @cache
    def get_parser(cls) -> DocumentParser:
        """Return a cached pytest-loco document parser instance.

        Returns:
            Parser configured with SafeLoader and non-strict validation.
        """
        class ClearLoader(SafeLoader):
            pass

        return DocumentParser(ClearLoader, strict=False)

    @classmethod
    @cache
    def get_model(cls) -> 'type[BaseModel]':
        """Build and cache the root Pydantic model for the DSL.

        Returns:
            Generated document model.
        """
        return cls.get_parser().build()

    @classmethod
    @cache
    def make_schema(cls, indent: int | str | None = 4) -> str:
        """Generate the JSON Schema for pytest-loco documents.

        Args:
            indent: Indentation level used for JSON formatting.

        Returns:
            Serialized JSON Schema string.
        """
        model = cls.get_model()

        schema = {
            **model.model_json_schema(
                schema_generator=cls,
                union_format='primitive_type_array',
            ),
            'title': 'pytest-loco',
            'description': 'JSON Schema for pytest-loco DSL documents',
            '$schema': cls.schema_dialect,
        }

        return dumps(
            schema,
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
        )

    def callable_schema(self, schema: 'core.CallableSchema') -> JsonSchemaValue:  # noqa: ARG002
        """Generate JSON Schema for callable runtime values.

        Args:
            schema: Pydantic core schema describing a callable.

        Returns:
            A permissive JSON Schema fragment allowing arbitrary values
            to represent runtime-evaluated expressions.
        """
        return {'description': 'Runtime value'}

    def generate_inner(self, schema: 'core.CoreSchema') -> JsonSchemaValue:
        """Generates a JSON schema for a given core schema.

        Args:
            schema: The given core schema.

        Returns:
            The generated JSON schema.
        """
        json_schema = super().generate_inner(schema)

        if ref_id := json_schema.get('x-ref'):
            ref_def, ref_link = self.get_cache_defs_ref_schema(ref_id)
            self.definitions[ref_def] = json_schema
            return ref_link

        return json_schema
