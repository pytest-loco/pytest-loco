# pytest-loco

Declarative DSL for structured, extensible test scenarios in pytest.

`pytest-loco` introduces a YAML-based domain-specific language (DSL) for
describing test workflows in a declarative and composable way.
It is designed to support structured validation, data-driven execution,
and pluggable extensions such as HTTP, JSON, and custom domain logic.

## Install

```sh
> pip install pytest-loco
```

Requirements:
- Python 3.13 or higher

## Concepts

### Definitions

A test file is a sequence of YAML documents, each document has a `spec`
that defines its role.

Document represents a `step` by default, but the first document in a file may define:

- a `case` (runnable scenario), or
- a `template` (reusable, non-runnable definition)

Subsequent documents define executable steps.

#### Case

A `case` represents a runnable test scenario.

```yaml
spec: case
title: Short human-readable case title
description: >
  Detailed human-readable description of the scenario.
  May span multiple lines and is intended for documentation
  and reporting purposes
metadata:
  tags:
    - engine
    - example
vars:
  baseUrl: https://httpbin.org
```

Only documents under a `case` are executed.

#### Template

A `template` defines reusable logic that can be applied to multiple cases.

```yaml
spec: template
title: Short human-readable template title
description: >
  Detailed human-readable description of the scenario template.
  May span multiple lines and is intended for documentation
  and reporting purposes
params:
  - name: baseUrl
    type: string
    default: https://httpbin.org
```

Templates allow:

- Reuse of common workflows
- Parameterized execution
- Elimination of duplication
- Standardization of expectations

Templates are resolved at parse time and merged into the execution graph.

```yaml
...

---
title: Example of invoking the template from a case
description: >
  This step demonstrates how a template can be invoked from
  within a case using the `include` action. The caller may pass
  variables into the action context via `vars`. These variables
  are treated as parameters of the invoked template. The template
  execution context is isolated: only values explicitly declared
  as template parameters are transferred and shared.
action: include
vars:
  argument: OK
file: echo.yaml
export:
  value: !var result.value
expect:
  - title: Value exists in include result
    value: !var value
    match: OK

...
```

### Steps

#### Actions

Actions are the executable units of a case, each step document
describes a single action invocation with expectations block.

The core itself does not implement domain-specific logic.
The plugin executes the action implementation. Action resolution
working with `action` field as a symbolic identifier (for example,
`http.get`).

At runtime:
- The core locates the plugin that registered this action
- The action schema is validated
- Arguments are parsed and compiled (including deferred expressions)
- The plugin executes the action implementation

The complex example with `pytest-loco-json` and `pytest-loco-http` extensions:

```yaml
...

---
title: Test HTTP GET-method
description: >
  Detailed human-readable description of the action.
  May span multiple lines and is intended for documentation
  and reporting purposes
action: http.get
url: !urljoin baseUrl /get
params: test: 'true'
headers:
  accept: application/json
output: response
export:
  responseJson: !load
    source: !var response.text
    format: json
expect:
  - title: Status is 200
    value: !var response.status
    match: 200
  - title: Response contains arguments
    value: !var responseJson.args.test
    match: 'true'

...
```

After execution, the action produces a result object.

By convention, this result is stored in the case context under
`result`. But user can redefine output variable name by `output` field.

```yaml
...

output: response
value: !var response.status

...
```

The structure of result is defined by the plugin.


Actions may define an export block:

```yaml
...

export:
  token: !var result.token
...

```

Export:
- Evaluates expressions after action execution
- Stores values in case context
- Makes them available to subsequent steps

Exports are explicit data flow. Nothing is implicitly persisted
across steps except what is exported.

#### Expectations

Actions may define expectations.

```yaml
...

expect:
  - title: Status is 200
    value: !var result.status
    match: 200
...

```

Expectations:
- Are evaluated after export
- Operate on fully resolved values
- Produce structured assertion results
- Are reported individually

Failure of an expectation fails the step and the case.

By default available:
- `match` (aliased `eq`, `equal`)
- `not_match` (aliased `notMatch`, `ne`, `notEqual`)
- `less_than` (aliased `lt`, `lessThan`)
- `greater_than` (aliased `gt`, `greaterThan`)
- `less_than_or_equal` (aliased `lte`, `lessThanOrEqual`)
- `greater_than_or_equal` (aliased `gte`, `greaterThanOrEqual`)
- `regex` (aliased `reMatch`, `regexMatch`)

Expectations can be extended by plugins.

### Context

The context is the runtime state container for a case.

It holds:
- Case-level variables (defined by `vars` in a case)
- Case parameters (defined by `params` in a case)
- Template parameters (defined by `params` in a case)
- Environment variables (defined by `envs` in a case or a template)
- Step-level variables (defined by `vars` in a step)
- Step results (stored in `result` by default)
- Exported values
- Deferred expressions

Each case has its own isolated context.

Instructions such as:

```yaml
...

value: !var result.status
...
```

are compiled at parse time but executed at runtime.

Deferred evaluation allows:
- Accessing results of previous steps
- Chained transformations
- Late binding of values
- Context-aware resolution

Evaluation order is deterministic and follows step order.

### Errors

Parse Errors (before execution begins):
- Invalid YAML structure
- Invalid schema
- Unknown action or expectation
- Unknown instruction
- Invalid parameter declarations

In this case, the test case does not start execution.

Runtime Errors (during execution)
- Exception raised inside an action or an expectation
- Deferred evaluation failure
- Type validation failure
- Data transformation errors

Any failures must be deterministic and predictable, so
deliberate simplifications of semantics and behavior have
been introduced into the core:
- No implicit continuation after failure
- No silent exception suppression
- No partially committed state
- No automatic retries unless implemented by a plugin

## VSCode integration

Recommended extension:
[YAML Language Support by Red Hat](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)

DSL schema is available for validation and hints with this extension.

Just run:

```sh
> pytest-loco vscode-configure
```

at the root of a project.
