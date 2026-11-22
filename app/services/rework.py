from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services import settings as settings_svc
from app.services.errors import ServiceError


def list_jobs(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT j.*, i.item_key, r.reason, b.bin_code
            FROM rework_jobs j
            JOIN quarantine_rows r ON r.id=j.row_id
            JOIN capture_items i ON i.id=r.item_id
            JOIN quarantine_bins b ON b.id=r.bin_id
            ORDER BY j.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def run_job(job_id: int, succeed: bool = True, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        job = conn.execute("SELECT * FROM rework_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise ServiceError("回炉任务不存在", 404)
        if job["status"] not in ("排队", "失败"):
            raise ServiceError("任务状态不可执行")
        max_attempt = int(settings_svc.get_value("rework_max_attempt", "3", db_path) or "3")
        if job["attempt"] > max_attempt:
            raise ServiceError("已超过回炉最大次数")
        conn.execute(
            """
            UPDATE rework_jobs SET status='执行中', started_at=datetime('now')
            WHERE id=?
            """,
            (job_id,),
        )
        if succeed:
            conn.execute(
                """
                UPDATE rework_jobs
                SET status='成功', finished_at=datetime('now'), message='回炉抓取成功'
                WHERE id=?
                """,
                (job_id,),
            )
            row = conn.execute(
                "SELECT * FROM quarantine_rows WHERE id=?", (job["row_id"],)
            ).fetchone()
            conn.execute(
                "UPDATE quarantine_rows SET status='已放行' WHERE id=?", (row["id"],)
            )
            conn.execute(
                """
                UPDATE capture_items SET status='已放行', quality='合格'
                WHERE id=?
                """,
                (row["item_id"],),
            )
        else:
            attempt = job["attempt"] + 1
            conn.execute(
                """
                UPDATE rework_jobs
                SET status='失败', attempt=?, finished_at=datetime('now'),
                    message='回炉抓取失败'
                WHERE id=?
                """,
                (attempt, job_id),
            )
        out = conn.execute("SELECT * FROM rework_jobs WHERE id=?", (job_id,)).fetchone()
    audit_svc.write_event(
        "执行回炉",
        "rework_job",
        job_id,
        "成功" if succeed else "失败",
        db_path=db_path,
    )
    return dict(out)


def enqueue_from_row(row_id: int, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM quarantine_rows WHERE id=?", (row_id,)
        ).fetchone()
        if not row:
            raise ServiceError("隔离行不存在", 404)
        if row["status"] not in ("待复核", "回炉中"):
            raise ServiceError("当前状态不可回炉")
        active = conn.execute(
            """
            SELECT id FROM rework_jobs
            WHERE row_id=? AND status IN ('排队','执行中')
            """,
            (row_id,),
        ).fetchone()
        if active:
            raise ServiceError("已有进行中的回炉任务")
        n = conn.execute("SELECT COUNT(*) AS c FROM rework_jobs").fetchone()["c"] + 1
        cur = conn.execute(
            """
            INSERT INTO rework_jobs(job_code, row_id, status, message)
            VALUES (?, ?, '排队', '手工入回炉队列')
            """,
            (f"RWK-{n:04d}", row_id),
        )
        conn.execute(
            "UPDATE quarantine_rows SET status='回炉中' WHERE id=?", (row_id,)
        )
        conn.execute(
            "UPDATE capture_items SET status='回炉中' WHERE id=?", (row["item_id"],)
        )
        out = conn.execute("SELECT * FROM rework_jobs WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(out)
