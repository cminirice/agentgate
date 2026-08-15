from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agentgate.contracts import Result, Run, Trace


class SQLiteRepository:
    """Small JSON-document adapter with a stable domain-facing repository contract."""

    def __init__(self, path: str | Path = "agentgate.db") -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(run_id, case_id)
                );
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS business_state (
                    namespace TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(namespace, key)
                );
                CREATE INDEX IF NOT EXISTS idx_traces_run ON traces(run_id);
                CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id);
                """
            )

    @staticmethod
    def _json(model: Run | Trace | Result) -> str:
        return model.model_dump_json()

    def save_run(self, run: Run) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs(id,status,created_at,payload) VALUES(?,?,?,?)",
                (run.id, run.status, run.snapshot.created_at.isoformat(), self._json(run)),
            )

    def get_run(self, run_id: str) -> Run | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
        return Run.model_validate_json(row[0]) if row else None

    def list_runs(self, limit: int = 50) -> list[Run]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Run.model_validate_json(row[0]) for row in rows]

    def save_trace(self, trace: Trace) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO traces(id,run_id,case_id,payload) VALUES(?,?,?,?)",
                (trace.id, trace.run_id, trace.case_id, self._json(trace)),
            )

    def get_trace(self, run_id: str, case_id: str) -> Trace | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM traces WHERE run_id=? AND case_id=?", (run_id, case_id)
            ).fetchone()
        return Trace.model_validate_json(row[0]) if row else None

    def list_traces(self, run_id: str) -> list[Trace]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM traces WHERE run_id=? ORDER BY case_id", (run_id,)
            ).fetchall()
        return [Trace.model_validate_json(row[0]) for row in rows]

    def save_results(self, results: list[Result]) -> None:
        with self._connect() as db:
            db.executemany(
                "INSERT OR REPLACE INTO results(id,run_id,case_id,payload) VALUES(?,?,?,?)",
                [(r.id, r.run_id, r.case_id, self._json(r)) for r in results],
            )

    def list_results(self, run_id: str) -> list[Result]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM results WHERE run_id=? ORDER BY case_id,id", (run_id,)
            ).fetchall()
        return [Result.model_validate_json(row[0]) for row in rows]

    def put_business_state(self, namespace: str, key: str, value: dict) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO business_state(namespace,key,payload) VALUES(?,?,?)",
                (namespace, key, json.dumps(value, ensure_ascii=False)),
            )

    def get_business_state(self, namespace: str, key: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM business_state WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
        return json.loads(row[0]) if row else None
