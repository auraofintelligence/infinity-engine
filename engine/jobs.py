"""Job payloads and the SQLite run log.

A job is a folder: spec.json plus any reference assets. That folder is
the ONLY thing that ever travels to a GPU worker; the vault and the
orchestration stay on the trusted machine. Results come back into the
same folder under results/.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    song_slug TEXT NOT NULL,
    kind TEXT NOT NULL,          -- panels | keyframes | video | tts | lipsync
    tier TEXT NOT NULL,          -- draft | standard | premium
    provider TEXT,               -- key from providers.yaml models
    runner TEXT,                 -- key from providers.yaml runners
    status TEXT NOT NULL,        -- queued | running | done | failed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    cost_usd REAL,
    notes TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def create_job(jobs_dir: Path, conn: sqlite3.Connection, *, song_slug: str,
               kind: str, tier: str, provider: str | None,
               runner: str, spec: dict) -> Path:
    job_id = f"{song_slug}-{kind}-{uuid.uuid4().hex[:8]}"
    job_dir = jobs_dir / job_id
    (job_dir / "results").mkdir(parents=True)
    spec = {"id": job_id, "song_slug": song_slug, "kind": kind,
            "tier": tier, "provider": provider, **spec}
    (job_dir / "spec.json").write_text(
        json.dumps(spec, indent=2), encoding="utf-8")
    conn.execute(
        "INSERT INTO jobs (id, song_slug, kind, tier, provider, runner,"
        " status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (job_id, song_slug, kind, tier, provider, runner, "queued",
         _now(), _now()))
    conn.commit()
    return job_dir


def set_status(conn: sqlite3.Connection, job_id: str, status: str,
               cost_usd: float | None = None, notes: str | None = None):
    conn.execute(
        "UPDATE jobs SET status=?, updated_at=?,"
        " cost_usd=COALESCE(?, cost_usd), notes=COALESCE(?, notes)"
        " WHERE id=?",
        (status, _now(), cost_usd, notes, job_id))
    conn.commit()


def list_jobs(conn: sqlite3.Connection, limit: int = 50) -> list[tuple]:
    return conn.execute(
        "SELECT id, kind, tier, status, cost_usd, updated_at FROM jobs"
        " ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
