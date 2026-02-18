"""Pytest plugin and DSL runtime for YAML-based test specifications.

The `pytest_loco` package provides a declarative, YAML-based DSL for
describing test cases and integrates it seamlessly with pytest.

Key features:
- YAML-driven test specifications collected as pytest test items;
- schema validation and structured execution via a document parser;
- extensible checks, steps, and execution context;
- optional strict validation and controlled execution of dynamic code.

The package is designed to keep test specifications readable while
preserving pytest execution model and reporting capabilities.
"""
