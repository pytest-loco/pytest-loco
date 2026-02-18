"""Extensions discovery and extension loading infrastructure.

This module defines a mixin responsible for discovering, loading, and
registering DSL plugins exposed via Python entry points.

Plugins are loaded defensively: individual failures do not interrupt
the loading process unless strict mode is enabled. Each plugin may
contribute actors, checkers, content types, and YAML instructions.
"""

from typing import TYPE_CHECKING
from warnings import warn

from pydantic import ValidationError

from pytest_loco.errors import PluginError, PluginWarning
from pytest_loco.extensions import Plugin

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

if TYPE_CHECKING:
    from pydantic import RootModel

if TYPE_CHECKING:
    from pytest_loco.extensions import Actor, Checker, ContentType, Instruction
    from pytest_loco.schema import BaseAction, BaseCheck, BaseContent, BaseInstruction


class ExtensionsLoaderMixin:
    """Mixin defining plugin extension loading behavior.

    This mixin encapsulates logic for discovering and loading plugins
    via entry points and delegating registration of their declared
    extensions.

    Implementers are expected to override the `add_*` methods to perform
    actual registration. This class provides only orchestration and
    error-handling logic.

    Attributes:
        strict_mode: If True, any plugin loading issue raises an error.
            If False, issues are emitted as warnings and loading continues.
    """

    strict_mode: bool = False

    actors: dict[str, type['BaseAction']]
    checkers: dict[str, type['BaseCheck']]

    decoders: dict[str, type['RootModel[BaseContent]']]
    encoders: dict[str, type['RootModel[BaseContent]']]

    instructions: dict[str, type['BaseInstruction']]

    def add_actor(self, actor: 'Actor',
                  entrypoint: 'EntryPoint | None' = None,
                  namespace: str | None = None) -> None:
        """Register an actor definition.

        Args:
            actor: Declarative actor definition.
            entrypoint: Entry point from which the content type was loaded,
                if applicable. Used for diagnostics and warnings.
            namespace: Optional plugin namespace to prefix the actor name.

        Raises:
            PluginError: If actor is invalid on strict mode.
        """
        module, qualname = self.resolve_plugin_names(actor, entrypoint, namespace)

        if qualname in self.actors and (error := self.emit_plugin_issue(
            f'Actor {qualname!r} from {module!r} is shadowing an existing',
            entrypoint,
        )):
            raise error

        self.actors[qualname] = actor.build(namespace)

    def add_checker(self, checker: 'Checker',
                    entrypoint: 'EntryPoint | None' = None) -> None:
        """Register a checker definition.

        Args:
            checker: Declarative checker definition.
            entrypoint: Entry point from which the content type was loaded,
                if applicable. Used for diagnostics and warnings.

        Raises:
            PluginError: If checker is invalid on strict mode.
        """
        module, qualname = self.resolve_plugin_names(checker, entrypoint)

        if qualname in self.checkers and (error := self.emit_plugin_issue(
            f'Checker {qualname!r} from {module!r} is shadowing an existing',
            entrypoint,
        )):
            raise error

        self.checkers[qualname] = checker.build()

    def add_content_type(self, content_type: 'ContentType',
                         entrypoint: 'EntryPoint | None' = None) -> None:
        """Register a content type definition.

        Args:
            content_type: Declarative content type definition.
            entrypoint: Entry point from which the content type was loaded,
                if applicable. Used for diagnostics and warnings.

        Raises:
            PluginError: If content type is invalid on strict mode.
        """
        module, qualname = self.resolve_plugin_names(content_type, entrypoint)

        if decoder_model := content_type.build_decoder():
            if qualname in self.decoders and (error := self.emit_plugin_issue(
                f'Format-decoder {qualname!r} from {module!r} is shadowing an existing',
                entrypoint,
            )):
                raise error
            self.decoders[qualname] = decoder_model

        if encoder_model := content_type.build_encoder():
            if qualname in self.encoders and (error := self.emit_plugin_issue(
                f'Format-encoder {qualname!r} from {module!r} is shadowing an existing',
                entrypoint,
            )):
                raise error
            self.encoders[qualname] = encoder_model

    def add_instruction(self, instruction: 'Instruction',
                        entrypoint: 'EntryPoint | None' = None) -> None:
        """Register an instruction.

        Args:
            instruction: Declarative instruction definition.
            entrypoint: Entry point from which the instruction was loaded, if applicable.

        Raises:
            PluginError: If instruction is invalid on strict mode.
        """
        module, qualname = self.resolve_plugin_names(instruction, entrypoint)

        if instruction.name in self.instructions and (error := self.emit_plugin_issue(
            f'Instruction {qualname!r} from {module!r} is shadowing an existing',
            entrypoint,
        )):
            raise error

        self.instructions[instruction.name] = instruction.build()

    @staticmethod
    def resolve_plugin_names(item: 'Actor | Checker | ContentType | Instruction',
                             entrypoint: 'EntryPoint | None' = None,
                             namespace: str | None = None) -> tuple[str, str]:
        """Resolve plugin display names for a definition.

        Args:
            item: Declarative definition.
            entrypoint: Entry point from which the content type was loaded, if applicable.
            namespace: Optional plugin namespace to prefix the definition name.

        Returns:
            Tuple with a module name and a qualified name for a definition.
        """
        return (
            f'{entrypoint.value if entrypoint else item.__module__}',
            f'{namespace or 'builtins'}.{item.name}',
        )

    def emit_plugin_issue(self, message: str,
                          entrypoint: 'EntryPoint | None' = None) -> Exception | None:
        """Emit a plugin warning or return the exception.

        Args:
            message: Warning message to emit.
            entrypoint: Entry point from which the content type was loaded, if applicable.

        Returns:
            PluginError on strict mode, otherwise `None`
                with producing a PluginWarning.
        """
        if self.strict_mode:
            return PluginError(message, entrypoint=entrypoint)

        warn(message, category=PluginWarning, stacklevel=2)

        return None

    def _load_plugin(self, entrypoint: 'EntryPoint') -> None:
        """Load and process a single plugin entry point.

        Safely loads the plugin object and extracts supported extension
        providers if present.

        Each provider is expected to be a callable returning an iterable
        of extension definitions. All items are validated individually.
        Any errors or malformed entries result in warnings and do not
        interrupt plugin loading by default, but raises on strict mode.

        Args:
            entrypoint: Entry point describing the plugin to load.

        Raises:
            PluginError: If any loading issues occur on strict mode.
        """
        try:
            plugin = entrypoint.load()

        except ValidationError as base:
            if error := self.emit_plugin_issue(
                f'Failed to validate entrypoint {entrypoint.name!r}',
                entrypoint,
            ):
                raise error from base
            return None

        except Exception as base:
            if error := self.emit_plugin_issue(
                f'Failed to load entrypoint {entrypoint.name!r}',
                entrypoint,
            ):
                raise error from base
            return None

        if not isinstance(plugin, Plugin):
            if error := self.emit_plugin_issue(
                f'Loaded from entrypoint {entrypoint.name!r} object is not a plugin',
                entrypoint,
            ):
                raise error
            return None

        for actor in plugin.actors:
            self.add_actor(actor, entrypoint, namespace=plugin.name)

        for checker in plugin.checkers:
            self.add_checker(checker, entrypoint)

        for content_type in plugin.content_types:
            self.add_content_type(content_type, entrypoint)

        for instruction in plugin.instructions:
            self.add_instruction(instruction, entrypoint)

    def clear_plugins(self) -> None:
        """Clear all registered plugins.

        Clear all internal containers with registered plugins.
        """
        self.actors = {}
        self.checkers = {}
        self.decoders = {}
        self.encoders = {}
        self.instructions = {}

    def load_plugins(self) -> None:
        """Load plugins via entry points and register their extensions.

        Discovers plugins from the `loco_plugins` entry point group.

        Raises:
            PluginError: If any loading issues occur on strict mode.
        """
        from importlib.metadata import entry_points  # noqa: PLC0415

        for entrypoint in entry_points().select(group='loco_plugins'):
            self._load_plugin(entrypoint)
