"""Report collector protocol for test execution tracking.

This module defines the interface for collecting and reporting test execution
information, including test cases and individual steps within those cases.
"""

from collections import defaultdict, deque
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, override, runtime_checkable

from pytest_loco.errors import DSLFailure
from pytest_loco.io import TerminalWriter

from .loader import ExtensionsLoaderMixin

if TYPE_CHECKING:
    from collections.abc import Iterator
    from importlib.metadata import EntryPoint


type NodeType = Literal['case', 'step', 'check']


@runtime_checkable
class ReportCollector(Protocol):
    """Protocol for collecting test execution reports and step information.

    This protocol defines the interface that report collectors must implement
    to track test case execution and individual steps within those cases.
    Collectors are responsible for recording test metadata, descriptions,
    context, and failure information.
    """

    def enter_node(self, node_type: NodeType, *,
                   title: str | None = None, description: str | None = None,
                   context: dict[str, Any] | None = None,
                   metadata: dict[str, Any] | None = None) -> None:
        """Start a new node execution.

        Args:
            node_type: Node type.
            title: Node title.
            description: Node description.
            context: Current context
            metadata: Node metadata.
        """
        ...

    def exit_node(self, node_type: NodeType, *,
                  error: Exception | None = None) -> None:
        """Stop the current node execution.

        Args:
            node_type: Node type.
            error: Exception raised during node execution, if any.
        """
        ...


class TotalsCollector(ReportCollector):
    """Simple total results collector."""

    INDENTS: ClassVar[dict['NodeType', int]] = {
        'case': 0,
        'step': 1,
        'check': 2,
    }

    def __init__(self) -> None:
        """Init a new collector."""
        self._levels: defaultdict[NodeType, deque[tuple[bool, str]]] = defaultdict(deque)
        self._stack: deque[str | None] = deque()

    @override
    def enter_node(self, node_type: 'NodeType', *,
                   title: str | None = None, description: str | None = None,
                   context: dict[str, Any] | None = None,
                   metadata: dict[str, Any] | None = None) -> None:
        """Start a new node execution.

        Args:
            node_type: Node type.
            title: Node title.
            description: Node description.
            context: Current context
            metadata: Node metadata.
        """
        if not title:
            title = '<unnamed>'

        self._stack.append(title)

    @override
    def exit_node(self, node_type: 'NodeType', *,
                  error: Exception | None = None) -> None:
        """Stop the current node execution.

        Args:
            node_type: Node type.
            error: Exception raised during node execution, if any.
        """
        title = self._stack.pop()

        error_mark = '!'
        error_color = True

        if isinstance(error, (AssertionError, DSLFailure)):
            error_mark = '-'
        elif error is None:
            error_mark = '+'
            error_color = False

        indent = self.INDENTS.get(node_type, 0) * 2

        current = self._levels[node_type]

        current.append((
            error_color,
            f'{" " * indent}{error_mark} {title}',
        ))

        child_type: NodeType | None = None
        match node_type:
            case 'case':
                child_type = 'step'
            case 'step':
                child_type = 'check'
            case _:
                return

        childs = self._levels[child_type]
        for child in childs:
            current.append(child)
        childs.clear()

        if node_type == 'case':
            current.append((False, ''))

    def get_content(self, isatty: bool = False) -> str:
        """Get content.

        Args:
            isatty: Is a TTY.

        Returns:
            A formatted error message suitable for display.
        """
        writer = TerminalWriter(isatty)

        for error, line in self._levels['case']:
            writer.line(line, red=error, green=not error)

        return writer.content()


class ReportAggregator(ExtensionsLoaderMixin):
    """Aggregates multiple report collectors for test execution tracking.

    This class collects and manages multiple implementations of the ReportCollector
    protocol, discovered via entry points. It delegates all test case and step
    tracking calls to all registered collectors.
    """

    def __init__(self, strict: bool = False) -> None:
        """Initialize the report aggregator by discovering registered collectors.

        Loads all report collectors registered via the 'loco_report_collectors'
        entry point group and instantiates them. Collectors are stored for later
        use when tracking test cases and steps.

        Args:
            strict: Whether to raise errors on collectors loading failures instead
                of emitting warnings.
        """
        self.strict_mode = strict
        self.collectors: list[ReportCollector] = list(self.load_collectors())

        self.totals = TotalsCollector()
        self.collectors.append(self.totals)

    def enter_node(self, node_type: NodeType, *,
                   title: str | None = None, description: str | None = None,
                   context: dict[str, Any] | None = None,
                   metadata: dict[str, Any] | None = None) -> None:
        """Start a new node execution.

        Args:
            node_type: Node type.
            title: Node title.
            description: Node description.
            context: Current context
            metadata: Node metadata.
        """
        for collector in self.collectors:
            collector.enter_node(
                node_type=node_type,
                title=title,
                description=description,
                context=context,
                metadata=metadata,
            )

    def exit_node(self, node_type: NodeType, *,
                  error: Exception | None = None) -> None:
        """Stop the current node execution.

        Args:
            node_type: Node type.
            error: Exception raised during node execution, if any.
        """
        for collector in self.collectors:
            collector.exit_node(
                node_type=node_type,
                error=error,
            )

    def _load_collector(self, entrypoint: 'EntryPoint') -> ReportCollector | None:
        """Load and process a single collector entry point.

        Safely loads the collector type.

        Args:
            entrypoint: Entry point describing the collector to load.

        Raises:
            PluginError: If any loading issues occur on strict mode.
        """
        try:
            collector: type[ReportCollector] = entrypoint.load()
            if callable(collector):
                instance = collector()

        except Exception as base:
            if error := self.emit_plugin_issue(
                f'Failed to load entrypoint {entrypoint.name!r}',
                entrypoint,
            ):
                raise error from base
            return None

        if isinstance(instance, ReportCollector):
            return instance

        if error := self.emit_plugin_issue(
            f'Can not find a report collector class in {entrypoint.name!r}',
            entrypoint,
        ):
            raise error

        return None

    def load_collectors(self) -> 'Iterator[ReportCollector]':
        """Load all registered report collector classes from entry points.

        Discovers and yields collector classes registered via the
        'loco_report_collectors' entry point group. Only classes that are
        subclasses of ReportCollector are yielded.

        Yields:
            Collector classes that implement the ReportCollector protocol.
        """
        for entrypoint in entry_points().select(group='loco_report_collectors'):
            if instance := self._load_collector(entrypoint):
                yield instance
