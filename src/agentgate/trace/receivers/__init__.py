"""Trace receiver entry points."""

from .otlp_http import ingest_otlp_http_json

__all__ = ["ingest_otlp_http_json"]
