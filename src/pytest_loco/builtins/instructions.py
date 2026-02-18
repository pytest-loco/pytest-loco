"""Built-in YAML instructions for deferred value resolution.

This module defines built-in DSL instructions used to resolve values
from the execution context at runtime.

Each instruction is implemented as a PyYAML constructor and produces
a deferred lookup object instead of an immediate value. These lookups
are evaluated later against the execution context.
"""

from base64 import b64decode
from datetime import date, datetime, timedelta
from pathlib import Path
from re import MULTILINE, sub
from re import compile as regexp
from typing import TYPE_CHECKING

from yaml.error import MarkedYAMLError

from pytest_loco.builtins.lookups import LambdaLookup, SecretLookup, VariableLookup
from pytest_loco.errors import DSLError, DSLRuntimeError, DSLSchemaError
from pytest_loco.extensions import Instruction

if TYPE_CHECKING:
    from yaml import BaseLoader
    from yaml.nodes import ScalarNode

#: Pattern for duration.
#: Identifiers must start with a digits and contains a unit.
_DURATION_PATTERN = regexp(r'^(?P<value>-?\d+(\.\d+)?)(?P<unit>[YmwdHhMSs])$')

#: Units for duration.
_DURATION_UNITS = {
    'Y': 31_556_952,
    'm': 2_629_746,
    'w': 604_800,
    'd': 86_400,
    'H': 3_600,
    'h': 3_600,
    'M': 60,
    'S': 1,
    's': 1,
}


def variable_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> VariableLookup:
    """Construct a variable lookup instruction.

    This constructor is used for instructions such as `!var` and `!ctx`.
    It produces a deferred resolver that extracts a value from the
    execution context at runtime using a variable path.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a variable path.

    Returns:
        A `VariableLookup` bound to the parsed variable path.

    Raises:
        DSLSchemaError: If the node is not a scalar or the variable path.
    """
    try:
        return VariableLookup(path=loader.construct_scalar(node))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid variable path', node) from base


def secret_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> SecretLookup:
    """Construct a secret lookup instruction.

    This constructor is used for the `!secret` instruction and produces
    a deferred resolver that extracts a secret value from the execution
    context at runtime.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a secret path.

    Returns:
        A `SecretLookup` bound to the parsed secret path.

    Raises:
        DSLSchemaError: If the node is not a scalar or the secret path is invalid.
    """
    try:
        return SecretLookup(path=loader.construct_scalar(node))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid secret variable path', node) from base


def lambda_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> LambdaLookup:
    """Construct a lambda expression lookup instruction.

    This constructor is used for the `!lambda` instruction and produces
    a deferred resolver that evaluates a Python expression against the
    execution context at runtime.

    The expression must be a valid Python expression suitable for use
    as the body of a lambda function.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing the lambda expression body.

    Returns:
        A `LambdaLookup` instance bound to the compiled expression.

    Raises:
        DSLSchemaError: If the node is not a scalar or the expression
            has invalid syntax or cannot be compiled.
    """
    try:
        return LambdaLookup(body=loader.construct_scalar(node))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid syntax for lambda body', node) from base


def date_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> date:
    """YAML constructor for ISO-formatted date values.

    This constructor parses a scalar node containing a date in ISO 8601
    format (YYYY-MM-DD) and returns a `datetime.date` instance.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing the date string.

    Returns:
        Parsed `date` instance.

    Raises:
        DSLSchemaError: If the value cannot be parsed as an ISO date.
    """
    try:
        return date.fromisoformat(loader.construct_scalar(node))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid date format', node) from base


def datetime_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> datetime:
    """YAML constructor for ISO-formatted datetime values.

    This constructor parses a scalar node containing a datetime in ISO 8601
    format and returns a `datetime.datetime` instance.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing the datetime string.

    Returns:
        Parsed `datetime` instance.

    Raises:
        DSLSchemaError: If the value cannot be parsed as an ISO datetime.
    """
    try:
        return datetime.fromisoformat(loader.construct_scalar(node))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid datetime format', node) from base


def timedelta_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> timedelta:
    """YAML constructor for timedelta values expressed in seconds.

    This constructor parses a scalar node containing a numeric value
    representing a duration in seconds and returns a `timedelta` instance.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a numeric duration in seconds.

    Returns:
        Parsed `timedelta` instance.

    Raises:
        DSLSchemaError: If the value cannot be parsed as a float.
    """
    try:
        return timedelta(seconds=float(loader.construct_scalar(node)))

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid timedelta format', node) from base


def duration_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> timedelta:
    """YAML constructor for timedelta values expressed in formatted string.

    This constructor parses a scalar node containing a string value
    representing a duration and returns a `timedelta` instance.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a numeric duration in seconds.

    Returns:
        Parsed `timedelta` instance.

    Raises:
        DSLSchemaError: If the value cannot be parsed.
    """
    try:
        match = _DURATION_PATTERN.match(loader.construct_scalar(node))
        if not match:
            raise DSLSchemaError.from_yaml_node('Invalid duration format', node)

        value = float(match.group('value'))
        unit = _DURATION_UNITS.get(match.group('unit'))
        if not unit:  # pragma: no cover
            raise DSLSchemaError.from_yaml_node('Invalid duration unit', node)

        return timedelta(seconds=value * unit)

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid duration value', node) from base


def base64_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> bytes:
    """YAML constructor for Base64-encoded binary data.

    This constructor parses a scalar node containing Base64-encoded data
    and returns decoded bytes. Missing padding characters (`=`) are
    automatically added if required.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing Base64-encoded string.

    Returns:
        Decoded binary data.

    Raises:
        DSLSchemaError: If the value is not valid Base64.
    """
    try:
        fromat_value = loader.construct_scalar(node)
        value = sub(r'\s', '', fromat_value, flags=MULTILINE)

        missing_padding = len(value) % 4
        if missing_padding:
            value += '=' * (4 - missing_padding)

        return b64decode(value, validate=True)

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid base64-encoded value', node) from base


def binary_hex_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> bytes:
    """YAML constructor for hexadecimal-encoded binary data.

    This constructor parses a scalar node containing hexadecimal data
    and returns decoded bytes. Whitespace characters (spaces, newlines)
    are ignored.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing hexadecimal string.

    Returns:
        Decoded binary data.

    Raises:
        DSLSchemaError: If the value is not valid hexadecimal data.
    """
    try:
        format_value = loader.construct_scalar(node)
        value = sub(r'\s', '', format_value, flags=MULTILINE).lower()

        return bytes.fromhex(value)

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except Exception as base:
        raise DSLSchemaError.from_yaml_node('Invalid hexadecimal-encoded value', node) from base


def text_file_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> str:
    """YAML constructor for loading text file contents.

    This constructor treats the scalar value as a filesystem path and
    returns the contents of the referenced text file.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a file path.

    Returns:
        Contents of the text file.

    Raises:
        DSLSchemaError: If the value is not valid filepath.
        DSLRuntimeError: If the file does not exist or cannot be read.
    """
    try:
        file_ = Path(loader.construct_scalar(node))
        if not file_.exists():
            raise DSLRuntimeError.from_yaml_node('File not found', node)

        return file_.read_text()

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except DSLError:
        raise

    except Exception as base:
        raise DSLRuntimeError.from_yaml_node('Invalid text IO', node) from base


def binary_file_constructor(loader: 'BaseLoader', node: 'ScalarNode') -> bytes:
    """YAML constructor for loading binary file contents.

    This constructor treats the scalar value as a filesystem path and
    returns the contents of the referenced file as bytes.

    Args:
        loader: YAML loader instance.
        node: Scalar node containing a file path.

    Returns:
        Contents of the file as bytes.

    Raises:
        DSLSchemaError: If the value is not valid filepath.
        DSLRuntimeError: If the file does not exist or cannot be read.
    """
    try:
        file_ = Path(loader.construct_scalar(node))
        if not file_.exists():
            raise DSLRuntimeError.from_yaml_node('File not found', node)

        return file_.read_bytes()

    except MarkedYAMLError as base:
        raise DSLSchemaError.from_yaml_error(base) from base

    except DSLError:
        raise

    except Exception as base:
        raise DSLRuntimeError.from_yaml_node('Invalid binary IO', node) from base


#: Instruction for `!lambda <body>` expression.
lambda_ = Instruction(name='lambda', constructor=lambda_constructor)

#: Instruction for `!secret <path>` expression (path must be in dot notation).
secret = Instruction(name='secret', constructor=secret_constructor)

#: Instruction for `!var <path>` expression (path must be in dot notation).
variable = Instruction(name='var', constructor=variable_constructor)

#: Instruction for `!date <ISO-formatted date>` expression.
date_ = Instruction(name='date', constructor=date_constructor)

#: Instruction for `!datetime <ISO-formatted datetime>` expression.
datetime_ = Instruction(name='datetime', constructor=datetime_constructor)

#: Instruction for `!timedelta <seconds>` expression.
timedelta_ = Instruction(name='timedelta', constructor=timedelta_constructor)

#: Instruction for `!duration <value><unit>` expression.
duration = Instruction(name='duration', constructor=duration_constructor)

#: Instruction for `!base64 <base64-data>` expression (data must be a valid base64).
#: Optional, data may be pretty printed (whitespaces and multilines allowed).
base64 = Instruction(name='base64', constructor=base64_constructor)

#: Instruction for `!binaryHex <hex-data>` expression (data must be a valid hex-string without `0x` prefixes).
#: Optional, data may be pretty printed (whitespaces and multilines allowed).
binary_hex = Instruction(name='binaryHex', constructor=binary_hex_constructor)

#: Instruction for `!textFile <path>` expression (file must exists).
text_file = Instruction(name='textFile', constructor=text_file_constructor)

#: Instruction for `!binaryFile <path>` expression (file must exists).
binary_file = Instruction(name='binaryFile', constructor=binary_file_constructor)
