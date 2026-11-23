import sqlite3
import threading

import pytest

from app.services import captures, page_merge, quarantine, review, rework
from app.services.errors import ServiceError


def _open_batch(db_path):
    batch = next(b for b in captures.list_batches(db_path) if b["status"] != "已关闭")
    return batch


def test_commit_merge_writes_key_badge_and_landing_rows(db_path):
    batch = _open_batch(db_path)
    detail = captures.get_batch(batch["id"], db_path)
    bad = [i for i in detail["items"] if i["quality"] != "合格"]
    res = page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    assert res["merge_key"].startswith("MG-")
    assert res["badge"].startswith(res["merge_key"])
    assert res["landing_count"] == len(bad)
    merges = page_merge.list_merges(db_path)
    assert merges[0]["merge_key"] == res["merge_key"]
    rows = page_merge.merge_rows(merges[0]["id"], db_path)
    assert len(rows) == len(bad)
    listed = next(b for b in captures.list_batches(db_path) if b["id"] == batch["id"])
    assert listed["merge_key"] == res["merge_key"]
    assert listed["merge_landing_count"] == len(bad)


def test_reject_refresh_same_page(db_path):
    batch = _open_batch(db_path)
    page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    with pytest.raises(ServiceError) as exc:
        page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    assert exc.value.status_code == 409
    assert "拒绝回刷" in exc.value.message


def test_failed_commit_rolls_back_and_speaks_plain(db_path):
    with pytest.raises(ServiceError) as exc:
        page_merge.commit_merge(99999, "P1", db_path=db_path)
    assert exc.value.message == "批次不存在"
    assert page_merge.list_merges(db_path) == []


def test_fingerprint_drift_blocks_release(db_path):
    batch = _open_batch(db_path)
    bins = quarantine.list_bins(db_path)
    open_bin = next(b for b in bins if b["status"] == "开放")
    detail = captures.get_batch(batch["id"], db_path)
    bad = next(i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检")
    row = quarantine.enter_item(bad["id"], open_bin["id"], "合并前入舱", db_path)
    page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    captures.add_item(batch["id"], "sku-drift-1", "{}", "缺字段", db_path)
    ticket = next(
        t for t in review.list_tickets(db_path)
        if t["row_id"] == row["id"] and t["decision"] == "待决"
    )
    with pytest.raises(ServiceError) as exc:
        review.decide(ticket["id"], "放行", "tester", "", db_path)
    assert exc.value.status_code == 409
    assert "指纹" in exc.value.message


def test_badge_key_mismatch_blocks_rework(db_path):
    batch = _open_batch(db_path)
    bins = quarantine.list_bins(db_path)
    open_bin = next(b for b in bins if b["status"] == "开放")
    detail = captures.get_batch(batch["id"], db_path)
    bad = next(i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检")
    row = quarantine.enter_item(bad["id"], open_bin["id"], "合并前入舱", db_path)
    res = page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE page_merges SET badge='MG-9999·拧花' WHERE merge_key=?",
        (res["merge_key"],),
    )
    conn.commit()
    conn.close()
    with pytest.raises(ServiceError) as exc:
        rework.enqueue_from_row(row["id"], db_path)
    assert exc.value.status_code == 409
    assert "拧花" in exc.value.message


def test_concurrent_merge_same_page_only_one_wins(db_path):
    batch = _open_batch(db_path)
    results = []

    def worker():
        try:
            page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
            results.append("ok")
        except ServiceError as exc:
            results.append(f"err:{exc.status_code}")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1
    assert sum(1 for r in results if r.startswith("err:409")) == 1
    assert len(page_merge.list_merges(db_path)) == 1


def test_bin_card_shows_merge_landings(db_path):
    batch = _open_batch(db_path)
    bins = quarantine.list_bins(db_path)
    open_bin = next(b for b in bins if b["status"] == "开放")
    detail = captures.get_batch(batch["id"], db_path)
    bad = next(i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检")
    quarantine.enter_item(bad["id"], open_bin["id"], "合并前入舱", db_path)
    page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    bins_after = quarantine.list_bins(db_path)
    target = next(b for b in bins_after if b["id"] == open_bin["id"])
    assert target["landing_count"] >= 1


def test_merged_batch_main_chain_stays_green(db_path):
    """合并落账后主链不受误伤：驳回回炉→回炉成功→同批他件仍可放行。"""
    batch = _open_batch(db_path)
    open_bin = next(b for b in quarantine.list_bins(db_path) if b["status"] == "开放")
    detail = captures.get_batch(batch["id"], db_path)
    bad_items = [i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检"]
    if len(bad_items) < 2:
        captures.add_item(batch["id"], "sku-chain-x", "", "编码空", db_path)
        detail = captures.get_batch(batch["id"], db_path)
        bad_items = [i for i in detail["items"] if i["quality"] != "合格" and i["status"] == "待检"]
    page_merge.commit_merge(batch["id"], "P1", db_path=db_path)
    row1 = quarantine.enter_item(bad_items[0]["id"], open_bin["id"], "链一", db_path)
    ticket1 = next(
        t for t in review.list_tickets(db_path)
        if t["row_id"] == row1["id"] and t["decision"] == "待决"
    )
    review.decide(ticket1["id"], "驳回回炉", "tester", "", db_path)
    job = next(j for j in rework.list_jobs(db_path) if j["row_id"] == row1["id"])
    done = rework.run_job(job["id"], succeed=True, db_path=db_path)
    assert done["status"] == "成功"
    row2 = quarantine.enter_item(bad_items[1]["id"], open_bin["id"], "链二", db_path)
    ticket2 = next(
        t for t in review.list_tickets(db_path)
        if t["row_id"] == row2["id"] and t["decision"] == "待决"
    )
    released = review.decide(ticket2["id"], "放行", "tester", "", db_path)
    assert released["decision"] == "放行"
