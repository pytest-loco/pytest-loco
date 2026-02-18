"""Base instruction model for YAML compilation.

This module defines the base class used to represent compiled YAML
instructions that are registered as PyYAML constructors.
"""

from collections.abc import Callable
from typing import ClassVar

from yaml import BaseLoader
from yaml.nodes import Node

from pytest_loco.models import SchemaModel
from pytest_loco.values import Deferred, RuntimeValue

#: The runner is invoked by the YAML loader during parsing and is
#: responsible for converting a YAML node into a runtime representation
#: (for example, an AST node, a step object, or a primitive value).
type InstructionRunner = Callable[[BaseLoader, Node], Deferred[RuntimeValue]]


class BaseInstruction(SchemaModel):
    """Base class for a compiled YAML instruction.

    Instances of this model are registered as PyYAML constructors and are
    invoked during YAML parsing. The actual execution logic is provided by
    a class-level `runner` callable, which defines how a YAML node is
    transformed into a runtime object.

    Subclasses are expected to define a `runner` attribute.
    """

    #: Callable implementing the instruction execution logic.
    runner: ClassVar[InstructionRunner]

    def __call__(self, loader: BaseLoader, node: Node) -> Deferred[RuntimeValue]:
        """Invoke the instruction runner.

        This method is called by PyYAML when the instruction is registered
        as a constructor. It delegates execution to the class-level `runner` callable.

        Args:
            loader: YAML loader invoking the constructor.
            node: YAML node associated with the instruction.

        Returns:
            A runtime object produced from the given YAML node.
        """
        return type(self).runner(loader, node)
