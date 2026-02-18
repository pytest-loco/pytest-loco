"""YAML DSL parser and runtime integration.

This module defines a high-level parser responsible for integrating
all DSL extensions into a YAML loader and validating DSL documents.

The parser coordinates:
- built-in instructions and checkers,
- plugin-provided extensions,
- dynamically built content encoders and decoders,
- custom YAML constructors.

As a result, the YAML loader becomes capable of parsing, validating,
and preparing executable DSL documents with full plugin support.
"""

from typing import TYPE_CHECKING, Literal

from pydantic import PydanticUserError, ValidationError
from yaml import add_constructor, load_all
from yaml.error import MarkedYAMLError

from pytest_loco.builtins import actors, checkers, instructions
from pytest_loco.errors import DSLBuildError, DSLError, DSLSchemaError
from pytest_loco.schema import BaseAction, Case, Template

from .builder import Document, ExtensionsBuilderMixin
from .loader import ExtensionsLoaderMixin

if TYPE_CHECKING:
    from io import TextIOBase

if TYPE_CHECKING:
    from yaml import BaseLoader

#: Parsed file header.
#: Can be a Case header, a Template header, or None if no header is present.
type Header = Case | Template | None

#: Parsed executable step.
type Step = BaseAction

#: Parsed executable steps.
type Steps = tuple[Step, ...]

#: Fully unpacked DSL file contents.
#: Consists of an optional header and a list of steps.
type Source = tuple[Header, Steps]


class DocumentParser(ExtensionsBuilderMixin, ExtensionsLoaderMixin):
    """DSL YAML parser with plugin and extension support.

    This class is responsible for:
    - registering built-in and plugin-provided DSL instructions;
    - attaching custom YAML constructors to a loader;
    - dynamically building a Pydantic model representing the DSL schema;
    - parsing and validating YAML documents into executable DSL models.

    The parser is stateful and may cache the built DSL model for reuse.
    """

    def __init__(self, loader: type['BaseLoader'],
                 strict: bool = False, allow_lambda: bool = False,
                 auto_attach: bool = True,
                 auto_build: bool = False) -> None:
        """Initialize the DSL document parser.

        During initialization, the parser:
        - resets internal plugin state;
        - registers all built-in DSL instructions and checkers;
        - loads plugin-provided extensions;
        - optionally attaches constructors to the YAML loader;
        - optionally builds and caches the DSL document model.

        Args:
            loader: YAML loader class to extend with DSL constructors.
            strict: Whether to raise errors on plugin or extension loading
                failures instead of emitting warnings.
            allow_lambda: Whether to enable the unsafe `!lambda` instruction.
                Disabled by default for security reasons.
            auto_attach: Whether to automatically attach all known DSL
                constructors to the YAML loader during initialization.
            auto_build: Whether to automatically build and cache the DSL
                document model during initialization.

        Raises:
            DSLBuildError: If the DSL document model cannot be built
                when `auto_build` is enabled.
        """
        self.loader = loader
        self.strict_mode = strict

        self.clear_plugins()

        self.add_instruction(instructions.variable)
        self.add_instruction(instructions.secret)

        self.add_instruction(instructions.date_)
        self.add_instruction(instructions.datetime_)
        self.add_instruction(instructions.timedelta_)
        self.add_instruction(instructions.duration)

        self.add_instruction(instructions.text_file)

        self.add_instruction(instructions.binary_file)
        self.add_instruction(instructions.base64)
        self.add_instruction(instructions.binary_hex)

        self.add_actor(actors.noop)

        self.add_checker(checkers.eq)
        self.add_checker(checkers.neq)
        self.add_checker(checkers.lt)
        self.add_checker(checkers.lte)
        self.add_checker(checkers.gt)
        self.add_checker(checkers.gte)
        self.add_checker(checkers.regex)

        if allow_lambda:
            self.add_instruction(instructions.lambda_)

        self.load_plugins()

        if auto_attach:
            self.attach()

        self._cached_model: type[Document] | None = None
        if auto_build:
            self.build()

    def attach(self) -> None:
        """Attach all known DSL constructors to the YAML loader.

        This method mutates the provided YAML loader in-place by registering:
        - content decoders (`!load`),
        - content encoders (`!dump`),
        - instruction constructors (`!<instruction>`).

        It is safe to call this method multiple times, but repeated calls
        may overwrite previously registered constructors.
        """
        if self.decoders:
            decoder_constructor = self.build_content_constructor(*self.decoders.values())
            add_constructor('!load', decoder_constructor, Loader=self.loader)

        if self.encoders:
            encoder_constructor = self.build_content_constructor(*self.encoders.values())
            add_constructor('!dump', encoder_constructor, Loader=self.loader)

        for name, instruction in self.instructions.items():
            add_constructor(f'!{name}', instruction(), Loader=self.loader)

    def build(self) -> type[Document]:
        """Build and cache the root DSL document model.

        The model is constructed dynamically from all registered DSL actors
        (instructions) and checkers, and then cached for reuse.

        Returns:
            The root Pydantic model representing the DSL document schema.

        Raises:
            DSLBuildError: If the document model cannot be built due to
                configuration conflicts, missing components, or internal errors.
        """
        if self._cached_model is not None:
            return self._cached_model

        try:
            self._cached_model = self.build_document(
                list(self.actors.values()),
                list(self.checkers.values()),
            )
            if not self._cached_model:
                raise DSLBuildError('Document model is empty')

        except PydanticUserError as base:
            raise DSLBuildError('Document model has conflicts') from base

        except DSLBuildError:
            raise

        except Exception as base:
            raise DSLBuildError('Unexpected error') from base

        return self._cached_model

    def parse(self, content: 'TextIOBase | str') -> Source:
        """Parse a YAML stream into validated DSL documents.

        The input may contain multiple YAML documents. At most one header
        document (`Case` or `Template`) is allowed and it must appear first.
        All subsequent documents are treated as executable steps.

        Each document is validated against the dynamically built DSL schema.

        Args:
            content: YAML content as a string or file-like object.

        Returns:
            A tuple consisting of:
            - the optional header document;
            - a list of executable step documents.

        Raises:
            DSLBuildError: If the document model cannot be built due to
                configuration conflicts, missing components, or internal errors.
            DSLSchemaError: If YAML parsing fails or DSL validation fails.
        """
        model = self.build()

        try:
            documents = list(load_all(content, Loader=self.loader))

        except MarkedYAMLError as base:
            raise DSLSchemaError.from_yaml_error(base) from base

        except DSLError:
            raise

        except Exception as base:
            raise DSLSchemaError('Unexpected error') from base

        header, steps = None, []

        for position, document in enumerate(documents):
            try:
                item = model.model_validate(document)

            except ValidationError as base:
                raise DSLSchemaError.from_pydantic_error(
                    base,
                    step_num=position + 1,
                    data=document,
                ) from base

            if isinstance(item.root, (Case, Template)):
                if position > 0:
                    raise DSLSchemaError('Header must be at first position')
                header = item.root
            elif isinstance(item.root.root, BaseAction):
                steps.append(item.root.root)

        return header, tuple(steps)

    def parse_file(self, content: 'TextIOBase | str', *,
                   expect: Literal['case', 'template'] = 'case') -> Source:
        """Parse and unpack a DSL specification file.

        This method is a high-level wrapper over :meth:`parse` that enforces
        expectations about the file structure and separates the header
        document from executable steps.

        Args:
            content: YAML content as a string or file-like object.
            expect: Expected file type:
                - `case`: a Case header is optional;
                - `template`: a Template header is required and must be present.

        Returns:
            A tuple consisting of:
            - the optional header document;
            - a list of executable step documents.

        Raises:
            DSLBuildError: If the document model cannot be built due to
                configuration conflicts, missing components, or internal errors.
            DSLSchemaError: If the file structure does not match expectations
                or if the file is empty when a template is required.
        """
        header, steps = self.parse(content)
        if expect == 'template' and not isinstance(header, Template):
            raise DSLSchemaError('Template must contain a template header definition')

        if expect == 'case' and header is not None and not isinstance(header, Case):
            raise DSLSchemaError('Case must contain a case header definition')

        return header, steps
