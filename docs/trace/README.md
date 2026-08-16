# Trace

This module owns the canonical vendor-neutral Trace, OTLP/HTTP receivers, future
importers, and normalization. Evaluators consume the canonical domain Trace rather than
provider-specific telemetry payloads.

Detailed plans:

- [Canonical Trace ingestion](ingestion-plan.md): correlation, multi-batch merge,
  deduplication, deterministic ordering, completeness, late arrivals, persistence, and
  OTLP/HTTP behavior.
