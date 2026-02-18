"""Integration tests for DSL parsing and execution pipeline."""

import os
from typing import TYPE_CHECKING

import pytest

from pytest_loco.core import DocumentParser
from pytest_loco.errors import DSLRuntimeError, DSLSchemaError
from pytest_loco.extensions import Actor, Attribute, Plugin, Schema
from pytest_loco.plugin.case import TestPlan
from pytest_loco.plugin.spec import TestSpec

if TYPE_CHECKING:
    from collections.abc import Callable
    from re import Pattern

if TYPE_CHECKING:
    from pyfakefs.fake_filesystem import FakeFilesystem
    from pytest_mock import MockerFixture, MockType
    from yaml import SafeLoader


TEST_INCREMET_CASE_OK_CONTENT = '''
---
spec: case
title: A test case
vars:
  value: 1
metadata:
  author: Tester

---
action: test.increment
title: Test increment with export
val: !var value
export:
  value: !var result
  resultDict:
    result:
      values:
        - !var result
      status: OK
expect:
  - title: Result exists
    value: !var result
    match: 2
  - title: Value is changed
    value: !var value
    match: 2
  - title: Result dict status is not ERROR
    value: !var resultDict.result
    partialMatch: yes
    notMatch:
      result:
        status: ERROR
  - title: Result dict values list partially match
    value: !var resultDict.result.values
    partialMatch: yes
    match:
      - 2
  - title: Result dict exactly match
    value: !var resultDict
    match:
      result:
        values:
          - 2
        status: OK

---
action: test.increment
title: Test increment without export
val: !var value
expect:
  - title: Result exists
    value: !var result
    match: 3
  - title: Value is unchanged
    value: !var value
    notMatch: 3
'''

TEST_INCREMET_CASE_OK_CONTENT_WITH_PARAMS = '''
---
spec: case
title: A test case
params:
  - name: value
    values:
      - 1
      - 2
metadata:
  author: Tester

---
action: test.increment
title: Test increment with export
val: !var params.value
expect:
  - title: Result more than one
    value: !var result
    gt: 1
  - title: Result less than or equal three
    value: !var result
    lte: 3
  - title: Warm-up 1
    value:
      - 1
      - 2
      - 3
      - name: surprise!
        value: 4
    partialMatch: yes
    match:
      - 2
      - name: surprise!
        value: 4
  - title: Warm-up 2
    value:
      status: OK
    partialMatch: yes
    notMatch:
      state: OK

'''

TEST_INCREMET_CASE_OK_CONTENT_WITH_ENVS = '''
---
spec: case
title: A test case
envs:
  - name: TEST_VAR
    type: integer
vars:
  value: !var envs.TEST_VAR
metadata:
  author: Tester

---
action: test.increment
title: Test increment with export
val: !var value
expect:
  - title: Result more than one
    value: !var result
    gt: 1
'''

TEST_INCREMET_CASE_OK_CONTENT_WITHOUT_HEADER = '''
---
action: test.increment
title: Test increment with export
val: 1
export:
  value: !var result
expect:
  - title: Result exists
    value: !var result
    equal: 2
  - title: Value is changed
    value: !var value
    equal: 2

---
action: test.increment
title: Test increment without export
val: !var value
expect:
  - title: Result exists
    value: !var result
    equal: 3
  - title: Value is unchanged
    value: !var value
    notEqual: 3
'''

TEST_INCREMET_CASE_FAIL_CONTENT = '''
---
spec: case
title: A test case
vars:
  value: 1
metadata:
  author: Tester

---
action: test.increment
title: Test increment with export
val: !var value
export:
  value: !var result
expect:
  - title: Result exists
    value: !var result
    equal: 2
  - title: Value is changed
    value: !var value
    equal: 2

---
action: test.increment
title: Test how to fail
val: !var value
export:
  values:
    - !var result
expect:
  - title: Result exists
    value: !var result
    match: 3
  - title: Must fail here
    value: !var result
    partialMatch: yes
    match:
      - 5
      - 2
  - title: Value is changed
    value: !var value
    match: 3
'''

TEST_INCREMET_CASE_FAIL_RUNTIME = '''
---
spec: case
title: A test case
metadata:
  author: Tester

---
action: test.increment
title: Test increment with export
val: !var value
export:
  value: !var result
expect:
  - title: Result exists
    value: !var result
    equal: 2
  - title: Value is changed
    value: !var value
    equal: 2
'''

TEST_INVALID_STRUCTURE_CASE_CONTENT = '''
action: test.increment
title: Test increment with export
val: !var value
export:
  value: !var result
expect:
  - title: Result exists
    value: !var result
    match: 2
  - title: Value is changed
    value: !var value
    match: 2

---
spec: case
title: A test case
vars:
  value: 1
metadata:
  author: Tester

---
action: test.increment
title: Test increment without export
val: !var value
expect:
  - title: Result exists
    value: !var result
    match: 3
  - title: Value is unchanged
    value: !var value
    notMatch: 3
'''

TEST_INVALID_MODEL_CASE_CONTENT = '''
spec: case
title: A test case
vars:
  value: 1
metadata:
  author: Tester

---
action: test.increment
title: Test without required action field
expect:
  - title: Unknown check
    value: !var result
    wrong: yes
'''

TEST_INVALID_MODEL_CASE_SPEC = '''
spec: func
title: A test case
vars:
  value: 1
metadata:
  author: Tester
'''

TEST_INVALID_MODEL_DOCUMENT = '''
- 1
- 2
- 3
'''

TEST_INVALID_MODEL_YAML= '''
!!python.object:str:"ERROR"
'''


@pytest.mark.parametrize('content, expect_message', (
    pytest.param(TEST_INCREMET_CASE_OK_CONTENT, None, id='ok'),
    pytest.param(TEST_INCREMET_CASE_OK_CONTENT_WITH_PARAMS, None, id='ok with params'),
    pytest.param(TEST_INCREMET_CASE_OK_CONTENT_WITH_ENVS, None, id='ok with envs'),
    pytest.param(TEST_INCREMET_CASE_OK_CONTENT_WITHOUT_HEADER, None, id='ok without header'),
    pytest.param(TEST_INCREMET_CASE_FAIL_CONTENT, r'^Expectation fail: Must fail here', id='fail'),
))
def test_parse_and_run(content: str, expect_message: 'Pattern | None',
                       patch_entrypoints: 'Callable[..., MockType]',
                       loader: 'type[SafeLoader]', mocker: 'MockerFixture') -> None:
    """Parse a DSL case."""
    mocker.patch.dict(os.environ, {'TEST_VAR': '1'})

    increment = Actor(
        name='increment',
        actor=lambda params: params['val'] + 1,
        parameters=Schema({
            'val': Attribute(base=int, default=0),
        }),
    )

    patch_entrypoints(Plugin(
        name='test',
        actors=[increment],
    ))

    parser = DocumentParser(loader)
    head, steps = parser.parse_file(content, expect='case')

    plans = [
        TestPlan(head, steps, params=values)
        for values in TestSpec.prepare_params(head)
    ]

    if expect_message is not None:
        with pytest.raises(AssertionError, match=expect_message):
            [plan.run_spec() for plan in plans]
        return None

    [plan.run_spec() for plan in plans]


def test_parse_on_invalid_structure(patch_entrypoints: 'Callable[..., MockType]',
                                    loader: 'type[SafeLoader]') -> None:
    """Reject invalid document ordering in multi-document DSL input."""
    increment = Actor(
        name='increment',
        actor=lambda params: params['val'] + 1,
        parameters=Schema(
            val=Attribute(base=int, default=0),
        ),
    )

    patch_entrypoints(Plugin(
        name='test',
        actors=[increment],
    ))

    parser = DocumentParser(loader)

    with pytest.raises(DSLSchemaError, match=r'^Header must be at first position'):
        parser.parse(TEST_INVALID_STRUCTURE_CASE_CONTENT)


@pytest.mark.parametrize('content, expect_message', (
    pytest.param(TEST_INVALID_MODEL_CASE_SPEC, r'^Input should be \'case\'', id='invalid spec'),
    pytest.param(TEST_INVALID_MODEL_CASE_CONTENT, r'^Extra inputs are not permitted', id='extra fields'),
    pytest.param(TEST_INVALID_MODEL_DOCUMENT, r'^Type validation error', id='invalid type'),
    pytest.param(TEST_INVALID_MODEL_YAML, r'^Invalid YAML', id='invalid yaml'),
))
def test_parse_on_invalid_schema(content: str, expect_message: 'Pattern',
                                 patch_entrypoints: 'Callable[..., MockType]',
                                 loader: 'type[SafeLoader]') -> None:
    """Fail parsing on schema validation errors."""
    increment = Actor(
        name='increment',
        actor=lambda params: params['val'] + 1,
        parameters=Schema(
            val=Attribute(base=int, default=0),
        ),
    )

    patch_entrypoints(Plugin(
        name='test',
        actors=[increment],
    ))

    parser = DocumentParser(loader)

    with pytest.raises(DSLSchemaError, match=expect_message):
        parser.parse(content)


@pytest.mark.parametrize('content, expect_message', (
    pytest.param(TEST_INCREMET_CASE_FAIL_RUNTIME, r'^Runtime error', id='runtime error'),
))
def test_run_on_runtime_error(content: str, expect_message: 'Pattern',
                              patch_entrypoints: 'Callable[..., MockType]',
                              loader: 'type[SafeLoader]') -> None:
    """Fail run with runtime errors."""
    increment = Actor(
        name='increment',
        actor=lambda params: params['val'] + 1,
        parameters=Schema(
            val=Attribute(base=int, default=0),
        ),
    )

    patch_entrypoints(Plugin(
        name='test',
        actors=[increment],
    ))

    parser = DocumentParser(loader)
    head, steps = parser.parse_file(content, expect='case')

    for values in TestSpec.prepare_params(head):
        plan = TestPlan(head, steps, params=values)
        with pytest.raises(DSLRuntimeError, match=expect_message):
            plan.run_spec()


TEST_INCLUDE_CASE = '''
---
spec: case
title: A simple case including a template

---
action: include
vars:
  argument: OK
file: template.yaml
export:
  value: !var result.value
expect:
  - title: Value exists in include result
    value: !var value
    match: OK
'''

TEST_INCLUDE_TEMPLATE = '''
spec: template
title: A simple template
params:
 - name: argument

---
action: empty
export:
  value: !var params.argument
expect:
  - title: Value exists in template
    value: !var value
    match: OK
'''


def test_base_template(fs: 'FakeFilesystem',
                       patch_entrypoints: 'Callable[..., MockType]',
                       loader: 'type[SafeLoader]') -> None:
    """Test base template running."""
    patch_entrypoints()

    fs.create_file('test_case.yaml', contents=TEST_INCLUDE_CASE)
    fs.create_file('template.yaml', contents=TEST_INCLUDE_TEMPLATE)

    parser = DocumentParser(loader)

    with open('test_case.yaml') as content:
        head, steps = parser.parse_file(content, expect='case')

    plan = TestPlan(head, steps, params={}, parser=parser)
    plan.run_spec()
