"""Tests for errors outputs."""

from os import linesep
from typing import TYPE_CHECKING

import pytest

from pytest_loco.errors import ErrorContext, ErrorFormatter

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize('filename, line, column', (
    pytest.param('test.yaml', 1, 1, id='file with meta'),
    pytest.param(None, 1, 1, id='string with meta'),
    pytest.param('test.yaml', None, None, id='file without meta'),
    pytest.param(None, None, None, id='string without meta'),
))
def test_error_location(filename: str | None,
                        line: int | None, column: int | None,
                        mocker: 'MockerFixture') -> None:
    """Format error location."""
    value = ErrorFormatter.with_longrepr(
        message='Error',
        context=ErrorContext(
            filename=filename,
            line_num=line,
            column_num=column,
        ),
        isatty=False,
        verbosity=0,
    )

    assert value == 'Error'
    assert hasattr(value, 'toterminal')

    tw = mocker.Mock()

    expected = filename
    if not filename:
        expected = '<unicode string>'
    if line is not None and column is not None:
        expected += f':{line + 1}:{column + 1}'
    expected += f': ErrorFormatter{linesep}{linesep}Error{linesep}'

    value.toterminal(tw)
    tw.write.assert_called_with(expected)


def test_error_locals(mocker: 'MockerFixture') -> None:
    """Format error locals variables."""
    value = ErrorFormatter.with_longrepr(
        message='Error',
        context=ErrorContext(
            context={'test': True},
        ),
        isatty=False,
        verbosity=2,
    )

    assert value == 'Error'
    assert hasattr(value, 'toterminal')

    tw = mocker.Mock()

    value.toterminal(tw)
    tw.write.assert_called_with(
        f'<unicode string>: ErrorFormatter{linesep}{linesep}'
        f'Locals:{linesep}    test: true{linesep}{linesep}'
        f'Error{linesep}',
    )


def test_error_source(mocker: 'MockerFixture') -> None:
    """Format error source."""
    value = ErrorFormatter.with_longrepr(
        message='Error',
        context=ErrorContext(
            source='test: true',
        ),
        isatty=False,
        verbosity=2,
    )

    assert value == 'Error'
    assert hasattr(value, 'toterminal')

    tw = mocker.Mock()

    value.toterminal(tw)
    tw.write.assert_called_with(
        f'<unicode string>: ErrorFormatter{linesep}{linesep}'
        f'Source:{linesep}    test: true{linesep}{linesep}'
        f'Error{linesep}',
    )


def test_error_element_source(mocker: 'MockerFixture') -> None:
    """Format error element source."""
    value = ErrorFormatter.with_longrepr(
        message='Error',
        context=ErrorContext(
            element={'test': True},
        ),
        isatty=False,
        verbosity=2,
    )

    assert value == 'Error'
    assert hasattr(value, 'toterminal')

    tw = mocker.Mock()

    value.toterminal(tw)
    tw.write.assert_called_with(
        f'<unicode string>: ErrorFormatter{linesep}{linesep}'
        f'Source:{linesep}    test: true{linesep}{linesep}'
        f'Error{linesep}',
    )


def test_error_markup(mocker: 'MockerFixture') -> None:
    """Format error markup."""
    value = ErrorFormatter.with_longrepr(
        message='Error',
        context=ErrorContext(
            filename='test.yaml',
            line_num=0,
            column_num=0,
            element={'test': True},
        ),
        isatty=True,
        verbosity=2,
    )

    assert value == 'Error'
    assert hasattr(value, 'toterminal')

    tw = mocker.Mock()

    value.toterminal(tw)
    tw.write.assert_called_with(
        f'\x1b[1m\x1b[31mtest.yaml:1:1:\x1b[0m ErrorFormatter{linesep}{linesep}'
        f'Source:{linesep}\x1b[0m\x1b[90m    '
        '\x1b[39;49;00m\x1b[94mtest\x1b[39;49;00m:\x1b[90m '
        f'\x1b[39;49;00mtrue\x1b[90m\x1b[39;49;00m{linesep}{linesep}'
        f'Error{linesep}',
    )
