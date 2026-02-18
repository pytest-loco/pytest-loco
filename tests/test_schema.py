"""Tests for schema and attribute definitions."""

from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal, Optional

import pydantic
import pytest

from pytest_loco.extensions import Attribute, Schema

type TestTypeAlias = Callable[[int], int]
type TestGenericAlias[T] = Callable[[T], T]

AVAILABLE_BASES = (
    str,
    Literal['allow', 'ignore', 'forbid'],
    Annotated[str, 'annotation'],
    Optional[int],  # noqa: UP045
    Any,
    int | float,
    dict[str, str],
    Mapping[str, Any],
    Callable[[int], int],
    TestTypeAlias,
    TestGenericAlias[int],
)


@pytest.mark.parametrize('base', tuple(
    pytest.param(base, id=f'{base!r}:{type(base)!r}')
    for base in AVAILABLE_BASES
))
def test_attribute_types(base: Any) -> None:
    """Allow extended types in attribute base definitions."""
    Schema(indent=Attribute(base=base, default=None))


def test_base_schema() -> None:
    """Create base schema."""
    schema = Schema(
        label=Attribute(base=str),
        offset=Attribute(
            base=int,
            aliases=['page'],
            default=0,
        ),
        limit=Attribute(
            base=int,
            aliases=['perPage'],
            required=True,
        ),
    )

    model = pydantic.create_model('test', **schema.build())

    expected = {'label': None, 'offset': 0, 'limit': 42}

    assert model.model_validate({'limit': 42}).model_dump() == expected
    assert model.model_validate({'perPage': 42}).model_dump() == expected

    with pytest.raises(pydantic.ValidationError,  match=r'^1 validation error for test'):
        model.model_validate({'label': {'key': 'value'}})

    with pytest.raises(pydantic.ValidationError,  match=r'^1 validation error for test'):
        model.model_validate({'page': 'error'})


def test_exclude_builtin_fields() -> None:
    """Allow to exclude builtins fields on a build."""
    schema = Schema(
        label=Attribute(base=str),
        offset=Attribute(
            base=int,
            aliases=['page'],
            default=0,
        ),
        limit=Attribute(
            base=int,
            aliases=['perPage'],
            required=True,
        ),
    )

    fields = schema.build()

    assert 'label' in fields
    assert 'offset' in fields
    assert 'limit' in fields

    with pytest.raises(ValueError, match=r'^attribute `label` is not unique in schema$'):
        schema.build(exclude={'label'})


def test_non_unique_attribute_aliases() -> None:
    """Fail schema build when attribute names or aliases are not unique."""
    schema = Schema(
        ignore=Attribute(base=bool, default=False),
        ignore_less_than=Attribute(
            base=int,
            aliases=['ignore'],
            default=False,
        ),
    )

    with pytest.raises(ValueError):
        schema.build()


def test_attribute_default_required() -> None:
    """Reject attributes marked as required while having a default value."""
    with pytest.raises(pydantic.ValidationError):
        Schema(page=Attribute(
            base=int,
            default=1,
            required=True,
        ))
