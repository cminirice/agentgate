# Current Implementation Progress

Verified on branch `codex/trace-ingestion` at merge commit `018a769` on 2026-08-25.
The Python suite passes with **169 tests**; source compilation, wheel build, and Git diff
checks also pass.

## Capability Status

| Capability | Status | Current behavior |
| --- | --- | --- |
| Dataset/Case lifecycle | Implemented | Draft, validation, immutable publication, snapshots, single- and multi-turn Cases |
| Regression set | Implemented | Copy a snapshotted Case with provenance into a regression Dataset draft, prevent duplicate membership, publish and run normally |
| Single-Case rerun | Implemented | Create a child Run for one historical Case and retain parent/root/rerun identity and comparison data |
| Python/Demo Target | Implemented | Executes through `PythonFunctionTarget` and can return an inline canonical Trace |
| HTTP External Target | Implemented P1 path | Target request/result contracts, `traceparent`, idempotency header, pending Trace correlation, bounded HTTP adapter, and Trace wait |
| OTLP receiver | Implemented HTTP path | `POST /v1/traces` accepts JSON or protobuf and identity/gzip encoding with bounded decompression |
| OTLP normalization | Implemented | Strict IDs/correlation, OTel/OpenInference/GenAI kinds, attributes, scope, events, links, status, signals, and partial rejection |
| Canonical Trace | Implemented | Idempotent persistence, conflicts, deterministic ordering, multi-source merge, TraceTurns, completeness/deadline, immutable revisions, late arrival |
| Trace retrieval | Implemented | `GET /api/runs/{run_id}/traces/{case_id}` returns the latest canonical revision |
| Evaluation binding | Implemented | Only complete Trace is evaluated in the ingestion path; Result records Trace revision and content hash |
| Web evaluation flow | Implemented P1 UI | Dataset selection, launch/report/Trace views, regression action, and single-Case rerun workflows |

## Important Runtime Distinction

`POST /v1/traces` receives telemetry; it does not start an evaluation.

```text
Python/Demo Target -> inline Trace -----------------------+
                                                         +-> Evaluators -> Results
HTTP Target -> Agent OTel export -> POST /v1/traces -----+
```

The built-in loan Demo normally uses the inline path. An instrumented HTTP Target uses
the OTLP path, after which RunEngine waits for and evaluates the reconstructed canonical
Trace.

## Remaining Work

- OTLP/gRPC and vendor-specific importers;
- production Target catalog/discovery and Invocation registry;
- process and trace-only Target adapters;
- production credential vault, retry/cancellation scheduler, and background deadline
  worker;
- automatic evaluator/rerun workflow for late-arrival Trace revisions;
- public conflict/debug API and production ingestion telemetry;
- richer Target/Skill/tool descriptors and management UI;
- production authorization, tenancy, retention, and distributed ingestion.

## Related Documents

- [Trace ingestion plan](trace/ingestion-plan.md)
- [HTTP Target and OTel correlation](run/http-target-short-term-plan.md)
- [External Target integration](run/external-target-plan.md)
- [Regression-set design](dataset/regression-set-design.md)
- [Regression-set implementation](dataset/regression-set-plan.md)
- [Historical P1 walkthrough](history/p1-demo/demo-test-guide.md)
