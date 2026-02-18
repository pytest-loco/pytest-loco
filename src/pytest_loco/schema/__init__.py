"""Declarative DSL base-schema for executable test scenarios.

Defines immutable Pydantic models that describe test cases, templates,
steps, inputs, parameters, and their validation rules. The module specifies
the structural and semantic contract of the DSL and is consumed by external
execution engines and tooling.
"""

from .actions import ActionRunner, BaseAction, IncludeAction
from .cases import Case, Template
from .checks import BaseCheck, CheckRunner
from .contents import BaseContent, ContentRunner
from .instructions import BaseInstruction, InstructionRunner

__all__ = (
    'ActionRunner',
    'BaseAction',
    'BaseCheck',
    'BaseContent',
    'BaseInstruction',
    'Case',
    'CheckRunner',
    'ContentRunner',
    'IncludeAction',
    'InstructionRunner',
    'Template',
)
