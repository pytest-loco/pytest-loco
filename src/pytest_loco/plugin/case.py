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
from pytest_loco.errors import DSLError, DSLRuntimeError, ErrorContext
from pytest_loco.schema.actions import IncludeAction

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

if TYPE_CHECKING:
    from pydantic import BaseModel

if TYPE_CHECKING:
    from pytest_loco.core import DocumentParser, Header, Step
    from pytest_loco.schema import BaseAction, BaseCheck, Case
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
                 params: dict[str, 'Value'], *,
                 parent: pytest.Item | None = None,
                 parser: 'DocumentParser | None' = None) -> None:
        """Initialize a test execution plan.

        Args:
            header: Optional DSL header (case-level action).
            steps: Ordered sequence of DSL steps.
            params: Initial parameter context.
            parent: Optional pytest item owning this plan.
            parser: Parser used to resolve included templates.
        """
        self.header = header
        self.steps = steps
        self.params = params

        self.parent = parent
        self.parser = parser

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

    def run_step(self, step: 'BaseAction', context: dict[str, 'Value'], *,
                 step_num: int | None = None) -> dict[str, 'Value']:
        """Execute a single DSL action step.

        Args:
            step: Action to execute.
            context: Execution context.
            step_num: Step index for error reporting.

        Returns:
            Mapping of values produced by the action.
        """
        return self.run_callable(
            partial(step, context),
            model=step,
            context=context,
            step_num=step_num,
        )

    def run_check(self, check: 'BaseCheck', context: dict[str, 'Value'], *,
                  step_num: int | None = None,
                  check_num: int | None = None) -> bool:
        """Evaluate a single DSL expectation.

        Args:
            check: Expectation to evaluate.
            context: Execution context.
            step_num: Step index for error reporting.
            check_num: Expectation index for error reporting.

        Returns:
            Boolean result of the expectation.
        """
        return self.run_callable(
            partial(check, context),
            model=check,
            context=context,
            step_num=step_num,
            check_num=check_num,
        )

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
            locals_ = ContextDict(deepcopy(globals_))

            results = self.run_step(
                step,
                locals_,
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

            for check_num, _check in enumerate(step.expect):
                check = _check.root
                try:
                    check_result = self.run_check(
                        check,
                        locals_,
                        step_num=step_num,
                        check_num=check_num,
                    )
                    if check_result is False:
                        raise AssertionError

                except AssertionError as base:
                    raise self.fail(
                        check,
                        locals_,
                        step_num=step_num,
                        check_num=check_num,
                    ) from base

            globals_.update(exports)

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
        if not self.parser:
            raise DSLRuntimeError('missing parser')

        with step.filepath.open('rt', encoding='utf-8') as content:
            header, steps = self.parser.parse_file(content, expect='template')

        subplan = TestPlan(
            header,
            steps,
            context,
            parent=self.parent,
            parser=self.parser,
        )

        return {step.output: subplan.run_spec()}

    @property
    def filename(self) -> str:
        """Return filename associated with this test plan."""
        if not self.parent:
            return '<unicode string>'

        return f'{self.parent.path}'

    def fail(self, check: 'BaseCheck',
             context: dict[str, 'Value'],
             step_num: int | None = None,
             check_num: int | None = None) -> AssertionError:
        """Create an AssertionError enriched with DSL context.

        Args:
            check: Expectation that failed.
            context: Execution context at failure time.
            step_num: Index of the step.
            check_num: Index of the expectation.

        Returns:
            AssertionError with formatted DSL error message.
        """
        error_context = ErrorContext(
            filename=self.filename,
            step_num=step_num,
            check_num=check_num,
            context=context,
            element=check.model_dump(
                exclude_none=True,
                exclude_unset=True,
            ),
        )

        message = 'Expectation fail'
        if check.title:
            message += f': {check.title}'

        return AssertionError(DSLError.format(message, error_context))


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
                 parser: 'DocumentParser',
                 **kwargs: 'Any') -> None:
        """Initialize a pytest test case backed by a DSL test plan.

        Args:
            header: Optional DSL case header.
            steps: Sequence of DSL steps.
            params: Initial execution parameters.
            parser: DSL document parser.
            **kwargs: Keyword pytest.Item arguments.
        """
        super().__init__(**kwargs)

        self.plan = TestPlan(
            header,
            steps,
            params,
            parent=self,
            parser=parser,
        )

    def runtest(self) -> None:
        """Execute the DSL test case."""
        self.plan.run_spec()
