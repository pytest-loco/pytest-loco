"""Core exception hierarchy.

This module defines base error and warning types used across the library
to report plugin loading issues, DSL schema and model construction
failures, and runtime execution errors in a structured and extensible way.
"""

from os import linesep
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import BaseModel  # noqa: TC002
from yaml import dump
from yaml.error import MarkedYAMLError

from pytest_loco.values import MAPPINGS, SCALARS, SEQUENCES

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint
    from typing import Self

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails, ValidationError
    from yaml.nodes import Node

if TYPE_CHECKING:
    from pytest_loco.values import Value

SNIPPET_ELLIPSIS = f' ...{linesep}'
SNIPPET_SEPARATOR = f' ---{linesep}'
SNIPPET_INDENT = 2

FORMAT_REPLACER = '<runtime object>'
FORMAT_FILENAME = '<unicode string>'
FORMAT_INDENT = 4


class ErrorContext(TypedDict, total=False):
    """Container describing contextual information for error formatting.

    This structure aggregates optional metadata that may be available
    at different stages of DSL parsing, validation, or execution.

    All fields are optional; the formatter adapts output based on
    provided values.
    """

    #: Name of the source file where the error occurred.
    filename: str | None

    #: Line number in the source file.
    line_num: int | None
    #: Column number in the source file.
    column_num: int | None

    #: Number of the DSL step where the error occurred.
    step_num: int | None
    #: Number of the expectation within a step.
    check_num: int | None

    #: Underlying exception that triggered formatting.
    error: Exception | None

    #: Runtime context values available at the moment of failure.
    context: dict[str, Any] | None
    #: Runtime element associated with the error.
    element: Any


class ErrorFormatter:
    """Utility class for formatting DSL-related errors.

    This formatter is responsible for producing human-readable
    error messages with optional source location and YAML-based
    contextual snippets.
    """

    @classmethod
    def format(cls, message: str, context: ErrorContext | None = None) -> str:
        """Format an error message using contextual information.

        This method combines a base message with optional location
        metadata and a YAML snippet describing the failing element
        or runtime context.

        Args:
            message: Base human-readable error message.
            context: Optional error context with location and data.

        Returns:
            A fully formatted error message suitable for display.
        """
        if not context:
            return message

        message += linesep
        message += cls.get_location_string(context, indent=FORMAT_INDENT)
        message += cls.get_snippet_string(context, indent=FORMAT_INDENT * 2)

        return message

    @classmethod
    def get_location_string(cls, context: ErrorContext, *,
                            indent: str | int | None = None) -> str:
        """Format source and execution location information.

        Args:
            context: Error context containing location metadata.
            indent: Optional indentation (string or number of spaces).

        Returns:
            A formatted location string including filename, line,
            column, step, and expectation numbers when available.
        """
        indent = cls._ensure_indent(indent)

        filename = context.get('filename')
        if not filename:
            filename = FORMAT_FILENAME

        message = f'{indent}in "{filename}"'
        if (line_num := context.get('line_num')) is not None:
            line_num += 1
            message += f', line {line_num}'
            if (column_num := context.get('column_num')) is not None:
                column_num += 1
                message += f', column {column_num}'
        message += linesep

        if (step_num := context.get('step_num')) is not None:
            step_num += 1
            message += f'{indent}on step {step_num}'
            if (check_num := context.get('check_num')) is not None:
                check_num += 1
                message += f', expectation {check_num}'
            message += linesep

        return message

    @classmethod
    def get_snippet_string(cls, context: ErrorContext, *,
                           indent: str | int | None = None) -> str:
        """Generate a formatted snippet illustrating the error context.

        Args:
            context: Error context containing model or exception data.
            indent: Optional indentation (string or number of spaces).

        Returns:
            A formatted multi-line snippet string, or an empty string
            if no snippet data is available.
        """
        indent = cls._ensure_indent(indent)

        if (error := context.get('error')) and isinstance(error, MarkedYAMLError):
            snippet = error.problem_mark.get_snippet(indent=0) or ''
            return cls._make_indent(snippet, indent)

        if element := context.get('element'):
            return cls._make_snippet(element, context, indent)

        return ''

    @classmethod
    def _make_snippet(cls, element: dict[str, Any],
                      context: ErrorContext, indent: str) -> str:
        """Build a YAML-based snippet for an element.

        Args:
            element: Element associated with the error.
            context: Error context containing optional runtime values.
            indent: String indentation prefix.

        Returns:
            A formatted snippet string including context and model data.
        """
        snippet = f'{indent}{SNIPPET_ELLIPSIS}'

        if values := context.get('context'):
            snippet += cls._make_yaml({'context': {**values}}, indent)
            snippet += linesep
            snippet += f'{indent}{SNIPPET_SEPARATOR}'

        snippet += cls._make_yaml(element, indent)
        snippet += linesep

        return snippet

    @classmethod
    def _filter_unsafe(cls, value: Any) -> Any:  # noqa: ANN401
        """Recursively sanitize values for safe YAML serialization.

        Non-scalar and non-container objects are replaced with
        a placeholder to prevent leaking executable or opaque data.

        Args:
            value: Arbitrary value to sanitize.

        Returns:
            A YAML-safe representation of the value.
        """
        if value is None or isinstance(value, SCALARS):
            return value

        if isinstance(value, MAPPINGS):
            return type(value)({
                key: cls._filter_unsafe(item)
                for key, item in value.items()
            })

        if isinstance(value, SEQUENCES):
            return type(value)(
                cls._filter_unsafe(item)
                for item in value
            )

        return FORMAT_REPLACER

    @classmethod
    def _make_yaml(cls, value: Any, indent: str = '') -> str:  # noqa: ANN401
        """"Serialize a value to a YAML-formatted string.

        The value is first sanitized to remove unsafe or non-serializable
        objects and then rendered as YAML with stable formatting.

        Args:
            value: Arbitrary value to serialize.
            indent: Optional indentation prefix.

        Returns:
            A YAML-formatted string representation of the value.
        """
        data = dump(
            cls._filter_unsafe(value),
            indent=SNIPPET_INDENT,
            sort_keys=False,
        )

        return cls._make_indent(data, indent)

    @staticmethod
    def _make_indent(value: str, indent: str) -> str:
        """Apply indentation to a multi-line string.

        Empty or whitespace-only lines are omitted.

        Args:
            value: Original multi-line string.
            indent: Indentation prefix.

        Returns:
            Indented string.
        """
        if not indent:
            return value

        return linesep.join(
            f'{indent}{line}'
            for line in value.splitlines()
            if line.strip()
        )

    @staticmethod
    def _ensure_indent(indent: str | int | None = None) -> str:
        """Normalize indentation input.

        Args:
            indent: Indentation as string or number of spaces.

        Returns:
            A string consisting of spaces or the provided string.
        """
        if isinstance(indent, int) and indent > 0:
            return ' ' * indent

        if isinstance(indent, str):
            return indent

        return ''


class PluginWarning(UserWarning):
    """Warning emitted for non-fatal plugin-related issues.

    This warning is used when a plugin cannot be loaded or processed,
    but the error does not prevent further execution (for example,
    when running in non-strict mode).
    """


class DSLError(Exception, ErrorFormatter):
    """Base exception for all pytest-loco errors.

    All custom exceptions raised by the library should inherit from
    this class to allow unified error handling by callers.
    """

    def __init__(self, message: str, *,
                 context: ErrorContext | None = None) -> None:
        """Initialize an error.

        Args:
            message: Human-readable error description.
            context: Error context containing optional runtime values.
        """
        self.message = message
        self.context = context

        super().__init__(message)

    def __str__(self) -> str:
        """String represenatation."""
        return self.format(self.message, self.context)

    @classmethod
    def from_yaml_node(cls, message: str, node: 'Node',
                       error: Exception | None = None) -> 'Self':
        """Create an error instance from a YAML node.

        This helper extracts positional information from a PyYAML
        node and attaches it to the resulting error context.

        Args:
            message: Human-readable error message.
            node: YAML node associated with the error.
            error: Optional underlying exception.

        Returns:
            An initialized DSLError instance with location context.
        """
        error_context = ErrorContext(
            filename=node.start_mark.name,
            line_num=node.start_mark.line,
            column_num=node.start_mark.column,
            error=error,
        )

        return cls(message, context=error_context)


class PluginError(DSLError):
    """Error raised for fatal plugin-related failures.

    This exception is raised when a plugin entry point is invalid,
    misconfigured, or fails to load in strict mode.
    """

    def __init__(self, message: str, *,
                 entrypoint: 'EntryPoint | None' = None) -> None:
        """Initialize a plugin error.

        Args:
            message: Human-readable error description.
            entrypoint: Optional plugin entry point associated with the error.
        """
        self.entrypoint = entrypoint

        super().__init__(message)


class DSLBuildError(DSLError):
    """Error raised during DSL model or builder construction.

    This exception indicates a failure while dynamically building
    DSL components such as actions, checks, instructions, or
    Pydantic-based schemas.
    """


class DSLSchemaError(DSLError):
    """Error raised when a DSL schema is invalid or inconsistent.

    This exception is used when a parsed DSL document violates
    structural or semantic constraints that cannot be represented
    or validated at the Pydantic model level.
    """

    @classmethod
    def from_yaml_error(cls, error: MarkedYAMLError) -> 'Self':
        """Create a schema error from a YAML parsing failure.

        This method converts a low-level PyYAML error into a DSL-level
        schema error. Positional and contextual information may be
        preserved or enhanced in future iterations.

        Args:
            error: Exception raised by the YAML parser.

        Returns:
            DSLSchemaError representing the YAML parsing failure.
        """
        error_context = ErrorContext(
            filename=error.problem_mark.name,
            line_num=error.problem_mark.line,
            column_num=error.problem_mark.column,
            error=error,
        )

        message = 'Invalid YAML'
        if error.problem:
            message += f'{linesep}{' '* FORMAT_INDENT}{error.problem}'

        return cls(message, context=error_context)

    @classmethod
    def from_pydantic_error(cls, error: 'ValidationError', *,
                            data: Any = None,  # noqa: ANN401
                            filename: str | None = None,
                            step_num: int | None = None,
                            check_num: int | None = None) -> 'Self':
        """Create a schema error from a Pydantic validation failure.

        This method converts a Pydantic ValidationError raised during
        DSL document validation into a DSL-level schema error.

        The error message aggregates validation issues into a concise,
        human-readable form. Detailed formatting is deferred to a
        future iteration.

        Args:
            error: ValidationError raised by Pydantic.
            data: Element data.
            filename: Name of the source file where the error occurred.
            step_num: Number of the DSL step where the error occurred.
            check_num: Number of the expectation within a step.

        Returns:
            DSLSchemaError representing the validation failure.

        Notes:
            This method does not have access to original YAML node positions.
            Error snippets are reconstructed heuristically from document data.
        """
        error_context = ErrorContext(
            filename=filename,
            step_num=step_num,
            check_num=check_num,
            error=error,
            element=data,
        )

        if not data or not isinstance(data, dict):
            return cls('Type validation error', context=error_context)

        for item in error.errors(include_url=False, include_input=False):
            if context := cls._locate_pydantic_context(data, item):
                message, value = context
                return cls(message, context=ErrorContext({**error_context, 'element': value}))

        return cls('Validation error', context=error_context)

    @classmethod
    def _locate_pydantic_context(cls, value: 'Any',  # noqa: ANN401
                                 error: 'ErrorDetails') -> tuple[str, Any] | None:
        """Locate the most specific failing element in validated data.

        This method walks the Pydantic error location path and attempts
        to extract the minimal substructure responsible for the failure.
        The extracted fragment is later used to build a focused YAML
        snippet for error reporting.

        Args:
            value: Root data structure being validated.
            error: Pydantic error details including location path.

        Returns:
            A tuple of (error message, extracted element) if a relevant
            context can be located, otherwise None.
        """
        container = last_item = value
        last_key: int | str | None = None

        for key in error['loc']:
            if isinstance(last_item, (list, tuple)):
                if isinstance(key, int) and 0 <= key < len(last_item):
                    container = last_item
                    last_item = last_item[key]
                    last_key = key
            elif isinstance(last_item, dict):
                if key in last_item:
                    container = last_item
                    last_item = last_item[key]
                    last_key = key
            else:
                return None

        message = None
        if isinstance(last_key, (int, str)):
            for item in (error.get('msg') or '').splitlines():
                item_message = item.strip()
                if item_message:
                    message = item_message
                    break

        if message:
            if isinstance(container, (list, tuple)):
                return message, [last_item]
            if isinstance(container, dict):
                return message, {last_key: last_item}

        return None

class DSLRuntimeError(DSLError):
    """Error raised during DSL execution.

    This exception indicates a failure that occurs while executing
    DSL actions, checks, or runtime instructions.
    """

    @classmethod
    def from_pydantic_model(cls, model: BaseModel, *,  # noqa: PLR0913
                            message: str | None = None,
                            context: dict[str, 'Value'] | None = None,
                            filename: str | None = None,
                            step_num: int | None = None,
                            check_num: int | None = None) -> 'Self':
        """Create a runtime error from a Pydantic model instance.

        This method converts a Pydantic model into a DSL-level runtime error.

        Args:
            model: A Pydantic model.
            message: An optional custom message.
            context: A context dictionary.
            filename: An optional filename of source.
            step_num: Position of step.
            check_num: Position of expectation.

        Returns:
            DSLRuntimeError representing the validation failure.
        """
        error_context = ErrorContext(
            filename=filename,
            step_num=step_num,
            check_num=check_num,
            context=context,
            element=model.model_dump(
                exclude_none=True,
                exclude_unset=True,
            ),
        )

        error_message = 'Runtime error'
        if message:
            error_message += f'{linesep}{' ' * FORMAT_INDENT}{message}'

        return cls(error_message, context=error_context)
