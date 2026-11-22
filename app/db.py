from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_sites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  site_code TEXT NOT NULL UNIQUE,
  site_name TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('启用','停用','观察')),
  daily_quota INTEGER NOT NULL DEFAULT 100,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS policy_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  quality_match TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('入舱','直接关闭','观察')),
  target_bin_code TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT NOT NULL DEFAULT 'admin',
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER NOT NULL DEFAULT 0,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS capture_batches (

  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_code TEXT NOT NULL UNIQUE,
  source_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('采集中','已收齐','已关闭')),
  item_count INTEGER NOT NULL DEFAULT 0,
  bad_count INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS capture_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES capture_batches(id),
  item_key TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '',
  quality TEXT NOT NULL CHECK (quality IN ('合格','缺字段','编码空','重复键')),
  status TEXT NOT NULL CHECK (status IN ('待检','入舱','已放行','回炉中','已关闭')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(batch_id, item_key)
);

CREATE TABLE IF NOT EXISTS quarantine_bins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bin_code TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('开放','锁定','已归档')),
  capacity INTEGER NOT NULL DEFAULT 100,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quarantine_rows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bin_id INTEGER NOT NULL REFERENCES quarantine_bins(id),
  item_id INTEGER NOT NULL REFERENCES capture_items(id),
  reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('待复核','已放行','回炉中','已废弃')),
  entered_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(item_id)
);

CREATE TABLE IF NOT EXISTS review_tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_code TEXT NOT NULL UNIQUE,
  row_id INTEGER NOT NULL REFERENCES quarantine_rows(id),
  decision TEXT NOT NULL CHECK (decision IN ('待决','放行','驳回回炉','废弃')),
  reviewer TEXT NOT NULL DEFAULT '',
  comment TEXT NOT NULL DEFAULT '',
  decided_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rework_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_code TEXT NOT NULL UNIQUE,
  row_id INTEGER NOT NULL REFERENCES quarantine_rows(id),
  status TEXT NOT NULL CHECK (status IN ('排队','执行中','成功','失败')),
  attempt INTEGER NOT NULL DEFAULT 1,
  message TEXT NOT NULL DEFAULT '',
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reconcile_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  summary TEXT NOT NULL,
  open_rows INTEGER NOT NULL,
  released INTEGER NOT NULL,
  reworking INTEGER NOT NULL,
  abandoned INTEGER NOT NULL,
  mismatch INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lab_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def ensure_db() -> Path:
    Config.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    path = Config.DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    return path


@contextmanager
def get_db(db_path: str | Path | None = None):
    path = Path(db_path) if db_path else Config.DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _meta_get(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
