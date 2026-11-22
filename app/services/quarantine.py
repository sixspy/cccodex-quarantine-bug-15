from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services import settings as settings_svc
from app.services.errors import ServiceError


def list_bins(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT b.*,
              (SELECT COUNT(*) FROM quarantine_rows r WHERE r.bin_id=b.id AND r.status='待复核') AS pending_count,
              (SELECT COUNT(*) FROM quarantine_rows r WHERE r.bin_id=b.id) AS row_count
            FROM quarantine_bins b ORDER BY b.id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_rows(bin_id: int | None = None, db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        if bin_id:
            rows = conn.execute(
                """
                SELECT r.*, i.item_key, i.quality, i.batch_id, b.bin_code, b.title AS bin_title
                FROM quarantine_rows r
                JOIN capture_items i ON i.id=r.item_id
                JOIN quarantine_bins b ON b.id=r.bin_id
                WHERE r.bin_id=?
                ORDER BY r.id DESC
                """,
                (bin_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.*, i.item_key, i.quality, i.batch_id, b.bin_code, b.title AS bin_title
                FROM quarantine_rows r
                JOIN capture_items i ON i.id=r.item_id
                JOIN quarantine_bins b ON b.id=r.bin_id
                ORDER BY r.id DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]


def enter_item(item_id: int, bin_id: int, reason: str, db_path: str | None = None) -> dict:
    reason = (reason or "").strip() or "质量异常入舱"
    with get_db(db_path) as conn:
        item = conn.execute("SELECT * FROM capture_items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise ServiceError("条目不存在", 404)
        if item["status"] not in ("待检",):
            raise ServiceError("仅待检条目可入舱")
        if item["quality"] == "合格":
            raise ServiceError("合格条目不应入舱")
        bin_row = conn.execute("SELECT * FROM quarantine_bins WHERE id=?", (bin_id,)).fetchone()
        if not bin_row:
            raise ServiceError("隔离舱不存在", 404)
        if bin_row["status"] != "开放":
            raise ServiceError("隔离舱未开放")
        open_bins = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_bins WHERE status='开放'"
        ).fetchone()["c"]
        max_open = int(settings_svc.get_value("max_bin_open", "3", db_path) or "3")
        if open_bins > max_open:
            raise ServiceError("开放隔离舱超过上限")
        occupied = conn.execute(
            "SELECT COUNT(*) AS c FROM quarantine_rows WHERE bin_id=? AND status IN ('待复核','回炉中')",
            (bin_id,),
        ).fetchone()["c"]
        if occupied >= bin_row["capacity"]:
            raise ServiceError("隔离舱已满")
        exists = conn.execute(
            "SELECT id FROM quarantine_rows WHERE item_id=?", (item_id,)
        ).fetchone()
        if exists:
            raise ServiceError("条目已在隔离舱")
        cur = conn.execute(
            """
            INSERT INTO quarantine_rows(bin_id, item_id, reason, status)
            VALUES (?, ?, ?, '待复核')
            """,
            (bin_id, item_id, reason),
        )
        conn.execute(
            "UPDATE capture_items SET status='入舱' WHERE id=?", (item_id,)
        )
        n = conn.execute("SELECT COUNT(*) AS c FROM review_tickets").fetchone()["c"] + 1
        conn.execute(
            """
            INSERT INTO review_tickets(ticket_code, row_id, decision, comment)
            VALUES (?, ?, '待决', ?)
            """,
            (f"REV-{n:04d}", cur.lastrowid, "入舱自动开复核单"),
        )
        row_id = cur.lastrowid
        row = conn.execute(
            """
            SELECT r.*, i.item_key, i.quality, b.bin_code
            FROM quarantine_rows r
            JOIN capture_items i ON i.id=r.item_id
            JOIN quarantine_bins b ON b.id=r.bin_id
            WHERE r.id=?
            """,
            (row_id,),
        ).fetchone()
    audit_svc.write_event("入舱", "quarantine_row", row_id, reason, db_path=db_path)
    return dict(row)


def auto_enter_bad(batch_id: int, bin_id: int, db_path: str | None = None) -> dict:
    auto = settings_svc.get_value("auto_enter_bad", "1", db_path)
    if auto != "1":
        raise ServiceError("未开启自动入舱")
    with get_db(db_path) as conn:
        items = conn.execute(
            """
            SELECT id FROM capture_items
            WHERE batch_id=? AND quality!='合格' AND status='待检'
            """,
            (batch_id,),
        ).fetchall()
    entered = []
    for it in items:
        entered.append(enter_item(it["id"], bin_id, "批内自动入舱", db_path))
    return {"entered": len(entered), "rows": entered}
