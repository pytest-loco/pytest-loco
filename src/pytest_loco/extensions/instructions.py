"""Declarative instruction definitions and YAML integration.

This module defines a high-level DSL abstraction for custom YAML
instructions used by pytest-loco.

An instruction represents:
- a symbolic YAML tag name,
- a constructor function that converts a YAML node into a runtime value,
- and a dynamically generated runtime model compatible with `BaseInstruction`.

Instruction objects are declarative and describe how YAML should be
interpreted, but they do not perform execution themselves. During schema
compilation, each instruction is converted into a concrete Pydantic model
that binds the constructor as a runner, enabling structured and extensible
YAML-driven execution.
"""

from typing import Any, ClassVar, Literal

from pydantic import Field, create_model

from pytest_loco.models import SchemaModel
from pytest_loco.names import Variable  # noqa: TC001
from pytest_loco.schema import BaseInstruction, InstructionRunner


class Instruction(SchemaModel):
    """Declarative instruction definition.

    Defines a named YAML instruction and its constructor, which can be
    compiled into a runtime instruction model compatible with PyYAML.
    """

    name: Variable = Field(
        title='Instruction name',
        description='Symbolic name of the YAML tag.',
    )

    node_type: Literal['scalar', 'mapping'] = Field(
        default='scalar',
        title='Node type',
        description='Node type of the input data.',
    )

    constructor: InstructionRunner = Field(
        title='YAML constructor',
        description='Callable used to construct a runtime object from a YAML node.',
    )

    def build_runner(self) -> tuple[Any, InstructionRunner]:
        """Build a Pydantic field definition for the instruction runner.

        Returns:
            A tuple suitable for `create_model`, defining a `ClassVar`
            field bound to the instruction constructor.
        """
        return ClassVar[InstructionRunner], staticmethod(self.constructor)

    def build_node_type(self) -> tuple[Any, str]:
        """Build a Pydantic field definition for the node type.

        Returns:
            A tuple suitable for `create_model`, defining a `ClassVar`
            field bound to the constant node type.
        """
        return ClassVar[Literal['scalar', 'mapping']], self.node_type

    def build(self) -> type[BaseInstruction]:
        """Create a runtime instruction model.

        Returns:
            A `BaseInstruction` subclass with the constructor bound
            as its execution runner.
        """
        return create_model(
            f'{self.name}_Instruction',
            __base__=BaseInstruction,
            runner=self.build_runner(),
            node_type=self.build_node_type(),
        )
