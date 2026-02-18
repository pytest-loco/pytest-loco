"""Base content operation definitions.

This module defines the base class for declarative content-processing
operations used in the DSL, such as parsing, serialization, or format
conversion.
"""

from collections.abc import Callable, Mapping
from typing import ClassVar

from pydantic import Field

from pytest_loco.context import ContextDict
from pytest_loco.models import SchemaModel
from pytest_loco.values import Deferred, RuntimeValue, Value, normalize

#: The runner is responsible for performing the actual transformation
#: or interpretation of the input data to context value.
type ContentRunner = Callable[[RuntimeValue, Mapping[str, RuntimeValue]], RuntimeValue]


class BaseContent(SchemaModel):
    """Base class for content processing definitions.

    Represents a declarative content operation that transforms or interprets
    input data according to a specific format. The actual processing logic
    is provided by a class-level runner callable.
    """

    #: Callable implementing the content operation.
    runner: ClassVar[ContentRunner]

    format_type: str = Field(
        validation_alias='format',
        title='Content format type',
        description=(
            'Identifier of the content format or protocol. '
            'Defines how the source value should be interpreted or processed '
            '(for example: json, xml, yaml, text).'
        ),
        json_schema_extra={
            'x-ref': 'ContentFormatType',
        },
    )

    source: Deferred[Value] = Field(
        title='Content source',
        description=(
            'Input value to be processed by the content operation. '
            'May reference variables from the execution context or contain '
            'raw data, depending on the DSL usage.'
        ),
        json_schema_extra={
            'x-ref': 'ContentSource',
        },
    )

    def __call__(self, context: dict[str, Value]) -> Value:
        """Execute the content operation.

        The source value and operation parameters are resolved against
        the provided execution context before invoking the runner.

        Args:
            context: Execution context providing variable values.

        Returns:
            Result of applying the content operation to the source value.

        Raises:
            Any exception raised by deferred resolution or the runner itself.
        """
        locals_ = ContextDict(context)

        result = type(self).runner(
            locals_.resolve(self.source),
            locals_.resolve(
                self.model_dump(exclude={
                    'format_type',
                    'source',
                }),
            ),
        )

        return normalize(result)
