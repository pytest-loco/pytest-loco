"""Tests for declarative content formats."""

import pytest

from pytest_loco.builtins.lookups import VariableLookup
from pytest_loco.extensions import Attribute, ContentDecoder, ContentEncoder, ContentTransformer, Schema
from tests.examples.contents import json_decode, json_encode


def test_declarative_decoder() -> None:
    """Verify basic declarative decoder behavior."""
    model = ContentDecoder(decoder=json_decode).build('simpleJSON')

    instance = model.model_validate({
        'format': 'simpleJSON',
        'source': '{"value": 42}',
    })

    assert instance.root({}) == {'value': 42}


def test_declarative_decoder_with_transform() -> None:
    """Verify decoder behavior with chained transformers."""
    decoder = ContentDecoder(
        decoder=json_decode,
        transformers=[
            ContentTransformer(
                transformer=lambda val, params: {
                    'value': val['value'] + params['inc'],
                },
                name='inc',
                field=Attribute(
                    base=int,
                    default=1,
                ),
            ),
            ContentTransformer(
                transformer=lambda val, params: {
                    'value': val['value'] * params['mul'],
                },
                name='mul',
                field=Attribute(
                    base=int,
                    aliases=['mul', 'miltiply'],
                    default=1,
                ),
            ),
        ],
    )

    model = decoder.build('mathJSON')

    simple = model.model_validate({
        'format': 'mathJSON',
        'source': '{"value": 42}',
    })

    assert simple.root({}) == {'value': 42}

    increment = model.model_validate({
        'format': 'mathJSON',
        'source': '{"value": 42}',
        'inc': 5,
    })

    assert increment.root({}) == {'value': 47}

    multiply = model.model_validate({
        'format': 'mathJSON',
        'source': '{"value": 42}',
        'mul': 2,
    })

    assert multiply.root({}) == {'value': 84}


def test_non_unique_transforms_name() -> None:
    """Ensure transformer names must be unique."""
    inc = ContentTransformer(
        transformer=lambda val, params: {
            'value': val['value'] + params['inc'],
        },
        name='inc',
        field=Attribute(
            base=int,
            default=1,
        ),
    )
    increment = ContentTransformer(
        transformer=lambda val, params: {
            'value': val['value'] + params['inc'],
        },
        name='inc',
        field=Attribute(
            base=int,
            default=1,
        ),
    )

    decoder = ContentDecoder(
        decoder=json_decode,
        transformers=[
            inc,
            increment,
        ],
    )

    with pytest.raises(ValueError, match=r'is not unique in schema$'):
        decoder.build('failedJSON')


def test_non_unique_transforms_aliases() -> None:
    """Ensure transformer aliases do not conflict."""
    inc = ContentTransformer(
        transformer=lambda val, params: {
            'value': val['value'] + params['inc'],
        },
        name='inc',
        field=Attribute(
            base=int,
            default=1,
        ),
    )
    increment = ContentTransformer(
        transformer=lambda val, params: {
            'value': val['value'] + params['inc'],
        },
        name='increment',
        field=Attribute(
            base=int,
            aliases=['increment', 'inc'],
            default=1,
        ),
    )

    decoder = ContentDecoder(
        decoder=json_decode,
        transformers=[
            inc,
            increment,
        ],
    )

    with pytest.raises(ValueError, match=r'is not unique in schema$'):
        decoder.build('failedJSON')


def test_declarative_encoder() -> None:
    """Verify declarative encoder behavior with parameters."""
    model = ContentEncoder(
        encoder=json_encode,
        parameters=Schema(
            indent=Attribute(
                base=str | int | None,
                title='Indent',
                default=None,
            ),
            sort_keys=Attribute(
                base=bool,
                aliases=['sortKeys'],
                title='Sort keys flag',
                default=False,
            ),
        ),
    ).build('simpleJSON')

    instance = model.model_validate({
        'format': 'simpleJSON',
        'sortKeys': True,
        'source': {
            'var': VariableLookup('someVar'),
            'value': 42,
        },
    })

    assert instance.root({'someVar': 69}) == '{"value": 42, "var": 69}'
