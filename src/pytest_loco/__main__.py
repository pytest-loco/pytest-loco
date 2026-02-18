"""CLI utilities for pytest-loco JSON Schema management.

The schema is generated from the pytest-loco document model and
customized to support runtime-evaluated callable expressions.
"""

from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING

from click import Path as PathParam
from click import argument, echo, group, option
from yaml import safe_load

from pytest_loco.jsonschema import SchemaGenerator

if TYPE_CHECKING:
    from pytest_loco.core import DocumentParser


CUSTOM_TAGS_OPTION = 'yaml.customTags'
SCHEMAS_OPTION = 'yaml.schemas'

OutputFilepath = PathParam(
    dir_okay=False,
    readable=True,
    writable=True,
    path_type=Path,
)


@group(help='Command-line utilities for pytest-loco schema management.')
def cli() -> None:
    """Root CLI group for pytest-loco tools."""
    return None


@cli.command(
    name='schema',
    help='Print the pytest-loco JSON Schema to standard output.',
)
def print_schema() -> None:
    """Generate and print the JSON Schema."""
    echo(SchemaGenerator.make_schema())


def _update_tags(parser: 'DocumentParser', tags: list[str]) -> list[str]:
    """Update YAML custom tags for VSCode configuration.

    Args:
        parser: pytest-loco document parser instance.
        tags: Existing YAML custom tags.

    Returns:
        Updated list of YAML custom tags.
    """
    if not isinstance(tags, list):
        tags = []

    return sorted({
        *tags,
        '!dump mapping',
        '!load mapping',
        *(f'!{name} scalar' for name in parser.instructions),
    })


def _update_schemas(schema: str,
                    schemas: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
    """Update YAML schema mappings for VSCode configuration.

    Args:
        schema: Path to the generated schema file.
        schemas: Existing YAML schema configuration mapping.

    Returns:
        Updated schema configuration.
    """
    if not isinstance(schemas, dict):
        schemas = {}

    return {
        **schemas,
        schema: [
            'test_*.yaml',
            'test_*.yml',
        ],
    }


@cli.command(
    name='vscode-configure',
    help=(
        'Generate a JSON Schema file and update VSCode settings.json '
        'to enable YAML validation for pytest-loco files.'
    ),
)
@option(
    '-s', '--schema',
    type=OutputFilepath,
    help='Output path for the generated JSON Schema file.',
    default='.vscode/loco.schema.json',
)
@argument(
    'settings',
    type=OutputFilepath,
    default='.vscode/settings.json',
)
def configure_vscode(schema: Path, settings: Path) -> None:
    """Configure VSCode YAML validation for pytest-loco.

    Args:
        schema: Output path for the schema file.
        settings: Path to VSCode settings file.
    """
    schema.parent.mkdir(parents=True, exist_ok=True)
    with schema.open('wt') as output:
        output.write(SchemaGenerator.make_schema())
        output.write('\n')

    content = {}
    if settings.exists():
        content = safe_load(settings.read_text())

    parser = SchemaGenerator.get_parser()

    content[CUSTOM_TAGS_OPTION] = _update_tags(
        parser,
        content.get(CUSTOM_TAGS_OPTION, []),
    )

    content[SCHEMAS_OPTION] = _update_schemas(
        schema.as_posix(),
        content.get(SCHEMAS_OPTION, {}),
    )

    settings.parent.mkdir(parents=True, exist_ok=True)
    with settings.open('wt') as output:
        output.write(dumps(content, ensure_ascii=False, indent=4))
        output.write('\n')


if __name__ == '__main__':
    cli()
