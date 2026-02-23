"""Declarative action definitions and dynamic action model construction.

This module defines the DSL abstraction for executable actions, referred to as
*actors*. Actors are declarative objects that describe how runtime action models
are constructed rather than being executed directly.

Actors are compiled into Pydantic models derived from `BaseAction`. These
generated models are used by the scenario execution engine to perform concrete
steps, validate input parameters, manage execution context, and evaluate
expectations.

The module is intentionally declarative and does not implement execution
orchestration. All side effects and runtime behavior are delegated to the
bound actor callables and the execution engine.
"""

from typing import Any, ClassVar, Literal

from pydantic import Field, create_model

from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.schema import ActionRunner, BaseAction

from .parameters import ParametersMixin


class Actor(ParametersMixin, SchemaModel):
    """Declarative action definition.

    Represents a reusable declarative description of an executable action.
    An actor is not executed directly; instead, it is compiled into a
    Pydantic model derived from `BaseAction`.

    An actor defines:
    - an action discriminator name,
    - a callable implementing the action logic,
    - an optional parameter schema influencing execution behavior.

    The generated action model is used by the scenario execution engine
    to perform concrete runtime steps.
    """

    actor: ActionRunner = Field(
        title='Actor function',
        description=(
            'Callable implementing the action execution logic.\n'
            'Receives a dictionary of resolved input parameters and returns '
            'a dictionary of produced values.'
        ),
    )

    name: Variable = Field(
        title='Action discriminator name',
        description=(
            'Value of the action discriminator.\n'
            'Used to populate the `action` field in the generated action model '
            'and to uniquely identify the action type in the DSL.'
        ),
    )

    def build_action_field(self, namespace: str | None = None) -> Any:  # noqa: ANN401
        """Build Pydantic field type for the `action` field.

        Args:
            namespace: Optional namespace to prefix the action name.

        Returns:
            Literal type with the action name.
        """
        if namespace:
            return Literal[f'{namespace}.{self.name}']

        return Literal[self.name]

    def build_runner(self) -> tuple[Any, ActionRunner]:
        """Build runner definition for the generated Pydantic model.

        The runner is attached to the generated model as a class variable
        and is used by `BaseAction` to execute the action logic.

        Returns:
            A tuple containing `ClassVar[ActionRunner]` and the actor callable.
        """
        return ClassVar[ActionRunner], staticmethod(self.actor)

    def build_fields(self, namespace: str | None = None) -> dict[str, Any]:
        """Build field definitions for the generated action model.

        Internal fields defined by `BaseAction` are explicitly excluded
        to avoid conflicts and accidental overrides.

        Args:
            namespace: Optional namespace prefix for the action discriminator.

        Returns:
            A mapping of field names to Pydantic-compatible annotated types.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return {
            'action': self.build_action_field(namespace),
            'runner': self.build_runner(),
            **self.parameters.build(exclude={
                *BaseAction.model_fields.keys(),
                self.name,
                'runner',
                'vars',
            }),
        }

    def build(self, namespace: str | None = None) -> type[BaseAction]:
        """Build a dynamic Pydantic model representing this action.

        Args:
            namespace: Optional namespace prefix for the action discriminator.

        Returns:
            Dynamically created subclass of `BaseAction`.

        Raises:
            ValueError: If attribute names or aliases are not unique.
        """
        return create_model(f'{self.name}_Action', __base__=BaseAction, **self.build_fields(namespace))
