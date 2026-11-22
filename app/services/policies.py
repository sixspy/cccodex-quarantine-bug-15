
from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services import quarantine as quarantine_svc
from app.services.errors import ServiceError


def list_rules(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, rule_code, title, quality_match, action, target_bin_code,
                   enabled, note, created_at
            FROM policy_rules
            ORDER BY id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def create_rule(
    title: str,
    quality_match: str,
    action: str,
    target_bin_code: str = "",
    note: str = "",
    db_path: str | None = None,
) -> dict:
    title = (title or "").strip()
    quality_match = (quality_match or "").strip()
    if not title or not quality_match:
        raise ServiceError("规则标题与质量匹配不能空")
    if action not in ("入舱", "直接关闭", "观察"):
        raise ServiceError("规则动作无效")
    if quality_match not in ("缺字段", "编码空", "重复键", "合格"):
        raise ServiceError("质量匹配无效")
    with get_db(db_path) as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM policy_rules").fetchone()["c"] + 1
        code = f"POL-{n:03d}"
        cur = conn.execute(
            """
            INSERT INTO policy_rules(
              rule_code, title, quality_match, action, target_bin_code, enabled, note
            ) VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (code, title, quality_match, action, target_bin_code or "", note or ""),
        )
        rule_id = cur.lastrowid
        row = conn.execute("SELECT * FROM policy_rules WHERE id=?", (rule_id,)).fetchone()
    audit_svc.write_event("创建规则", "policy_rule", rule_id, title, db_path=db_path)
    return dict(row)


def set_enabled(rule_id: int, enabled: bool, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM policy_rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            raise ServiceError("规则不存在", 404)
        conn.execute(
            "UPDATE policy_rules SET enabled=? WHERE id=?",
            (1 if enabled else 0, rule_id),
        )
        out = conn.execute("SELECT * FROM policy_rules WHERE id=?", (rule_id,)).fetchone()
    audit_svc.write_event(
        "开关规则",
        "policy_rule",
        rule_id,
        "启用" if enabled else "停用",
        db_path=db_path,
    )
    return dict(out)


def apply_to_batch(batch_id: int, db_path: str | None = None) -> dict:
    """Apply enabled policy rules to pending bad items in a batch."""
    with get_db(db_path) as conn:
        batch = conn.execute(
            "SELECT * FROM capture_batches WHERE id=?", (batch_id,)
        ).fetchone()
        if not batch:
            raise ServiceError("批次不存在", 404)
        rules = conn.execute(
            "SELECT * FROM policy_rules WHERE enabled=1 ORDER BY id"
        ).fetchall()
        items = conn.execute(
            """
            SELECT * FROM capture_items
            WHERE batch_id=? AND status='待检' AND quality!='合格'
            """,
            (batch_id,),
        ).fetchall()
        bins = {
            r["bin_code"]: r["id"]
            for r in conn.execute("SELECT id, bin_code FROM quarantine_bins").fetchall()
        }

    entered = 0
    closed = 0
    observed = 0
    for item in items:
        matched = None
        for rule in rules:
            if rule["quality_match"] == item["quality"]:
                matched = rule
                break
        if not matched:
            continue
        if matched["action"] == "入舱":
            bin_code = matched["target_bin_code"] or "BIN-A"
            bin_id = bins.get(bin_code)
            if not bin_id:
                continue
            quarantine_svc.enter_item(
                item["id"], bin_id, f"规则{matched['rule_code']}自动入舱", db_path
            )
            entered += 1
        elif matched["action"] == "直接关闭":
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE capture_items SET status='已关闭' WHERE id=?",
                    (item["id"],),
                )
            closed += 1
        else:
            observed += 1

    audit_svc.write_event(
        "批内套规则",
        "capture_batch",
        batch_id,
        f"入舱{entered}/关闭{closed}/观察{observed}",
        db_path=db_path,
    )
    return {
        "batch_id": batch_id,
        "entered": entered,
        "closed": closed,
        "observed": observed,
        "rules_used": len(rules),
    }
