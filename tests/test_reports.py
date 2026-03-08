"""Test for reports aggregation."""

from pytest_loco.core import ReportAggregator


def test_report_tracing() -> None:
    """Collect tests tracing."""
    reporter = ReportAggregator()

    error = None
    try:
        raise AssertionError
    except Exception as e:
        error = e

    reporter.enter_node('case', title='Test 1')

    reporter.enter_node('step', title='Step 1.1')
    reporter.exit_node('step')

    reporter.exit_node('case')

    reporter.enter_node('case', title='Test 2')

    reporter.enter_node('step', title='Step 2.1')
    reporter.exit_node('step')

    reporter.enter_node('step', title='Step 2.2')

    reporter.enter_node('check', title='Check 2.2.1')
    reporter.exit_node('check')

    reporter.enter_node('check', title='Check 2.2.2')
    reporter.exit_node('check', error=error)

    reporter.exit_node('step', error=error)

    reporter.exit_node('case', error=error)

    expected = (
        '+ Test 1\r\n'
        '  + Step 1.1\r\n'
        '- Test 2\r\n'
        '  + Step 2.1\r\n'
        '  - Step 2.2\r\n'
        '    + Check 2.2.1\r\n'
        '    - Check 2.2.2\r\n'
    )

    assert expected == reporter.totals.get_content(isatty=False)
