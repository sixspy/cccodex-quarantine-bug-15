from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services import settings as settings_svc
from app.services.errors import ServiceError


def list_reports(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM reconcile_reports ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def run_reconcile(db_path: str | None = None) -> dict:
    label = settings_svc.get_value("reconcile_label", "隔离对账", db_path)
    with get_db(db_path) as conn:
        open_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_rows WHERE status='待复核'"
        ).fetchone()["c"]
        released = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_rows WHERE status='已放行'"
        ).fetchone()["c"]
        reworking = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_rows WHERE status='回炉中'"
        ).fetchone()["c"]
        abandoned = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_rows WHERE status='已废弃'"
        ).fetchone()["c"]
        # mismatch: item says 入舱 but no open quarantine row
        mismatch = conn.execute(
            """
            SELECT COUNT(*) AS c FROM capture_items i
            WHERE i.status='入舱'
              AND NOT EXISTS (
                SELECT 1 FROM quarantine_rows r
                WHERE r.item_id=i.id AND r.status IN ('待复核','回炉中')
              )
            """
        ).fetchone()["c"]
        summary = (
            f"{label}：待复核{open_rows} / 已放行{released} / 回炉中{reworking} / "
            f"已废弃{abandoned} / 错位{mismatch}"
        )
        cur = conn.execute(
            """
            INSERT INTO reconcile_reports(
              summary, open_rows, released, reworking, abandoned, mismatch
            ) VALUES (?,?,?,?,?,?)
            """,
            (summary, open_rows, released, reworking, abandoned, mismatch),
        )
        report_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM reconcile_reports WHERE id=?", (report_id,)
        ).fetchone()
    audit_svc.write_event("生成对账", "reconcile_report", report_id, summary, db_path=db_path)
    return dict(row)


def dashboard(db_path: str | None = None) -> dict:
    from app.services.page_merge import spec as _page_merge_spec
    with get_db(db_path) as conn:
        return {
            "batches": conn.execute("SELECT COUNT(*) AS c FROM capture_batches").fetchone()["c"],
            "items": conn.execute("SELECT COUNT(*) AS c FROM capture_items").fetchone()["c"],
            "pending_rows": conn.execute(
                "SELECT COUNT(*) AS c FROM quarantine_rows WHERE status='待复核'"
            ).fetchone()["c"],
            "tickets_open": conn.execute(
                "SELECT COUNT(*) AS c FROM review_tickets WHERE decision='待决'"
            ).fetchone()["c"],
            "rework_queue": conn.execute(
                "SELECT COUNT(*) AS c FROM rework_jobs WHERE status IN ('排队','执行中')"
            ).fetchone()["c"],
            "reports": conn.execute("SELECT COUNT(*) AS c FROM reconcile_reports").fetchone()["c"],
            "sites": conn.execute("SELECT COUNT(*) AS c FROM source_sites").fetchone()["c"],
            "rules": conn.execute(
                "SELECT COUNT(*) AS c FROM policy_rules WHERE enabled=1"
            ).fetchone()["c"],
            "audits": conn.execute("SELECT COUNT(*) AS c FROM audit_events").fetchone()["c"],
            "page_merge": _page_merge_spec(db_path),
        }
