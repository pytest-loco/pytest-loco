"""Core exception hierarchy.

This module defines base error and warning types used across the library
to report plugin loading issues, DSL schema and model construction
failures, and runtime execution errors in a structured and extensible way.
"""

from os import linesep, path
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from pydantic import BaseModel  # noqa: TC002
from yaml import dump, serialize

from pytest_loco.io import TerminalStr, TerminalWriter
from pytest_loco.values import normalize

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint
    from typing import Self

if TYPE_CHECKING:
    from pydantic_core import ValidationError
    from yaml.error import MarkedYAMLError
    from yaml.nodes import Node

if TYPE_CHECKING:
    from pytest_loco.values import Value


WRAP_VERBOSITY_LIMIT = 4

SNIPPET_INDENT = 2

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
    #: Runtime source.
    source: str | None
    #: Runtime element associated with the error.
    element: Any


class ErrorFormatter:
    """Utility class for formatting DSL-related errors.

    This formatter is responsible for producing human-readable
    error messages with optional source location and YAML-based
    contextual snippets.
    """

    @classmethod
    def with_longrepr(cls, message: str,
                      context: ErrorContext | None = None,
                      isatty: bool = False,
                      verbosity: int = 0) -> TerminalStr:
        """Extend a message string with formatted long representation.

        This method combines a base message with optional location
        metadata and a YAML snippet describing the failing element
        or runtime context.

        Args:
            message: Base human-readable error message.
            context: Optional error context with location and data.
            isatty: Is a TTY.
            verbosity: Verbosity level.

        Returns:
            A `TerminalStr` with fully formatted error message suitable for display.
        """
        writer = TerminalWriter(isatty)

        if context:
            writer.write(cls.get_location_string(context), bold=True, red=True)
            writer.line(f' {cls.__name__}')
            writer.write(linesep)

            if verbosity > 1 and (locals_snippet := cls.get_snippet(context, 'context')):
                writer.line('Locals:')
                writer.source(locals_snippet)
                writer.write(linesep)

            if source := context.get('source'):
                if verbosity > 1:
                    writer.line('Source:')
                writer.source(cls._make_indent(source, ' ' * FORMAT_INDENT))
                writer.write(linesep)
            elif source_snippet := cls.get_snippet(context, 'element'):
                if verbosity > 1:
                    writer.line('Source:')
                writer.source(source_snippet)
                writer.write(linesep)

        writer.lines(message)

        output = TerminalStr(message)
        setattr(output, 'toterminal', lambda tw: tw.write(writer.content()))  # noqa: B010

        return output

    @classmethod
    def get_location_string(cls, context: ErrorContext) -> str:
        """Format source and execution location information.

        Args:
            context: Error context containing location metadata.
            indent: Optional indentation (string or number of spaces).

        Returns:
            A formatted location string including filename, line,
            column, step, and expectation numbers when available.
        """
        filename = context.get('filename')
        if not filename:
            filename = FORMAT_FILENAME

        message = (
            path.relpath(filename)
            .replace('\\', '/')
        )

        if (line_num := context.get('line_num')) is not None:
            line_num += 1
            message += f':{line_num}'
            if (column_num := context.get('column_num')) is not None:
                column_num += 1
                message += f':{column_num}'

        message += ':'

        return message

    @classmethod
    def get_snippet(cls, context: ErrorContext,
                    field: Literal['context', 'element']) -> str:
        """Return a YAML-formatted snippet for a given context field.

        The method normalizes the provided value and converts it into
        a formatted YAML block suitable for terminal display.

        Args:
            context: Error context containing runtime metadata.
            field: Either "context" for runtime locals or "element" for DSL element data.

        Returns:
            A formatted YAML snippet or an empty string if no data is available.
        """
        if value := context.get(field):
            node = normalize(value, context.get('context'))
            return cls._make_snippet(node, ' ' * FORMAT_INDENT)

        return ''

    @classmethod
    def _make_snippet(cls, element: Any, indent: str) -> str:  # noqa: ANN401
        """Serialize an element to YAML and apply indentation.

        Args:
            element: DSL element or runtime data structure.
            indent: Indentation prefix applied to each non-empty line.

        Returns:
            A formatted YAML snippet string.
        """
        data = dump(
            element,
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

    def repr(self, isatty: bool = False, verbosity: int = 0) -> str:
        """Return formatted error representation.

        Args:
            isatty: Whether output supports ANSI markup.
            verbosity: Verbosity level controlling snippet inclusion.

        Returns:
            A formatted terminal-ready representation of the error.
        """
        return self.with_longrepr(
            self.message,
            self.context,
            isatty,
            verbosity,
        )

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
            source=serialize(node),
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
    def from_yaml_error(cls, error: 'MarkedYAMLError',
                        node: 'Node | None' = None) -> 'Self':
        """Create a schema error from a YAML parsing failure.

        This method converts a low-level PyYAML error into a DSL-level
        schema error. Positional and contextual information may be
        preserved or enhanced in future iterations.

        Args:
            error: Exception raised by the YAML parser.
            node: YAML node associated with the error.

        Returns:
            DSLSchemaError representing the YAML parsing failure.
        """
        filename = None
        line = None
        column = None

        if error.problem_mark:
            filename = error.problem_mark.name
            line = error.problem_mark.line
            column = error.problem_mark.column
        elif error.context_mark:
            filename = error.context_mark.name
            line = error.context_mark.line
            column = error.context_mark.column

        source = None
        if node:
            source = serialize(node)

        error_context = ErrorContext(
            filename=filename,
            line_num=line,
            column_num=column,
            source=source,
            error=error,
        )

        message = 'Invalid YAML'
        if error.problem:
            message += f': {error.problem}'

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

        entity = 'entity'
        if check_num is not None:
            entity = 'expectation'

        message = f'Invalid {entity}'
        if not data or not isinstance(data, dict):
            message = f'Wrong {entity} type'

        if step_num is not None:
            message += f' on document #{step_num}'

        return cls(message, context=error_context)


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

        The model is converted to a serializable representation
        and included in the formatted error snippet.

        Args:
            model: Pydantic model associated with the failure.
            message: Optional additional runtime message.
            context: Runtime values available at failure time.
            filename: Source filename.
            step_num: DSL step number.
            check_num: Expectation index within step.

        Returns:
            A DSLRuntimeError instance.
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
            error_message += f': {message}'

        return cls(error_message, context=error_context)


class DSLFailure(DSLError):
    """Exception representing a failed DSL expectation.

    This exception is raised when a DSL check evaluates to False
    and indicates a test failure rather than a structural or
    runtime error.
    """
