# Control Plane Design

## Status

This is the proposed architecture, not a claim that every file and API already exists. See [progress.md](../progress.md) for verified implementation status.

## Terms

| Term | Responsibility |
| --- | --- |
| Control panel | Web UI for configuring data, launching evaluations, and reading reports. |
| Control plane | Owns jobs, queueing, scheduling, cancellation, retry, and job status. |
| Execution | AgentGate-owned processing request created when a control-plane Job is submitted for evaluation. |
| Run | AgentGate's persisted domain record for one Execution. |
| Run service | Stable boundary for run creation, idempotency, status, cancellation, and reports. |
| Run engine | Executes Cases, captures traces, and runs evaluators. |

The control panel is a UI. The control plane is a backend orchestration component.

### Ownership rule

```text
Control-plane Job ownership
             !=
AgentGate Execution and Run ownership
```

The active control plane owns `job_id`, queue position, scheduling, retries, and job-level cancellation. AgentGate owns `execution_id`, the internal Run, trace, evaluator results, metrics, and the gate decision. Each accepted Execution maps to exactly one Run. External callers receive only the opaque `execution_id`; the internal `run_id` is not part of the integration contract.

## Workflow comparison

| Stage | AgentGate standalone | External control plane |
| --- | --- | --- |
| User entry | AgentGate Web UI | External Web UI or service |
| Job owner | AgentGate control plane | External control plane |
| Queue and scheduler | AgentGate local POC implementation | External implementation |
| Execution boundary | Local Python `RunExecution` interface | AgentGate Internal Execution API |
| Shared path | Run service -> Run engine -> evaluators | Run service -> Run engine -> evaluators |
| Results | AgentGate job/report API | AgentGate execution/result API |

```text
Standalone:
AgentGate Web -> Web API -> local control plane -> local queue/scheduler
              -> Python RunExecution -> Run service -> Run engine -> evaluators

External:
External Web -> external control plane -> external queue/scheduler
             -> AgentGate Internal Execution API -> integration adapter
             -> Run service -> Run engine -> evaluators
```

Only one control plane owns a job. In external mode, AgentGate does not add a second production queue or scheduler.

## Recommended architecture

```text
                     AgentGate
┌──────────────────────────────────────────────────────┐
│ Public API                 Internal Execution API    │
│     │                               │                │
│ Local control plane                │                │
│     │                               │                │
│ Local queue/scheduler               │                │
│     └───────────────┬───────────────┘                │
│                     v                                │
│                 Run service                          │
│                     │                                │
│                  Run engine                           │
│                     │                                │
│        Target -> Trace -> Evaluators                  │
│                     │                                │
│        Results -> Metrics -> Gate                     │
└──────────────────────────────────────────────────────┘
                            ^
                            │
                  External control plane
                  Queue + scheduler + Job
```

## Proposed code structure

```text
src/agentgate/
├── server/
│   ├── app.py
│   └── api.py
├── control_plane/
│   ├── models.py
│   ├── repository.py
│   ├── queue.py
│   ├── scheduler.py
│   └── service.py
├── integrations/
│   └── external_control_plane/
│       ├── api.py
│       ├── contracts.py
│       ├── mapper.py
│       ├── auth.py
│       └── callbacks.py
├── run/
│   ├── interface.py
│   ├── service.py
│   └── engine.py
├── domain/run.py
└── storage/
    ├── base.py
    └── sqlite.py
```

## File responsibilities

| File | Responsibility |
| --- | --- |
| `server/app.py` | Creates FastAPI and registers public and internal APIs. |
| `server/api.py` | APIs used by AgentGate's own Web UI. |
| `control_plane/models.py` | Local job, queue, retry, and scheduling models. |
| `control_plane/repository.py` | Persistence interface for control-plane jobs. |
| `control_plane/queue.py` | Local POC queue implementation. |
| `control_plane/scheduler.py` | Selects and dispatches runnable local jobs; not a production scheduler. |
| `control_plane/service.py` | Local job lifecycle, retry, cancellation, and status transitions. |
| `integrations/external_control_plane/api.py` | Inbound Internal Execution API for an external control plane. |
| `integrations/external_control_plane/contracts.py` | External request and response models. |
| `integrations/external_control_plane/mapper.py` | Maps external requests to Run requests and maps responses back. |
| `integrations/external_control_plane/auth.py` | Authenticates external control-plane calls. |
| `integrations/external_control_plane/callbacks.py` | Delivers optional signed status callbacks; polling remains available as fallback. |
| `run/interface.py` | Stable Python execution interface for the local control plane. |
| `run/service.py` | Run lifecycle, idempotency, cancellation, status, and reports. |
| `run/engine.py` | Case execution, trace capture, and evaluator invocation. |
| `domain/run.py` | Shared Pydantic run requests, snapshots, status, and identity. |
| `storage/base.py` | Persistence interfaces suitable for SQLite and later PostgreSQL. |
| `storage/sqlite.py` | POC SQLite persistence. |

The external integration is inbound: an external control plane owns scheduling and calls AgentGate. No outbound scheduler adapter is needed for this design.

## API and interface design

### AgentGate Web to local control plane

```text
POST /api/v1/jobs
GET  /api/v1/jobs/{job_id}
POST /api/v1/jobs/{job_id}/cancel
GET  /api/v1/jobs/{job_id}/report
```

These endpoints represent control-plane jobs. A queued job may exist before a Run is created.

### Local control plane to Run service

```python
class RunExecution(Protocol):
    def execute(self, request: RunRequest) -> Run: ...
    def status(self, run_id: str) -> RunStatus: ...
    def cancel(self, run_id: str) -> None: ...
    def report(self, run_id: str) -> RunReport: ...
```

### External control plane to AgentGate Internal Execution API

```text
POST /internal/v1/executions
GET  /internal/v1/executions/{execution_id}
POST /internal/v1/executions/{execution_id}/cancel
GET  /internal/v1/executions/{execution_id}/result
```

A submission must include:

- `external_job_id`
- `idempotency_key`
- immutable `target_snapshot` or a versioned target reference
- `dataset_version`
- `evaluator_versions`
- `execution_config`
- optional `callback_url`

A successful submission returns `execution_id` and status. The external control plane stores the `external_job_id` to `execution_id` mapping. If a callback URL is supplied, AgentGate signs callback requests. Status and result polling always remains available as a fallback.

## Boundary rules

1. Retrying the same idempotency key returns the same Execution and Run instead of duplicating work.
2. RunSnapshot records versioned target, Dataset, evaluators, MetricPlan, and GateSpec.
3. Internal APIs are versioned under `/internal/v1` and use service authentication.
4. AgentGate and an external control plane do not share a database.
5. Cancellation is cooperative and applied by Run service at safe execution boundaries.
6. Historical persisted reports are immutable.
7. Both modes produce the same canonical Run, Trace, Result, Metric, and Gate models.
8. Callback payloads include `execution_id`, status, event time, and signature; callbacks are retried safely and never replace polling.
9. A control-plane retry must reuse its idempotency key. A new key explicitly requests a new Execution.

## P1 boundary

P1 may use a local in-process queue and scheduler for the standalone demo. Interfaces must allow later replacement without changing RunEngine. A production distributed scheduler and full external control-plane integration are outside P1.
