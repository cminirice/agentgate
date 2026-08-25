# Run

The Run capability owns deterministic execution mechanics:

```text
run/
├── engine.py
├── process_manager.py
├── retry.py
├── manifest.py
├── artifacts.py
└── target_protocol.py
```

Complete Run lifecycle orchestration belongs in `application/run_management.py`.
Concrete Agent integrations belong in `integrations/targets/`, and Celery background
submission belongs in `integrations/job_dispatchers/`.

Detailed plans:

- [External target integration](external-target-plan.md)
- [Instrumented Demo Agent](demo-agent-plan.md)

Both plans retain useful contracts and acceptance criteria, but their pre-refactor file
maps are not authoritative.
