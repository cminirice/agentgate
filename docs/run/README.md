# Run

This module owns immutable Run snapshots, target execution, lifecycle, and the local POC
scheduler boundary. Add detailed plans here when Run behavior changes.

Dataset content, evaluator definitions, MetricPlan, and GateSpec are captured by the Run
but remain owned by their respective modules.

Detailed plans:

- [External target integration](external-target-plan.md): Agent/Skill target terminology,
  external metadata/version adapters, immutable TargetSnapshot, execution adapters, and
  Trace correlation.
- [Instrumented Demo Agent](demo-agent-plan.md): deterministic loan Agent HTTP service,
  OpenTelemetry SDK spans, OTLP export, and end-to-end evaluation acceptance.
