"""Tests for instruction loading and execution."""

from datetime import date, datetime, timedelta
from re import match
from typing import TYPE_CHECKING

import pydantic
import pytest
import yaml

from pytest_loco.builtins.instructions import variable_constructor
from pytest_loco.core import DocumentParser
from pytest_loco.errors import DSLRuntimeError, DSLSchemaError, PluginError, PluginWarning
from pytest_loco.extensions import ContentDecoder, ContentEncoder, ContentType, Instruction
from tests.examples.contents import base64_decoder, base64_encoder

if TYPE_CHECKING:
    from collections.abc import Callable
    from re import Pattern

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem
    from pytest_mock import MockType


def test_content_type_without_decoders(patch_entrypoints: 'Callable[..., MockType]',
                                       loader: type[yaml.SafeLoader]) -> None:
    """Verify content types defined with encoder only."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.add_content_type(ContentType(name='base64', encoder=base64_encoder))
    parser.attach()

    contents = '!dump\n  format: base64\n  source: !var value\n'
    b64_encoder_content = yaml.load(contents, Loader=loader)

    assert callable(b64_encoder_content)
    assert b64_encoder_content({'value': b'some bytes\00'}) == 'c29tZSBieXRlcwA='


def test_content_type_without_encoders(patch_entrypoints: 'Callable[..., MockType]',
                                       loader: type[yaml.SafeLoader]) -> None:
    """Verify content types defined with decoder only."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.add_content_type(ContentType(name='bytes', decoder=base64_decoder))
    parser.attach()

    contents = '!load\n  format: bytes\n  source: !var value\n'
    b64_decoder_content = yaml.load(contents, Loader=loader)

    assert callable(b64_decoder_content)
    assert b64_decoder_content({'value': 'c29tZSBieXRlcwA='}) == b'some bytes\00'


def test_content_type_decoder_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                        loader: type[yaml.SafeLoader]) -> None:
    """Verify decoder shadowing for content types."""
    patch_entrypoints()

    f1 = lambda val, ctx: val + 1  # noqa: E731, ARG005
    f2 = lambda val, ctx: val + 2  # noqa: E731, ARG005

    parser = DocumentParser(loader, auto_attach=False)
    parser.add_content_type(ContentType(name='test', decoder=ContentDecoder(decoder=f1)))

    with pytest.warns(PluginWarning, match=r'is shadowing an existing$'):
        parser.add_content_type(ContentType(name='test', decoder=ContentDecoder(decoder=f2)))

    parser.attach()

    contents = '!load\n  format: test\n  source: !var value\n'
    decoder = yaml.load(contents, Loader=loader)

    assert callable(decoder)
    assert decoder({'value': 40}) == f2(40, None)


def test_content_type_decoder_strict_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                               loader: type[yaml.SafeLoader]) -> None:
    """Verify decoder deny shadowing for content types with strict mode."""
    patch_entrypoints()

    f1 = lambda val, ctx: val + 1  # noqa: E731, ARG005

    parser = DocumentParser(loader, strict=True, auto_attach=False)
    parser.add_content_type(ContentType(name='test', decoder=ContentDecoder(decoder=f1)))

    with pytest.raises(PluginError, match=r'is shadowing an existing$'):
        parser.add_content_type(ContentType(name='test', decoder=ContentDecoder(decoder=f1)))


def test_content_type_encoder_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                        loader: type[yaml.SafeLoader]) -> None:
    """Verify encoder shadowing for content types."""
    patch_entrypoints()

    f1 = lambda val, ctx: val + 1  # noqa: E731, ARG005
    f2 = lambda val, ctx: val + 2  # noqa: E731, ARG005

    parser = DocumentParser(loader, auto_attach=False)
    parser.add_content_type(ContentType(name='test', encoder=ContentEncoder(encoder=f1)))

    with pytest.warns(PluginWarning, match=r'is shadowing an existing$'):
        parser.add_content_type(ContentType(name='test', encoder=ContentEncoder(encoder=f2)))

    parser.attach()

    contents = '!dump\n  format: test\n  source: !var value\n'
    encoder = yaml.load(contents, Loader=loader)

    assert callable(encoder)
    assert encoder({'value': 40}) == f2(40, None)


def test_content_type_encoder_strict_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                               loader: type[yaml.SafeLoader]) -> None:
    """Verify encoder deny shadowing for content types with strict mode."""
    patch_entrypoints()

    f1 = lambda val, ctx: val + 1  # noqa: E731, ARG005

    parser = DocumentParser(loader, strict=True, auto_attach=False)
    parser.add_content_type(ContentType(name='test', encoder=ContentEncoder(encoder=f1)))

    with pytest.raises(PluginError, match=r'is shadowing an existing$'):
        parser.add_content_type(ContentType(name='test', encoder=ContentEncoder(encoder=f1)))


def test_instructions_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                loader: type[yaml.SafeLoader]) -> None:
    """Verify instruction shadowing."""
    patch_entrypoints()

    def shadow_var(*args, **kwargs):
        resolver = variable_constructor(*args, **kwargs)
        def wrapper(ctx):
            return resolver(ctx) + 1
        return wrapper

    parser = DocumentParser(loader, auto_attach=False)

    with pytest.warns(PluginWarning, match=r'is shadowing an existing$'):
        parser.add_instruction(Instruction(name='var', constructor=shadow_var))

    parser.attach()

    builtin_shadow = yaml.load('!var value\n', Loader=loader)

    assert callable(builtin_shadow)
    assert builtin_shadow({'value': 41}) == 41 + 1


def test_instructions_strict_shadowing(patch_entrypoints: 'Callable[..., MockType]',
                                       loader: type[yaml.SafeLoader]) -> None:
    """Verify instruction deny shadowing with strict mode."""
    patch_entrypoints()

    def shadow_var(*args, **kwargs):
        resolver = variable_constructor(*args, **kwargs)
        def wrapper(ctx):
            return resolver(ctx) + 1
        return wrapper

    parser = DocumentParser(loader, strict=True, auto_attach=False)

    with pytest.raises(PluginError, match=r'is shadowing an existing$'):
        parser.add_instruction(Instruction(name='var', constructor=shadow_var))


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!var 42', r'^Invalid variable path', id='number'),
    pytest.param('!var {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!var\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!var []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!var\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_variable_resolver_with_invalid_path_type(value: str, except_message: 'Pattern',
                                                  patch_entrypoints: 'Callable[..., MockType]',
                                                  loader: type[yaml.SafeLoader]) -> None:
    """Verify failure of builtin variable resolver on invalid path types."""
    patch_entrypoints()

    DocumentParser(loader)

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_lambda_resolver_evaluate(patch_entrypoints: 'Callable[..., MockType]',
                                  loader: type[yaml.SafeLoader]) -> None:
    """Evaluate a valid lambda resolver loaded from YAML."""
    patch_entrypoints()

    DocumentParser(loader, allow_lambda=True)

    resolver = yaml.load('!lambda value + 1\n', Loader=loader)

    assert callable(resolver)
    assert resolver({'value': 41}) == 41 + 1


def test_lambda_resolver_default_disabled(patch_entrypoints: 'Callable[..., MockType]',
                                          loader: type[yaml.SafeLoader]) -> None:
    """Evaluate a valid lambda resolver not loaded from YAML if not allowed."""
    patch_entrypoints()

    DocumentParser(loader)

    with pytest.raises(yaml.error.MarkedYAMLError, match=(r'could not determine a constructor for the tag')):
        yaml.load('!lambda value + 1\n', Loader=loader)


@pytest.mark.parametrize('body', (
    pytest.param('value + unknown', id='name error'),
    pytest.param('value + math.sin(value)', id='some from exrernal module'),
    pytest.param('abs(value)', id='some from builtins'),
    pytest.param('value + "string"', id='type error'),
    pytest.param('value.__class__', id='introspection', marks=pytest.mark.xfail),
))
def test_lambda_resolver_evaluate_fail(body: str,
                                       patch_entrypoints: 'Callable[..., MockType]',
                                       loader: type[yaml.SafeLoader]) -> None:
    """Fail evaluation of a lambda resolver at runtime."""
    patch_entrypoints()

    DocumentParser(loader, allow_lambda=True)

    resolver = yaml.load(f'!lambda {body}', Loader=loader)

    assert callable(resolver)

    with pytest.raises(DSLRuntimeError, match=r'^Error during lambda expression evaluation$'):
        resolver({'value': 41})


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!lambda {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!lambda\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!lambda []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!lambda\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_lambda_resolver_content(value: str, except_message: 'Pattern',
                                         patch_entrypoints: 'Callable[..., MockType]',
                                         loader: type[yaml.SafeLoader]) -> None:
    """Reject invalid lambda node during YAML construction."""
    patch_entrypoints()

    DocumentParser(loader, allow_lambda=True)

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


@pytest.mark.parametrize('body', (
    pytest.param('value++', id='c-style increment'),
    pytest.param('for i in range(10): pass', id='imperative for loop'),
    pytest.param('(def func(): pass)', id='function definition'),
    pytest.param('import os', id='import statement'),
    pytest.param('return value', id='return statement'),
))
def test_invalid_lambda_resolver_evaluate(body: str,
                                          patch_entrypoints: 'Callable[..., MockType]',
                                          loader: type[yaml.SafeLoader]) -> None:
    """Reject invalid lambda syntax during YAML construction."""
    patch_entrypoints()

    DocumentParser(loader, allow_lambda=True)

    with pytest.raises(DSLSchemaError, match=r'Invalid syntax for lambda body'):
        yaml.load(f'!lambda {body}', Loader=loader)


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!secret 42', r'^Invalid secret variable path', id='number'),
    pytest.param('!secret {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!secret\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!secret []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!secret\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_secret_resolver_with_invalid_path_type(value: str, except_message: 'Pattern',
                                                 patch_entrypoints: 'Callable[..., MockType]',
                                                 loader: type[yaml.SafeLoader]) -> None:
    """Verify failure of builtin secret variable resolver on invalid path types."""
    patch_entrypoints()

    DocumentParser(loader)

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_secret_resolver_evaluate(patch_entrypoints: 'Callable[..., MockType]',
                                  loader: type[yaml.SafeLoader]) -> None:
    """Evaluate a valid sercret variable resolver loaded from YAML."""
    patch_entrypoints()

    DocumentParser(loader)

    context = {'value': pydantic.SecretStr('secret')}

    resolver = yaml.load('!var value\n', Loader=loader)

    assert callable(resolver)
    assert match(r'^\*+$', str(resolver(context))) is not None

    resolver = yaml.load('!secret value\n', Loader=loader)

    assert callable(resolver)
    assert resolver(context) == 'secret'


def test_valid_date(patch_entrypoints: 'Callable[..., MockType]',
                    loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid date."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    contents = '!date 2020-01-01\n'
    resolved_value = yaml.load(contents, Loader=loader)

    assert type(resolved_value) is date
    assert resolved_value == date(2020, 1, 1)


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!date NOW', r'Invalid date format', id='incorrect value'),
    pytest.param('!date 2020', r'Invalid date format', id='partial value'),
    pytest.param('!date 2020-01-01T00:00:00', r'Invalid date format', id='datetime'),
    pytest.param('!date {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!date\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!date []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!date\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_date(value: str, except_message: 'Pattern',
                      patch_entrypoints: 'Callable[..., MockType]',
                      loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid date."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_valid_datetime(patch_entrypoints: 'Callable[..., MockType]',
                        loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid datetime."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    contents = '!datetime 2020-01-01T00:00:00\n'
    resolved_value = yaml.load(contents, Loader=loader)

    assert type(resolved_value) is datetime
    assert resolved_value == datetime(2020, 1, 1, 0, 0, 0)


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!datetime NOW', r'Invalid datetime format', id='incorrect value'),
    pytest.param('!datetime 2020', r'Invalid datetime format', id='partial value'),
    pytest.param('!datetime {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!datetime\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!datetime []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!datetime\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_datetime(value: str, except_message: 'Pattern',
                          patch_entrypoints: 'Callable[..., MockType]',
                          loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid datetime."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_valid_timedelta(patch_entrypoints: 'Callable[..., MockType]',
                         loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid timedelta."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    resolved_int = yaml.load('!timedelta 10\n', Loader=loader)

    assert type(resolved_int) is timedelta
    assert resolved_int.total_seconds() == float('10.0')

    resolved_float = yaml.load('!timedelta 10.6\n', Loader=loader)

    assert type(resolved_float) is timedelta
    assert resolved_float.total_seconds() == float('10.6')


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!timedelta NOW', r'Invalid timedelta format', id='incorrect value'),
    pytest.param('!timedelta {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!timedelta\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!timedelta []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!timedelta\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_timedelta(value: str, except_message: 'Pattern',
                           patch_entrypoints: 'Callable[..., MockType]',
                           loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid timedelta."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


@pytest.mark.parametrize('value', (
    pytest.param('42Y', id='int year'),
    pytest.param('5.42Y', id='float year'),
    pytest.param('42m', id='int month'),
    pytest.param('5.42m', id='float month'),
    pytest.param('42w', id='int week'),
    pytest.param('5.42w', id='float week'),
    pytest.param('42d', id='int day'),
    pytest.param('5.42d', id='float day'),
    pytest.param('42H', id='int hour'),
    pytest.param('5.42H', id='float hour'),
    pytest.param('42h', id='int lowercase hour'),
    pytest.param('5.42h', id='float lowercase hour'),
    pytest.param('42M', id='int minute'),
    pytest.param('5.42M', id='float minute'),
    pytest.param('42S', id='int second'),
    pytest.param('5.42S', id='float second'),
    pytest.param('42s', id='int lowercase second'),
    pytest.param('5.42s', id='float lowercase second'),
))
def test_valid_duration(value: str,
                        patch_entrypoints: 'Callable[..., MockType]',
                        loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid duration."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    resolved_positive = yaml.load(f'!duration {value}\n', Loader=loader)

    assert type(resolved_positive) is timedelta

    resolved_negative = yaml.load(f'!duration -{value}\n', Loader=loader)

    assert type(resolved_negative) is timedelta
    assert resolved_positive.total_seconds() == -resolved_negative.total_seconds()


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!duration NOW', r'Invalid duration value', id='incorrect value'),
    pytest.param('!duration {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!duration\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!duration []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!duration\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_duration(value: str, except_message: 'Pattern',
                          patch_entrypoints: 'Callable[..., MockType]',
                          loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid duration."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_valid_base64(patch_entrypoints: 'Callable[..., MockType]',
                      loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid base64-encoded binary data."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    content_padding = '!base64 c29tZSBieXRlcwA=\n'
    resolved_padding = yaml.load(content_padding, Loader=loader)

    assert resolved_padding == b'some bytes\00'

    content_relaxed = '!base64 c29tZSBieXRlcwA\n'
    resolved_relaxed = yaml.load(content_relaxed, Loader=loader)

    assert resolved_relaxed == b'some bytes\00'


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!base64 $$', r'Invalid base64', id='incorrect value'),
    pytest.param('!base64 {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!base64\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!base64 []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!base64\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_base64(value: str, except_message: 'Pattern',
                        patch_entrypoints: 'Callable[..., MockType]',
                        loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid base64-encoded binary data."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_valid_binhex(patch_entrypoints: 'Callable[..., MockType]',
                      loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid hexadecimal-encoded binary data."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    content_simple = '!binaryHex 736f6d6520627974657300'
    resolved_simple = yaml.load(content_simple, Loader=loader)

    assert resolved_simple == b'some bytes\00'

    content_pretty = '''!binaryHex >
    73 6f 6d 65 20
    62 79 74 65 73
    00'''
    resolved_pretty = yaml.load(content_pretty, Loader=loader)

    assert resolved_pretty == b'some bytes\00'


@pytest.mark.parametrize('value, except_message', (
    pytest.param('!binaryHex SOME VALUE', r'Invalid hexadecimal', id='incorrect value'),
    pytest.param('!binaryHex 0 1f', r'Invalid hexadecimal', id='wrong padded value'),
    pytest.param('!binaryHex {key: value}', r'expected a scalar node, but found mapping', id='mapping inline'),
    pytest.param('!binaryHex\n  key: value', r'expected a scalar node, but found mapping', id='mapping'),
    pytest.param('!binaryHex []', r'expected a scalar node, but found sequence', id='list inline'),
    pytest.param('!binaryHex\n  - 1\n  - 2', r'expected a scalar node, but found sequence', id='list'),
))
def test_invalid_binhex(value: str, except_message: 'Pattern',
                        patch_entrypoints: 'Callable[..., MockType]',
                        loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid hexadecimal-encoded binary data."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    with pytest.raises(DSLSchemaError, match=except_message):
        yaml.load(value, Loader=loader)


def test_valid_text_file(fs: 'FakeFilesystem',
                         patch_entrypoints: 'Callable[..., MockType]',
                         loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid text data from file."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    file_ = fs.create_file('test.txt')
    file_.set_contents('some text')

    content_simple = '!textFile test.txt'
    resolved_simple = yaml.load(content_simple, Loader=loader)

    assert resolved_simple == 'some text'


def test_invalid_text_file(patch_entrypoints: 'Callable[..., MockType]',
                           loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid text file."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    content = '!textFile test.txt'

    with pytest.raises(DSLRuntimeError, match=r'File not found'):
        yaml.load(content, Loader=loader)


def test_valid_binary_file(fs: 'FakeFilesystem',
                         patch_entrypoints: 'Callable[..., MockType]',
                         loader: type[yaml.SafeLoader]) -> None:
    """Verify a valid binary data from file."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    file_ = fs.create_file('test.bin')
    file_.set_contents(b'some data')

    content_simple = '!binaryFile test.bin'
    resolved_simple = yaml.load(content_simple, Loader=loader)

    assert resolved_simple == b'some data'


def test_invalid_binary_file(patch_entrypoints: 'Callable[..., MockType]',
                           loader: type[yaml.SafeLoader]) -> None:
    """Verify an invalid binary file."""
    patch_entrypoints()

    parser = DocumentParser(loader, auto_attach=False)
    parser.attach()

    content = '!textFile test.bin'

    with pytest.raises(DSLRuntimeError, match=r'File not found'):
        yaml.load(content, Loader=loader)
