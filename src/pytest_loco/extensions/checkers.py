"""Declarative checker definitions and dynamic model construction.

This module defines a high-level DSL abstraction for reusable value checkers.
Checkers are declarative objects that describe:
- how a value should be validated or checked,
- which parameters the check accepts,
- and how to dynamically construct a runtime Pydantic model
  compatible with `BaseCheck`.

The resulting models are used during execution to validate values
and report check results in a structured and extensible way.
"""

from typing import Any, ClassVar

from pydantic import Field, create_model

from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.schema import BaseCheck, CheckRunner

from .parameters import Attribute, ParametersMixin


class Checker(ParametersMixin, SchemaModel):
    """Declarative checker definition.

    Represents a reusable logical check that can be dynamically compiled
    into a Pydantic model derived from `BaseCheck`.

    A checker defines:
    - a discriminator field identifying the check and holding
      the primary checked value,
    - a callable implementing the check logic,
    - an optional parameter schema influencing check behavior.

    Checker instances are declarative and are compiled into runtime
    check models used during execution.
    """

    checker: CheckRunner = Field(
        title='Checker function',
        description=(
            'Callable implementing the check logic. '
            'Receives the value being checked and a dictionary of resolved '
            'parameter values. Must return True if the check passes, '
            'or False otherwise.'
        ),
    )

    name: Variable = Field(
        title='Discriminator field name',
        description=(
            'Name of the discriminator field for the generated check model. '
            'This field uniquely identifies the check type and also holds '
            'the primary value being validated.'
        ),
    )

    field: Attribute = Field(
        title='Discriminator field schema',
        description=(
            'Declarative schema describing the type, constraints, and metadata '
            'of the discriminator field. The discriminator field serves as '
            'both the check identifier and the primary input value.'
        ),
    )

    def build_runner(self) -> tuple[Any, CheckRunner]:
        """Build runner definition for the generated Pydantic model.

        The runner is attached to the generated model as a class variable
        and is used by `BaseCheck` to execute the check logic.

        Returns:
            A tuple containing `ClassVar[CheckRunner]` and the checker callable.
        """
        return ClassVar[CheckRunner], staticmethod(self.checker)

    def build_fields(self) -> dict[str, Any]:
        """Build field definitions for the generated discriminator-based model.

        Internal fields used by `BaseCheck` and the checker infrastructure
        are explicitly excluded to prevent naming conflicts.

        Returns:
            A mapping of field names to Pydantic-compatible annotated types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return {
            self.name: self.field.build(field_name=self.name),
            'runner': self.build_runner(),
            **self.parameters.build(exclude={
                *BaseCheck.model_fields.keys(),
                self.name,
                'runner',
            }),
        }

    def build(self) -> type[BaseCheck]:
        """Build a dynamic Pydantic model representing this discriminator check.

        Returns:
            Dynamically created subclass of `BaseCheck`.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return create_model(f'{self.name}_Check', __base__=BaseCheck, **self.build_fields())
