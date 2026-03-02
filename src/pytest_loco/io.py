"""Terminal output utilities with ANSI markup and syntax highlighting support.

The writer is designed for deterministic output formatting and supports
both TTY and non-TTY environments.
"""

import io
import os
import sys
import types
import typing

from colorama.ansitowin32 import AnsiToWin32, StreamWrapper
from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound


class TerminalStr(str):
    """Base class for string objects with custom terminal rendering behavior.

    Subclasses must implement :meth:`toterminal` to define how the
    string should be written to a :class:`TerminalWriter`.

    This allows domain-specific rendering logic to be embedded directly
    into string-like objects.
    """

    def toterminal(self, tw: typing.Any) -> None:  # noqa: ANN401
        """Render the string into the provided terminal writer.

        Args:
            tw: The target terminal writer instance.
        """
        raise NotImplementedError


class TerminalWriter:
    """Buffered terminal writer with ANSI markup and syntax highlighting."""

    _color_codes = types.MappingProxyType({
        'black': 30,
        'red': 31,
        'green': 32,
        'yellow': 33,
        'blue': 34,
        'purple': 35,
        'cyan': 36,
        'white': 37,
        'Black': 40,
        'Red': 41,
        'Green': 42,
        'Yellow': 43,
        'Blue': 44,
        'Purple': 45,
        'Cyan': 46,
        'White': 47,
        'bold': 1,
        'light': 2,
        'blink': 5,
        'invert': 7,
    })

    def __init__(self, tty: bool = False) -> None:
        """Initialize the terminal writer.

        Args:
            tty: Whether the output should be treated as a TTY.
                Enables markup if environment permits.
        """
        self._value = io.StringIO()
        self._file: io.TextIOBase | StreamWrapper = self._value

        self._win32 = sys.platform == 'win32'
        self._isatty = tty

        self.code_highlight = True

        if tty and self._win32:
            wrapper = AnsiToWin32(self._value, strip=False)
            if wrapper.stream is not None:
                self._file = wrapper.stream

    def content(self) -> str:
        """Return the buffered terminal output.

        Returns:
            The accumulated output as a string.
        """
        return self._value.getvalue()

    @property
    def has_markup(self) -> bool:
        """Determine whether ANSI markup should be enabled.

        The decision is based on:

        - Environment variables (PY_COLORS, NO_COLOR, FORCE_COLOR).
        - TTY detection.
        - Terminal type.

        Returns:
            True if ANSI markup should be applied, False otherwise.
        """
        if os.environ.get('PY_COLORS') == '1':
            return True
        if os.environ.get('PY_COLORS') == '0':
            return False
        if os.environ.get('NO_COLOR'):
            return False
        if os.environ.get('FORCE_COLOR'):
            return True

        return self._isatty and os.environ.get('TERM') != 'dumb'

    def markup(self, text: str, **markup: bool) -> str:
        """Apply ANSI markup to the given text.

        Supported styles include foreground colors, background colors,
        and text modifiers such as bold or blink.

        Args:
            text: The input text.
            **markup: Keyword flags enabling specific styles.

        Returns:
            The styled text if markup is enabled, otherwise the original text.
        """
        if not self.has_markup or not markup:
            return text

        markup_colors = ''.join(
            f'\x1b[{self._color_codes[name]}m'
            for name, enabled in markup.items()
            if enabled and name in self._color_codes
        )

        return f'{markup_colors}{text}\x1b[0m'

    def lines(self, text: str = '', **markup: bool) -> None:
        """Write multiple lines to the terminal.

        Args:
            text: Multi-line text to write.
            **markup: ANSI style flags applied to each line.
        """
        for line in text.splitlines():
            self.line(line, **markup)

    def line(self, text: str = '', **markup: bool) -> None:
        """Write a single line to the terminal.

        Args:
            text: The text to write.
            **markup: ANSI style flags applied to the line.
        """
        if not text:
            return

        self.write(f'{text}{os.linesep}', **markup)

    def write(self, text: str = '', **markup: bool) -> None:
        """Write raw text to the terminal buffer.

        Applies ANSI markup if enabled and handles encoding issues
        gracefully.

        Args:
            text: The text to write.
            **markup: ANSI style flags applied to the text.
        """
        value = self.markup(text, **markup)

        try:
            self._file.write(value)
        except UnicodeEncodeError:
            self._file.write(value.encode('unicode-escape').decode('ascii'))

    def source(self, text: str = '', lang: str = 'yaml') -> None:
        """Write syntax-highlighted source code to the terminal.

        Highlighting is applied only if markup and code highlighting
        are enabled. Theme and background mode can be configured via
        environment variables.

        Args:
            text: The source code.
            lang: The lexer language name for Pygments.
        """
        if not self.has_markup or not self.code_highlight:
            self.lines(text)
            return

        theme = os.environ.get('PYTEST_THEME')
        if not theme:
            theme = 'default'
        else:
            try:
                get_style_by_name(theme)
            except ClassNotFound:
                theme = 'default'

        mode = os.environ.get('PYTEST_THEME_MODE')
        if mode not in ('light', 'dark'):
            mode = 'dark'

        formatter = TerminalFormatter(bg=mode, style=theme)

        try:
            lexer = get_lexer_by_name(lang)
        except ClassNotFound:
            self.lines(text)
            return

        self.lines('\x1b[0m' + highlight(text, lexer, formatter))
