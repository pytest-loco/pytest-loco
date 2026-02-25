"""Dynamic DSL schema composition utilities.

This module defines helpers for building runtime Pydantic models that
represent executable DSL documents.

It composes actions, checks, cases, and templates into a single root
document schema using discriminated unions and `RootModel`.
"""

from collections.abc import Callable
from typing import Any, Literal, Union

from pydantic import Field, RootModel, ValidationError, create_model
from yaml import BaseLoader  # noqa: TC002
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode  # noqa: TC002

from pytest_loco.schema import BaseAction, BaseCheck, BaseContent, Case, Template
from pytest_loco.schema.actions import IncludeAction

#: Root model for executable actions (with optional expectations).
type RootAction = RootModel[BaseAction]

#: Root model for checks used as expectations.
type RootCheck = RootModel[BaseCheck]

#: Root model for content instruction.
type RootContent = RootModel[BaseContent]

#: Content constructor.
type ContentConstructor = Callable[..., BaseContent]

#: Header executable definition in a document.
type Header = Case | Template

#: Step executable definition in a document.
type Step = RootAction

#: Single executable definition in a document.
type Definition = Header | Step

#: Root model for the entire DSL document.
type Document = RootModel[Definition]


class ExtensionsBuilderMixin:
    """Mixin providing dynamic DSL schema composition.

    This mixin builds runtime Pydantic models that represent executable
    DSL documents by composing actions, checks, cases, and templates.

    The resulting models are used for validation and execution planning
    of parsed DSL documents.
    """

    @classmethod
    def build_actions(cls, actions: list[type[BaseAction]],
                      check_model: type[RootCheck] | None = None) -> type[RootAction]:
        """Build a root model aggregating all executable actions.

        Each action model is extended with an optional `expect` field
        containing post-execution checks.

        Args:
            actions: Concrete action models.
            check_model: Root model for expectations.

        Returns:
            RootModel wrapping a union of executable action variants.
        """
        models = tuple(
            create_model(  # type: ignore[call-overload]
                model.__class__.__name__,
                __base__=model,
                expect=cls.build_check_field(check_model),
            )
            for model in (IncludeAction, *actions)
        )

        return create_model(
            'Step',
            __base__=RootModel,
            root=Union[models],  # noqa: UP007
        )

    @classmethod
    def build_check_field(cls, check_model: type[RootCheck] | None = None) -> tuple[Any, Any]:
        """Build a Pydantic field definition for action expectations.

        The field is attached to action models and represents a list of
        checks that must pass after action execution.

        Args:
            check_model: Root check model to use for expectations.

        Returns:
            A tuple suitable for passing to `create_model`.
                If no check model is provided, returns a `Literal[None]` field.
        """
        if not check_model:
            return Literal[None], None

        return list[check_model], Field(  # type: ignore[valid-type]
            default_factory=list,
            title='Action expectations',
            description=(
                'List of checks that must pass after the action execution. '
                'Each check validates some aspect of the action result or '
                'side effects. All expectations are evaluated to determine '
                'the success or failure of the step.'
            ),
        )

    @classmethod
    def build_checks(cls, checks: list[type[BaseCheck]]) -> type[RootCheck] | None:
        """Build a root model aggregating all available checks.

        Args:
            checks: Concrete check models.

        Returns:
            RootModel wrapping a union of all checks, or None if no checks are provided.
        """
        if not checks:  # pragma: no cover
            return None

        return create_model(
            'Check',
            __base__=RootModel,
            root=Union[tuple(checks)],  # noqa: UP007
        )

    @staticmethod
    def build_content_constructor(*models: type[RootContent]) -> ContentConstructor:
        """Create a YAML constructor for content encoder/decoder models.

        Dynamically builds a union-based Pydantic model that accepts any of
        the provided content models and returns a validated instance.

        Args:
            *models: Content model classes (encoders or decoders).

        Returns:
            A YAML constructor function producing a content model instance.
        """
        model = create_model(
            'Content',
            __base__=RootModel,
            root=Union[models],  # noqa: UP007
        )

        def content_constructor(loader: BaseLoader, node: MappingNode) -> BaseContent:
            """Construct callable content-model from node."""
            try:
                item = model.model_validate(loader.construct_mapping(node, deep=True))
                return item.root.root  # type: ignore[no-any-return]
            except ValidationError as error:
                raise ConstructorError(
                    context='while constructing the content resolver',
                    context_mark=node.start_mark,
                    problem=error.title,
                    problem_mark=node.start_mark,
                ) from error

        return content_constructor

    @classmethod
    def build_document(cls, actions: list[type[BaseAction]],
                       checks: list[type[BaseCheck]]) -> type[Document] | None:
        """Build the root DSL document model.

        Args:
            actions: List of registered action models.
            checks: List of registered check models.

        Returns:
            RootModel representing the entire DSL document,
                or None if no executable steps are available.
        """
        step = cls.build_actions(actions, check_model=cls.build_checks(checks))
        if not step:  # pragma: no cover
            return None

        return create_model(
            'Document',
            __base__=RootModel,
            root=Union[(Case, Template, step)],  # noqa: UP007
        )
