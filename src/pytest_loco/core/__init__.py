"""Core DSL runtime and YAML parser integration.

This module defines the core infrastructure for building and parsing
executable DSL documents.

It provides:
- dynamic composition of Pydantic schemas for runtime validation;
- safe loading and registration of builtin and plugin-based extensions;
- integration of all DSL extensions into a YAML loader.

The primary public entry point is `DocumentParser`, which prepares
a YAML loader, attaches all required constructors, and parses YAML
document streams into validated executable DSL models.
"""

from .parser import DocumentParser, Header, Step

__all__ = (
    'DocumentParser',
    'Header',
    'Step',
)
