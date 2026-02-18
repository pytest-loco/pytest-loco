"""Example plugin definition for pytest-loco.

This module demonstrates how to declare a simple pytest-loco plugin
using the high-level `Plugin` extension model.

The example plugin:
- defines a plugin namespace (`example`),
- registers multiple content types (JSON and Base64),
- registers a custom YAML instruction.

The module is intended for documentation and testing purposes and
serves as a reference for plugin authors implementing their own
extensions.
"""

from pytest_loco.extensions import Plugin

from .contents import base64, json
from .instructions import fmt

example = Plugin(
    name='example',
    content_types=[json, base64],
    instructions=[fmt],
)
