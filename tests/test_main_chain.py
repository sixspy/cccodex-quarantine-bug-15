from app.services import captures, quarantine, reconcile, review, rework


def test_enter_review_rework_reconcile(db_path):
    batches = captures.list_batches(db_path)
    batch = next(b for b in batches if b["status"] != "已关闭")
    bins = quarantine.list_bins(db_path)
    open_bin = next(b for b in bins if b["status"] == "开放")
    detail = captures.get_batch(batch["id"], db_path)
    bad = next(i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检")
    row = quarantine.enter_item(bad["id"], open_bin["id"], "测试入舱", db_path)
    assert row["status"] == "待复核"
    tickets = review.list_tickets(db_path)
    ticket = next(t for t in tickets if t["row_id"] == row["id"] and t["decision"] == "待决")
    decided = review.decide(ticket["id"], "驳回回炉", "tester", "回炉", db_path)
    assert decided["decision"] == "驳回回炉"
    jobs = rework.list_jobs(db_path)
    job = next(j for j in jobs if j["row_id"] == row["id"])
    done = rework.run_job(job["id"], succeed=True, db_path=db_path)
    assert done["status"] == "成功"
    report = reconcile.run_reconcile(db_path)
    assert "待复核" in report["summary"]
