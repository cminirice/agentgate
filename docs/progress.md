# P1 Demo Progress

## Current checkpoint

The P1 loan-approval vertical slice is implemented on `goal/p1-demo`.

- Immutable Pydantic contracts cover cases, datasets, targets, runs, snapshots, canonical traces, evaluators, evidence, results, and gate decisions.
- `AgentGateRepository` is the persistence boundary; `SQLiteRepository` persists runs, traces, results, and demo business state. A PostgreSQL adapter can implement the same protocol later.
- The demo target exposes loan approval, credit inquiry, repayment plan, and complaint capabilities. `loan-agent-v1-risky` directly approves the high-risk case; `loan-agent-v2-fixed` sends it to human review.
- Deterministic execution is the default. An optional OpenAI-compatible provider is isolated behind `AgentProvider`.
- `LocalScheduler` is the POC executor behind `ExternalSchedulerAdapter`; no production scheduler is included.
- FastAPI and Typer use the same `EvaluationService`.
- OTLP/HTTP JSON ingestion is available at `POST /v1/traces`; health is separate at `GET /health`. OTLP/gRPC remains an intentionally reserved boundary.
- The Vue 3, TypeScript, and Element Plus UI uses real API calls for overview, launch, run detail, result summary, and failed-case trace drill-down.
- Failure attribution is labelled `primary_failure_step`, meaning the first observed failing step; it is not presented as a proven root cause.

## Setup

Python 3.11+ and Node.js are required.

```bash
python3 -m pip install -e '.[test]'
cd web
npm install
npx playwright install chromium
```

On minimal Linux images, install the browser libraries printed by `npx playwright install-deps chromium` using the operating system package manager.

## Run the demo

```bash
agentgate evaluate --version loan-agent-v1-risky --database ./agentgate.db
agentgate evaluate --version loan-agent-v2-fixed --database ./agentgate.db
AGENTGATE_DB=./agentgate.db uvicorn agentgate.server.application:app --reload
cd web && npm run dev
```

Open `http://127.0.0.1:5173`. The Vite development server proxies API calls to FastAPI at `http://127.0.0.1:8000`.

## Verification

```bash
python3 -m pytest -q
python3 -m pip wheel . --no-deps --wheel-dir /tmp/agentgate-wheel
cd web
npm audit
npm run typecheck
npm run build
npm run test:e2e
```

The deterministic acceptance expectation is:

| Target version | Expected gate | Reason |
| --- | --- | --- |
| `loan-agent-v1-risky` | fail | Direct high-risk approval violates required-tool, forbidden-tool, argument, final-state, and policy checks. |
| `loan-agent-v2-fixed` | pass | High-risk applications enter human review and all deterministic checks pass. |

## Remaining work outside P1

- PostgreSQL adapter and migrations.
- OTLP/gRPC receiver.
- Production external-scheduler integration.
- Full experiment, queue, optimizer, and lineage feature sets.
- Public benchmark integrations.
