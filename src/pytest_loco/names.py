"""DSL names primitive types and validation rules.

This module defines base name patterns and strongly-typed aliases used by the
DSL execution engine to validate action identifiers and variable names.

The rules defined here form part of the public DSL contract and are relied upon
by scenario parsers, validators, plugins, and IDE tooling.
"""

from re import ASCII
from re import compile as regexp
from typing import Annotated

from pydantic import Field

#: Base pattern for all DSL identifiers.
#: Identifiers must start with a letter and may contain letters, digits, or underscores
_NAME_PATTERN = r'[a-zA-Z][\w]*'

#: Compiled pattern for action identifiers.
#: Supports both builtin actions ("debug") and plugin-qualified actions ("http.get", "utils.auth").
ACTION_PATTERN = regexp(
    rf'^((?P<plugin>{_NAME_PATTERN})\.)?(?P<name>{_NAME_PATTERN})$',
    flags=ASCII,
)

#: Compiled pattern for variable identifiers
VARIABLE_PATTERN = regexp(
    rf'^(?P<name>{_NAME_PATTERN})$',
    flags=ASCII,
)


Action = Annotated[
    str, Field(
        pattern=rf'^({_NAME_PATTERN}\.)?{_NAME_PATTERN}$',
        title='Action identifier',
        description=(
            'Name of the action executed by a scenario step. '
            'An action may be specified either as a bultins name '
            '(for example, `debug`) or as a plugin-qualified name '
            'using dot notation (for example, `http.get`). '
            'Action identifiers are limited to ASCII letters, '
            'digits, and underscores.'
        ),
        examples=[
            'debug',
            'http.get',
        ],
    ),
]

Variable = Annotated[
    str, Field(
        pattern=rf'^{_NAME_PATTERN}$',
        title='Variable identifier',
        description=(
            'Name of a variable used to store or reference values within '
            'a scenario execution context. '
            'Variable identifiers must start with a letter and may contain '
            'letters, digits, or underscores. '
            'Names are restricted to ASCII characters.'
        ),
        examples=[
            'userId',
            'api_token',
            'result',
        ],
    ),
]
