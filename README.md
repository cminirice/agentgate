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
  case/          # Cases, datasets, custom/public benchmark import
  run/           # Run engine, targets, lifecycle
  trace/         # Trace model, OTel import, execution graph
  evaluator/     # Built-in and external evaluators
  result/        # Results, reports, compare, release gates
  experiment/    # Controlled A/B experiments and statistical decisions
  queue/         # Public reservation and queue orchestration
  optimizer/     # Badcase analysis and human-reviewed recommendations
  lineage/       # Asset versions and dependency lineage
  control_plane/ # Local control-plane service used by CLI/API/Web
  cli/           # Command-line entry point
  server/        # REST API entry point

web/             # Vue/TypeScript evaluation UI
docs/            # Design docs
examples/        # Demo agents and datasets
tests/           # Test suite
```

The five core evaluation objects remain `Case -> Run + Trace -> Evaluator -> Result`.
Experiment, queue, optimizer, and lineage are product modules composed around that core;
they do not replace it. See `docs/capability-mapping.md` for capability ownership and
implementation status.

## First Demo Target

The first demo should be a loan approval agent:

- The agent may create a loan application.
- The agent must not approve high-risk loans directly.
- Approval may require human review.
- Evaluators check tool calls, tool arguments, workflow policy, and final state.

## P1 Demo

The repository contains a working SQLite-backed loan-approval evaluation slice with a deterministic target, CLI, REST/OTLP HTTP endpoints, and Chinese Vue UI. See `docs/progress.md` for verified implementation status and `docs/demo-test-guide.md` for the complete setup and test walkthrough.
