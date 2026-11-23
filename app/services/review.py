from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services import page_merge as page_merge_svc
from app.services import rework as rework_svc
from app.services.errors import ServiceError


def list_tickets(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT t.*, r.status AS row_status, r.reason, i.item_key, b.bin_code,
              (
                SELECT m.badge FROM page_merges m
                WHERE m.batch_id=i.batch_id ORDER BY m.id DESC LIMIT 1
              ) AS merge_badge
            FROM review_tickets t
            JOIN quarantine_rows r ON r.id=t.row_id
            JOIN capture_items i ON i.id=r.item_id
            JOIN quarantine_bins b ON b.id=r.bin_id
            ORDER BY t.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def decide(
    ticket_id: int,
    decision: str,
    reviewer: str = "admin",
    comment: str = "",
    db_path: str | None = None,
) -> dict:
    if decision not in ("放行", "驳回回炉", "废弃"):
        raise ServiceError("裁决无效")
    with get_db(db_path) as conn:
        ticket = conn.execute(
            "SELECT * FROM review_tickets WHERE id=?", (ticket_id,)
        ).fetchone()
        if not ticket:
            raise ServiceError("复核单不存在", 404)
        if ticket["decision"] != "待决":
            raise ServiceError("复核单已裁决")
        row = conn.execute(
            "SELECT * FROM quarantine_rows WHERE id=?", (ticket["row_id"],)
        ).fetchone()
        if not row or row["status"] != "待复核":
            raise ServiceError("隔离行不可裁决")
        item = conn.execute(
            "SELECT * FROM capture_items WHERE id=?", (row["item_id"],)
        ).fetchone()
        if decision == "放行":
            page_merge_svc.assert_release_allowed(conn, item)
        elif decision == "驳回回炉":
            page_merge_svc.assert_rework_allowed(conn, item)
        conn.execute(
            """
            UPDATE review_tickets
            SET decision=?, reviewer=?, comment=?, decided_at=datetime('now')
            WHERE id=?
            """,
            (decision, reviewer or "admin", comment or "", ticket_id),
        )
        if decision == "放行":
            conn.execute(
                "UPDATE quarantine_rows SET status='已放行' WHERE id=?", (row["id"],)
            )
            conn.execute(
                "UPDATE capture_items SET status='已放行' WHERE id=?", (row["item_id"],)
            )
        elif decision == "驳回回炉":
            conn.execute(
                "UPDATE quarantine_rows SET status='回炉中' WHERE id=?", (row["id"],)
            )
            conn.execute(
                "UPDATE capture_items SET status='回炉中' WHERE id=?", (row["item_id"],)
            )
            active_job = conn.execute(
                """
                SELECT id FROM rework_jobs
                WHERE row_id=? AND status IN ('排队','执行中')
                """,
                (row["id"],),
            ).fetchone()
            if not active_job:
                rework_svc._enqueue(conn, row["id"], "复核驳回回炉")
        else:
            conn.execute(
                "UPDATE quarantine_rows SET status='已废弃' WHERE id=?", (row["id"],)
            )
            conn.execute(
                "UPDATE capture_items SET status='已关闭' WHERE id=?", (row["item_id"],)
            )
        out = conn.execute(
            """
            SELECT t.*, r.status AS row_status, i.item_key
            FROM review_tickets t
            JOIN quarantine_rows r ON r.id=t.row_id
            JOIN capture_items i ON i.id=r.item_id
            WHERE t.id=?
            """,
            (ticket_id,),
        ).fetchone()
    audit_svc.write_event("复核裁决", "review_ticket", ticket_id, decision, db_path=db_path)
    return dict(out)
