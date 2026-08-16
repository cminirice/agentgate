# P1 Demo Progress

## Current checkpoint

The P1 loan-approval vertical slice is implemented on `goal/p1-demo`.

- Focused immutable Pydantic models under `domain/` cover Expectations, Cases,
  Datasets, evaluator specifications, canonical Traces, detailed Results, Metric plans,
  Gate specifications, Runs, and reports. Nested JSON is recursively immutable.
- RunSnapshot persists the full Dataset, target, evaluator specifications, primary
  evaluator IDs, MetricPlan, GateSpec, and a canonical SHA-256 content hash.
- `AgentGateRepository` is the persistence boundary; `SQLiteRepository` persists
  Dataset catalogs and versions, runs, traces, results, and demo business state. A
  PostgreSQL adapter can implement the same protocol later.
- The demo target exposes loan approval, credit inquiry, repayment plan, and complaint capabilities. `loan-agent-v1-risky` directly approves the high-risk case; `loan-agent-v2-fixed` sends it to human review.
- Deterministic execution is the default. An optional OpenAI-compatible provider is isolated behind `AgentProvider`.
- `LocalScheduler` is the POC executor behind `ExternalSchedulerAdapter`; no production scheduler is included.
- FastAPI and Typer use the same `EvaluationService`.
- OTLP/HTTP JSON ingestion is available at `POST /v1/traces`; parsing and normalization
  live under `trace/`, while the FastAPI route only delegates. Health is separate at
  `GET /health`. OTLP/gRPC remains an intentionally reserved boundary.
- The Vue 3, TypeScript, and Element Plus UI uses real API calls for overview, launch, run
  detail, result summary, failed-case trace drill-down, and the three-column Dataset/Case
  workspace. Draft editing, immutable publishing, JSON import/export, and version-aware
  evaluation all persist through SQLite.
- Seven deterministic Rule evaluators cover routing, required tools, forbidden tools, tool
  arguments, final state, final output, and policy compliance. LLM Judge and Hybrid have version-1
  contracts but runtime execution remains P2.
- Not-applicable checks use `outcome=not_applicable` and `score=null`. Evaluator
  crashes, timeouts, and malformed output use `outcome=error`, fail the Gate closed,
  and never assign an agent failure stage.
- Failure attribution is labelled `primary_failure_step`, meaning the first
  trace-sequenced observed failing stage; it is not presented as a proven root cause.
- Report metrics expose metric, dimension, evaluator-kind, and overall summaries. Kind
  summaries are a parallel reporting view and never feed the overall score.

## Setup

Python 3.11+ and Node.js are required.

```bash
python3 -m pip install -e '.[test]'
cd web
npm install
npx playwright install chromium
npx playwright install-deps chromium
```

The dependency command may require root privileges on minimal Linux images. If sudo is
not available, ask the machine administrator to install the printed browser libraries.

The refactor intentionally does not migrate old disposable P1 payloads. Stop the backend,
rename the old SQLite file as a backup, and start with a fresh database.

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

Current automated evidence:

- Python: 47 focused unit/API/CLI/integration tests pass.
- Vue TypeScript typecheck: pass.
- Vue production build: pass.
- Playwright: 6 desktop and Pixel 7 checks pass. Tests use dedicated ports 18000/15173 and
  a per-run SQLite database, so they never reuse the public demo service or old payloads.

The deterministic acceptance expectation is:

| Target version | Expected gate | Reason |
| --- | --- | --- |
| `loan-agent-v1-risky` | fail | Direct high-risk approval violates required-tool, forbidden-tool, final-state, and policy checks; the missing review tool makes its argument check not applicable. |
| `loan-agent-v2-fixed` | pass | High-risk applications enter human review and all deterministic checks pass. |

## Remaining work outside P1

- PostgreSQL adapter and migrations.
- OTLP/gRPC receiver.
- Production external-scheduler integration.
- Full experiment, queue, optimizer, and lineage feature sets.
- Public benchmark integrations.
- LLM Judge and Hybrid evaluator runtime.
- A/B consistency enforcement.
- JSON Schema and ordered-sequence operators.
