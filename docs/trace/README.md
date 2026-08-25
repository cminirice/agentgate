# Trace

The current Trace implementation owns bounded OTLP ingestion, canonical semantic
conversion, deterministic reconstruction, and lifecycle protection:

```text
trace/
├── models.py
├── receivers/otlp_http.py
├── normalizer.py
├── ordering.py
├── merge.py
├── completeness.py
└── service.py
```

`POST /v1/traces` accepts OTLP/HTTP JSON and protobuf, including gzip. The receiver
decodes transport data, the normalizer produces `TraceBatch`, the service validates
Run/Case/Turn/Target correlation, and SQLite persists spans, semantic signals,
conflicts, and immutable canonical Trace revisions. `GET
/api/runs/{run_id}/traces/{case_id}` returns the latest canonical Trace.

Domain Trace models and invariants remain in `domain/`; persistence remains in
`storage/`. Vendor importers and OTLP/gRPC remain future observability integrations.

The [ingestion plan](ingestion-plan.md) records the implemented contract and explicitly
lists the remaining cross-module work. Its pre-refactor file map is not authoritative.
