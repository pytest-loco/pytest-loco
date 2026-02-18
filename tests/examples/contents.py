"""Examples of ContentType definitions.

This module demonstrates how to define custom content types for
pytest-loco using declarative encoders and decoders.

The examples include:
- JSON content type with configurable encoding parameters,
- Base64 content type for binary data encoding and decoding.

These implementations are intended for demonstration and reference
purposes rather than production use.
"""

from base64 import b64decode, b64encode
from json import dumps, loads
from typing import TYPE_CHECKING

from pytest_loco.extensions import Attribute, ContentDecoder, ContentEncoder, ContentType, Schema

if TYPE_CHECKING:
    from pytest_loco.context import Value


def json_decode(value: str, params: dict) -> 'Value':
    """Decode JSON string into a Python object.

    Args:
        value: JSON string to decode.
        params: Additional keyword arguments passed directly to `json.loads`.

    Returns:
        Decoded Python object.
    """
    return loads(value, **params)


def json_encode(value: 'Value', params: dict) -> str:
    """Encode Python object into a JSON string.

    Args:
        value: Python object to serialize.
        params: Additional keyword arguments passed directly to `json.dumps`.

    Returns:
        JSON string representation of the value.
    """
    return dumps(value, **params)


def b64_decode(value: str, params: dict) -> bytes:
    """Decode Base64-encoded value.

    Args:
        value: Base64-encoded string.
        params: Additional keyword arguments passed to `base64.b64decode`.

    Returns:
        Decoded bytes.
    """
    return b64decode(value, **params)


def b64_encode(value: bytes, params: dict) -> str:
    """Encode bytes into a Base64 string.

    This encoder intentionally supports only `bytes` input and is
    simplified for demonstration purposes.

    Args:
        value: Bytes to encode.
        params: Additional keyword arguments passed to `base64.b64encode`.

    Returns:
        Base64-encoded string if input is bytes, otherwise `None`.
    """
    if isinstance(value, bytes):
        return b64encode(value, **params).decode()


json_decoder = ContentDecoder(
    decoder=json_decode,
)

json_encoder = ContentEncoder(
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
)

json = ContentType(
    name='json',
    decoder=json_decoder,
    encoder=json_encoder,
)

base64_decoder = ContentDecoder(
    decoder=b64_decode,
)

base64_encoder = ContentEncoder(
    encoder=b64_encode,
)

base64 = ContentType(
    name='base64',
    decoder=base64_decoder,
    encoder=base64_encoder,
)
