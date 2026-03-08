"""Runtime execution layer for DSL-based test plans.

This module defines the execution model for parsed DSL documents,
including orchestration of headers, steps, actions, expectations,
and template inclusion. It also integrates DSL execution with pytest
by providing a custom pytest.Item implementation.
"""

from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING

import pytest

from pytest_loco.context import ContextDict
from pytest_loco.core import PARSER, REPORTER
from pytest_loco.errors import WRAP_VERBOSITY_LIMIT, DSLError, DSLFailure, DSLRuntimeError, ErrorContext
from pytest_loco.schema import Case, IncludeAction

if TYPE_CHECKING:
    from collections.abc import Callable
    from os import PathLike
    from typing import Any

if TYPE_CHECKING:
    from pydantic import BaseModel

if TYPE_CHECKING:
    from pytest_loco.core import DocumentParser, Header, ReportAggregator, Step
    from pytest_loco.schema import BaseAction, BaseCheck
    from pytest_loco.values import Value


class TestPlan:
    """Executable runtime representation of a DSL test specification.

    A TestPlan encapsulates a parsed DSL document, including an optional
    header and an ordered sequence of steps. It is responsible for
    executing actions, evaluating expectations, handling includes,
    and managing execution context.
    """

    __test__ = False

    def __init__(self, header: 'Header', steps: tuple['Step', ...],
                 params: dict[str, 'Value'], parent: 'TestCase') -> None:
        """Initialize a test execution plan.

        Args:
            header: Optional DSL header (case-level action).
            steps: Ordered sequence of DSL steps.
            params: Initial parameter context.
            parent: Optional pytest item owning this plan.
        """
        self.header = header
        self.steps = steps
        self.params = params

        self.parent = parent

        self.parser = parent.parser
        self.reporter = parent.reporter

    def run_callable[T: dict[str, Value] | bool](
        self, executor: 'Callable[[], T]', model: 'BaseModel', *,
        context: dict[str, 'Value'] | None = None,
        step_num: int | None = None,
        check_num: int | None = None,
    ) -> T:
        """Execute a callable with unified DSL error handling.

        Args:
            executor: Callable performing the actual execution.
            model: Pydantic model associated with the execution unit.
            context: Runtime context at execution time.
            step_num: Step index for error reporting.
            check_num: Expectation index for error reporting.

        Returns:
            Result of the callable execution.

        Raises:
            AssertionError: Propagated as-is for pytest handling.
            DSLRuntimeError: Wrapped runtime exception with DSL context.
        """
        try:
            return executor()

        except AssertionError:
            raise

        except DSLRuntimeError as base:
            raise DSLRuntimeError.from_pydantic_model(
                model,
                message=base.message,
                context=context,
                filename=self.filename,
                check_num=check_num,
                step_num=step_num,
            ) from base

        except Exception as base:
            raise DSLRuntimeError.from_pydantic_model(
                model,
                message=f'{base!r}',
                context=context,
                filename=self.filename,
                check_num=check_num,
                step_num=step_num,
            ) from base

    def run_header(self) -> dict[str, 'Value']:
        """Execute the DSL header, if present.

        Returns:
            Mapping of values produced by the header execution.
        """
        if not self.header:
            return {}

        return self.run_callable(
            partial(self.header, self.params),
            model=self.header,
            step_num=0,
        )

    def run_check(self, check: 'BaseCheck',
                  context: dict[str, 'Value'],
                  step_num: int, check_num: int) -> bool:
        """Evaluate a single DSL expectation.

        Args:
            check: Expectation to evaluate.
            context: Execution context.
            step_num: Step index for error reporting.
            check_num: Expectation index for error reporting.

        Returns:
            Boolean result of the expectation.
        """
        self.reporter.enter_node(
            'check',
            title=check.title or f'Check {step_num + 1}.{check_num + 1}',
            description=check.description,
            context=context,
        )

        try:
            result = self.run_callable(
                partial(check, context),
                model=check,
                context=context,
                step_num=step_num,
                check_num=check_num,
            )

        except Exception as error:
            self.reporter.exit_node('check', error=error)
            raise
        else:
            self.reporter.exit_node('check')

        return result

    def run_checks(self, step: 'BaseAction',
                   context: dict[str, 'Value'],
                   step_num: int) -> None:
        """Execute checks from DSL action step.

        Args:
            step: Action to execute.
            context: Execution context.
            step_num: Step index for error reporting.
        """
        for check_num, _check in enumerate(step.expect):
            check = _check.root
            try:
                check_result = self.run_check(
                    check,
                    context,
                    step_num=step_num,
                    check_num=check_num,
                )
                if check_result is False:
                    raise AssertionError

            except AssertionError as base:
                raise self.fail(check, ErrorContext(
                    filename=self.filename,
                    step_num=step_num,
                    check_num=check_num,
                    context=context,
                    error=base,
                    element=check.model_dump(
                        exclude_defaults=False,
                        exclude_none=True,
                        exclude_unset=True,
                    ),
                )) from base

    def run_step(self, step: 'BaseAction',
                 context: dict[str, 'Value'],
                 step_num: int) -> dict[str, 'Value']:
        """Execute a single DSL action step.

        Args:
            step: Action to execute.
            context: Execution context.
            step_num: Step index for error reporting.

        Returns:
            Mapping of values produced by the action.
        """
        locals_ = ContextDict(deepcopy(context))

        results = self.run_callable(
            partial(step, locals_),
            model=step,
            context=locals_,
            step_num=step_num,
        )

        if isinstance(step, IncludeAction):
            results = self.include(step, results)

        locals_.update(results)

        exports: dict[str, Value] = self.run_callable(
            partial(locals_.resolve, step.export),  # type: ignore[arg-type]
            step,
            context=locals_,
            step_num=step_num,
        )

        locals_.update(exports)

        self.run_checks(
            step,
            locals_,
            step_num=step_num,
        )

        return exports

    def run_spec(self) -> dict[str, 'Value']:
        """Execute the full DSL specification.

        This includes:
        - header execution,
        - step execution,
        - include resolution,
        - export handling,
        - expectation evaluation.

        Returns:
            Final accumulated execution context.

        Raises:
            AssertionError: If any expectation fails.
            DSLRuntimeError: If runtime execution fails.
        """
        globals_ = self.run_header()

        for step_num, step in enumerate(self.steps):
            self.reporter.enter_node(
                'step',
                title=step.title or f'Step {step_num + 1}',
                description=step.description,
                context=globals_,
            )

            try:
                globals_.update(self.run_step(
                    step,
                    globals_,
                    step_num=step_num,
                ))

            except Exception as error:
                self.reporter.exit_node('step', error=error)
                raise
            else:
                self.reporter.exit_node('step')

        return globals_

    def include(self, step: IncludeAction, context: dict[str, 'Value']) -> dict[str, 'Value']:
        """Execute an included DSL template.

        Args:
            step: Include action describing the template to execute.
            context: Context passed to the included template.

        Returns:
            Mapping of the include output name to the resulting context.

        Raises:
            AssertionError: If any expectation fails.
            DSLRuntimeError: If parser is missing or template execution fails.
        """
        with step.filepath.open('rt', encoding='utf-8') as content:
            header, steps = self.parser.parse_file(content, expect='template')

        results = (
            TestPlan(header, steps, context, parent=self.parent)
            .run_spec()
        )

        return {step.output: results}

    def get_report_data(self) -> dict[str, 'Any']:
        """Get information for this item for test reports.

        Returns:
            Dictonary of parameters for report collector.
        """
        if not self.header:
            return {'title': self.parent.name}

        metadata = {}
        if isinstance(self.header, Case):
            metadata = self.header.metadata

        return {
            'title': self.header.title or self.parent.name,
            'description': self.header.description,
            'metadata': {
                'params': self.params,
                **metadata,
            },
        }

    @property
    def filename(self) -> str:
        """Return filename associated with this test plan."""
        if not self.parent:
            return '<unicode string>'

        return f'{self.parent.path}'

    def fail(self, check: 'BaseCheck',
             error: ErrorContext | None = None) -> DSLFailure:
        """Create an DSLFailure enriched with DSL context.

        Args:
            check: Expectation that failed.
            error: Error context at failure time.

        Returns:
            DSLFailure with message and context.
        """
        message = 'Expectation fail'
        if check.title:
            message += f': {check.title}'

        return DSLFailure(message, context=error)


class TestCase(pytest.Item):
    """Pytest item executing a single DSL test case.

    Execution is performed sequentially with explicit context
    propagation and validation of expectations.
    """

    __test__ = False

    def __init__(self, *,
                 header: 'Case | None',
                 steps:  tuple['BaseAction', ...],
                 params: dict[str, 'Value'],
                 **kwargs: 'Any') -> None:
        """Initialize a pytest test case backed by a DSL test plan.

        Args:
            header: Optional DSL case header.
            steps: Sequence of DSL steps.
            params: Initial execution parameters.
            **kwargs: Keyword pytest.Item arguments.
        """
        super().__init__(**kwargs)

        self.parser: DocumentParser = self.config.stash[PARSER]
        self.reporter: ReportAggregator = self.config.stash[REPORTER]

        self.plan = TestPlan(header, steps, params, parent=self)

    def runtest(self) -> None:
        """Execute the DSL test case."""
        self.reporter.enter_node('case', **self.plan.get_report_data())
        try:
            self.plan.run_spec()
        except Exception as error:
            self.reporter.exit_node('case', error=error)
            raise
        else:
            self.reporter.exit_node('case')

    def reportinfo(self) -> tuple['PathLike[str] | str', int | None, str]:
        """Get location information for this item for test reports.

        Returns:
            A tuple with three elements:
            - The path of the test (default ``self.path``)
            - The 0-based line number of the test (default ``None``)
            - A name of the test to be shown (default ``""``)
        """
        return self.path, None, self.name

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException],
                     style: 'Any' = None) -> 'Any':  # noqa: ANN401
        """Return a representation of a collection or test failure.

        Args:
            excinfo: Exception information for the failure.
            style: Traceback style.

        Returns:
            String or terminal representation for the error.
        """
        verbosity = self.config.get_verbosity()

        if verbosity < WRAP_VERBOSITY_LIMIT and isinstance(excinfo.value, DSLError):
            isatty = False
            if reporter := self.config.pluginmanager.get_plugin('terminalreporter'):
                isatty = bool(reporter.isatty)
            return excinfo.value.repr(isatty, verbosity)

        return super().repr_failure(excinfo, style)
