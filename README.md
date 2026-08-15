# AgentGate

AgentGate is an open-source evaluation harness for enterprise agents.

It helps teams run agent test cases, collect traces, evaluate behavior, compare versions, and make release gate decisions.

## Goal

AgentGate focuses on:

- Active evaluation: run cases against an agent.
- Passive evaluation: score existing production traces.
- Business contracts: validate tool calls, arguments, policies, workflow rules, and final state.
- Release gates: decide whether an agent/model/prompt version is safe to ship.
- Dataset growth: turn failures and traces into regression cases.

## Initial Architecture

```text
CLI / Web / REST API
        |
    Control Layer
        |
Case -> Run -> Trace -> Evaluator -> Result
```

## Project Layout

```text
src/agentgate/
  case/          # Cases, datasets, customer/public benchmark import
  run/           # Run engine, targets, lifecycle
  trace/         # Trace model, OTel import, execution graph
  evaluator/     # Built-in and external evaluators
  result/        # Results, reports, compare, release gates
  control/       # Shared operations used by CLI/API/Web
  cli/           # Command-line entry point
  server/        # REST API entry point

web/             # Future Vue/TypeScript UI
docs/            # Design docs
examples/        # Demo agents and datasets
tests/           # Test suite
```

## First Demo Target

The first demo should be a loan approval agent:

- The agent may create a loan application.
- The agent must not approve high-risk loans directly.
- Approval may require human review.
- Evaluators check tool calls, tool arguments, workflow policy, and final state.

## Status

Early scaffold. Core models and contracts should be finalized before building the Web UI or distributed runtime.
