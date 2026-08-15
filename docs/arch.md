# AgentGate Architecture

## Positioning

AgentGate is an OpenTelemetry-native, framework-independent evaluation harness for enterprise agent quality gates.

It is not only a trace viewer or generic LLM eval library. Its core job is to answer:

```text
Can this agent version be released safely?
```

## Core Flow

```text
Case
  -> Target Agent
  -> Run + Trace
  -> Evaluators
  -> Result
  -> Report / Gate Decision
```

## Five Core Modules

### Case

Defines what should be tested.

Includes:

- input messages
- initial state
- expected outcome
- required actions
- forbidden actions
- tool argument constraints
- workflow constraints
- final state assertions
- policy references
- provenance and review status

### Run

Represents one execution of a case or batch.

Includes:

- run config
- target agent config
- evaluator config snapshot
- lifecycle status
- timeout, retry, concurrency
- run events

### Trace

Represents what happened during execution.

Includes:

- raw spans
- normalized agent execution graph
- LLM calls
- tool calls
- retrieval events
- approvals
- retries
- errors
- state-changing actions

### Evaluator

Defines how behavior is judged.

Initial evaluator types:

- final answer match
- required tool called
- forbidden tool not called
- tool argument constraints
- trajectory match
- policy rule match
- final state assertion
- latency/cost budget

### Result

Stores score, verdict, explanation, and evidence.

Each result should link back to:

- evaluator name and version
- score
- pass/fail/manual review verdict
- reason
- evidence span IDs
- policy/document references

## Entry Points

```text
CLI      -> control services -> core modules
REST API -> control services -> core modules
Web UI   -> REST API -> control services -> core modules
Java SDK -> REST API / OTLP -> control services -> core modules
```

CLI and Web should expose the same major operations, but Web calls the REST API while CLI can call the control layer directly.

## Technology Choices

Initial backend:

- Python 3.11+
- Pydantic v2
- Typer CLI
- FastAPI REST API
- SQLite first
- PostgreSQL later
- OpenTelemetry/OTLP for trace interoperability

Initial Web:

- Vue 3
- TypeScript
- Vite

## Repository Strategy

Start as one repository:

```text
agentgate/
  src/agentgate/
  web/
  docs/
  examples/
  tests/
```

Split only when needed:

- Web UI has an independent release cycle.
- Enterprise control plane becomes large.
- Go service is needed for a high-performance gateway or scheduler.
- Multiple teams own backend and frontend separately.
