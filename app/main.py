from __future__ import annotations

import json
from pathlib import Path

from itsdangerous import BadSignature, URLSafeSerializer
from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPFound, HTTPUnauthorized
from pyramid.response import FileResponse, Response

from app.config import Config
from app.seed import seed_if_needed
from app.services import audit as audit_svc
from app.services import captures as captures_svc
from app.services import policies as policies_svc
from app.services import quarantine as quarantine_svc
from app.services import reconcile as reconcile_svc
from app.services import review as review_svc
from app.services import rework as rework_svc
from app.services import settings as settings_svc
from app.services import page_merge as page_merge_svc
from app.services import page_merge_cutover as page_merge_cutover_svc
from app.services import page_merge_dualwrite as page_merge_dual_svc
from app.services import sources as sources_svc
from app.services.errors import ServiceError

STATIC = Path(__file__).resolve().parent.parent / "static"
serializer = URLSafeSerializer(Config.SECRET, salt="cc-quarantine-session")


def _json(data, status: int = 200) -> Response:
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _read_json(request) -> dict:
    try:
        data = request.json_body
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _current_user(request) -> str | None:
    raw = request.cookies.get(Config.COOKIE_NAME)
    if not raw:
        return None
    try:
        data = serializer.loads(raw)
    except BadSignature:
        return None
    if isinstance(data, dict) and data.get("user") == Config.ADMIN_USER:
        return data["user"]
    return None


def _require(request) -> str:
    user = _current_user(request)
    if not user:
        raise ServiceError("未登录", 401)
    return user


def create_app():
    seed_if_needed()
    with Configurator() as config:
        config.add_static_view(name="static", path=str(STATIC))

        def login_page(request):
            return FileResponse(str(STATIC / "login.html"))

        def spa(request):
            if not _current_user(request):
                return HTTPFound(location="/login")
            return FileResponse(str(STATIC / "index.html"))

        def root(request):
            if _current_user(request):
                return HTTPFound(location="/app")
            return HTTPFound(location="/login")

        def api_login(request):
            body = _read_json(request)
            if body.get("username") == Config.ADMIN_USER and body.get("password") == Config.ADMIN_PASS:
                token = serializer.dumps({"user": Config.ADMIN_USER})
                resp = _json({"ok": True, "user": Config.ADMIN_USER})
                resp.set_cookie(Config.COOKIE_NAME, token, max_age=86400 * 7, httponly=True)
                return resp
            return _json({"error": "用户名或密码错误"}, 401)

        def api_logout(request):
            resp = _json({"ok": True})
            resp.delete_cookie(Config.COOKIE_NAME)
            return resp

        def api_me(request):
            user = _current_user(request)
            if not user:
                return _json({"error": "未登录"}, 401)
            return _json({"user": user})

        def wrap(fn):
            def inner(request):
                try:
                    return fn(request)
                except ServiceError as exc:
                    return _json({"error": exc.message}, exc.status_code)

            return inner

        # captures
        def batches_list(request):
            _require(request)
            return _json({"items": captures_svc.list_batches()})

        def batch_get(request):
            _require(request)
            return _json(captures_svc.get_batch(int(request.matchdict["id"])))

        def batch_create(request):
            _require(request)
            body = _read_json(request)
            return _json(captures_svc.create_batch(body.get("source_name", ""), body.get("note", "")))

        def batch_add_item(request):
            _require(request)
            body = _read_json(request)
            return _json(
                captures_svc.add_item(
                    int(request.matchdict["id"]),
                    body.get("item_key", ""),
                    body.get("payload", ""),
                    body.get("quality", "合格"),
                )
            )

        def batch_close(request):
            _require(request)
            return _json(captures_svc.close_batch(int(request.matchdict["id"])))

        # quarantine
        def bins_list(request):
            _require(request)
            return _json({"items": quarantine_svc.list_bins()})

        def rows_list(request):
            _require(request)
            bin_id = request.params.get("bin_id")
            return _json(
                {
                    "items": quarantine_svc.list_rows(
                        int(bin_id) if bin_id else None
                    )
                }
            )

        def enter_row(request):
            _require(request)
            body = _read_json(request)
            return _json(
                quarantine_svc.enter_item(
                    int(body.get("item_id") or 0),
                    int(body.get("bin_id") or 0),
                    body.get("reason", ""),
                )
            )

        def auto_enter(request):
            _require(request)
            body = _read_json(request)
            return _json(
                quarantine_svc.auto_enter_bad(
                    int(body.get("batch_id") or 0),
                    int(body.get("bin_id") or 0),
                )
            )

        # review
        def tickets_list(request):
            _require(request)
            return _json({"items": review_svc.list_tickets()})

        def ticket_decide(request):
            _require(request)
            body = _read_json(request)
            return _json(
                review_svc.decide(
                    int(request.matchdict["id"]),
                    body.get("decision", ""),
                    body.get("reviewer", "admin"),
                    body.get("comment", ""),
                )
            )

        # rework
        def jobs_list(request):
            _require(request)
            return _json({"items": rework_svc.list_jobs()})

        def job_run(request):
            _require(request)
            body = _read_json(request)
            return _json(
                rework_svc.run_job(
                    int(request.matchdict["id"]),
                    bool(body.get("succeed", True)),
                )
            )

        def job_enqueue(request):
            _require(request)
            body = _read_json(request)
            return _json(rework_svc.enqueue_from_row(int(body.get("row_id") or 0)))

        # reconcile / settings
        def reports_list(request):
            _require(request)
            return _json({"items": reconcile_svc.list_reports()})

        def report_run(request):
            _require(request)
            return _json(reconcile_svc.run_reconcile())

        def dash(request):
            _require(request)
            return _json(reconcile_svc.dashboard())

        def settings_list(request):
            _require(request)
            return _json({"items": settings_svc.list_settings()})

        def settings_update(request):
            _require(request)
            body = _read_json(request)
            return _json(
                settings_svc.update_setting(body.get("key", ""), body.get("value", ""))
            )

        def sites_list(request):
            _require(request)
            return _json({"items": sources_svc.list_sites()})

        def site_get(request):
            _require(request)
            return _json(sources_svc.get_site(int(request.matchdict["id"])))

        def site_create(request):
            _require(request)
            body = _read_json(request)
            return _json(
                sources_svc.create_site(
                    body.get("site_name", ""),
                    body.get("base_url", ""),
                    int(body.get("daily_quota") or 100),
                    body.get("note", ""),
                )
            )

        def site_status(request):
            _require(request)
            body = _read_json(request)
            return _json(
                sources_svc.set_status(
                    int(request.matchdict["id"]), body.get("status", "")
                )
            )

        def site_quota(request):
            _require(request)
            body = _read_json(request)
            return _json(
                sources_svc.update_quota(
                    int(request.matchdict["id"]), int(body.get("daily_quota") or 1)
                )
            )

        def rules_list(request):
            _require(request)
            return _json({"items": policies_svc.list_rules()})

        def rule_create(request):
            _require(request)
            body = _read_json(request)
            return _json(
                policies_svc.create_rule(
                    body.get("title", ""),
                    body.get("quality_match", ""),
                    body.get("action", ""),
                    body.get("target_bin_code", ""),
                    body.get("note", ""),
                )
            )

        def rule_enable(request):
            _require(request)
            body = _read_json(request)
            return _json(
                policies_svc.set_enabled(
                    int(request.matchdict["id"]), bool(body.get("enabled", True))
                )
            )

        def rule_apply(request):
            _require(request)
            body = _read_json(request)
            return _json(policies_svc.apply_to_batch(int(body.get("batch_id") or 0)))


        def page_merge_dash(request):
            _require(request)
            return _json(page_merge_cutover_svc.board())

        def page_merge_commit(request):
            _require(request)
            body = _read_json(request)
            return _json(page_merge_svc.commit_action(body))

        def page_merge_half(request):
            _require(request)
            return _json(page_merge_svc.reconcile_display())

        def page_merge_snap(request):
            _require(request)
            return _json(page_merge_svc.snapshot())

        def page_merge_cutover(request):
            _require(request)
            body = _read_json(request)
            return _json(
                page_merge_cutover_svc.append_cutover(
                    int(body.get("ref_id") or 0),
                    str(body.get("note") or "分页合并"),
                )
            )

        def page_merge_dual(request):
            _require(request)
            body = _read_json(request)
            return _json(page_merge_dual_svc.apply_dualwrite(str(body.get("note") or "分页合并")))

        def audits_list(request):
            _require(request)
            limit = int(request.params.get("limit") or 100)
            return _json({"items": audit_svc.list_events(limit), "summary": audit_svc.summary()})

        config.add_route("root", "/")
        config.add_route("login", "/login")
        config.add_route("app", "/app")
        config.add_route("app_slash", "/app/")
        config.add_route("api_login", "/api/login")
        config.add_route("api_logout", "/api/logout")
        config.add_route("api_me", "/api/me")
        config.add_route("batches", "/api/batches")
        config.add_route("batch", "/api/batches/{id}")
        config.add_route("batch_items", "/api/batches/{id}/items")
        config.add_route("batch_close", "/api/batches/{id}/close")
        config.add_route("bins", "/api/bins")
        config.add_route("rows", "/api/rows")
        config.add_route("enter", "/api/quarantine/enter")
        config.add_route("auto_enter", "/api/quarantine/auto-enter")
        config.add_route("tickets", "/api/tickets")
        config.add_route("ticket_decide", "/api/tickets/{id}/decide")
        config.add_route("jobs", "/api/rework/jobs")
        config.add_route("job_run", "/api/rework/jobs/{id}/run")
        config.add_route("job_enqueue", "/api/rework/enqueue")
        config.add_route("reports", "/api/reports")
        config.add_route("report_run", "/api/reports/run")
        config.add_route("dash", "/api/dashboard")
        config.add_route("settings", "/api/settings")
        config.add_route("settings_update", "/api/settings/update")
        config.add_route("sites", "/api/sites")
        config.add_route("site", "/api/sites/{id}")
        config.add_route("site_status", "/api/sites/{id}/status")
        config.add_route("site_quota", "/api/sites/{id}/quota")
        config.add_route("rules", "/api/rules")
        config.add_route("rule_enable", "/api/rules/{id}/enable")
        config.add_route("rule_apply", "/api/rules/apply")
        config.add_route("audits", "/api/audits")
        config.add_route("page_merge_dash", "/api/page_merge/dash")
        config.add_route("page_merge_commit", "/api/page_merge/commit")
        config.add_route("page_merge_half", "/api/page_merge/half")
        config.add_route("page_merge_snap", "/api/page_merge/snap")
        config.add_route("page_merge_cutover", "/api/page_merge/cutover")
        config.add_route("page_merge_dual", "/api/page_merge/dual")


        config.add_view(root, route_name="root")
        config.add_view(login_page, route_name="login")
        config.add_view(spa, route_name="app")
        config.add_view(spa, route_name="app_slash")
        config.add_view(api_login, route_name="api_login", request_method="POST")
        config.add_view(api_logout, route_name="api_logout", request_method="POST")
        config.add_view(wrap(api_me), route_name="api_me")
        config.add_view(wrap(batches_list), route_name="batches", request_method="GET")
        config.add_view(wrap(batch_get), route_name="batch", request_method="GET")
        config.add_view(wrap(batch_create), route_name="batches", request_method="POST")
        config.add_view(wrap(batch_add_item), route_name="batch_items", request_method="POST")
        config.add_view(wrap(batch_close), route_name="batch_close", request_method="POST")
        config.add_view(wrap(bins_list), route_name="bins", request_method="GET")
        config.add_view(wrap(rows_list), route_name="rows", request_method="GET")
        config.add_view(wrap(enter_row), route_name="enter", request_method="POST")
        config.add_view(wrap(auto_enter), route_name="auto_enter", request_method="POST")
        config.add_view(wrap(tickets_list), route_name="tickets", request_method="GET")
        config.add_view(wrap(ticket_decide), route_name="ticket_decide", request_method="POST")
        config.add_view(wrap(jobs_list), route_name="jobs", request_method="GET")
        config.add_view(wrap(job_run), route_name="job_run", request_method="POST")
        config.add_view(wrap(job_enqueue), route_name="job_enqueue", request_method="POST")
        config.add_view(wrap(reports_list), route_name="reports", request_method="GET")
        config.add_view(wrap(report_run), route_name="report_run", request_method="POST")
        config.add_view(wrap(dash), route_name="dash", request_method="GET")
        config.add_view(wrap(settings_list), route_name="settings", request_method="GET")
        config.add_view(wrap(settings_update), route_name="settings_update", request_method="POST")
        config.add_view(wrap(sites_list), route_name="sites", request_method="GET")
        config.add_view(wrap(site_create), route_name="sites", request_method="POST")
        config.add_view(wrap(site_get), route_name="site", request_method="GET")
        config.add_view(wrap(site_status), route_name="site_status", request_method="POST")
        config.add_view(wrap(site_quota), route_name="site_quota", request_method="POST")
        config.add_view(wrap(rules_list), route_name="rules", request_method="GET")
        config.add_view(wrap(rule_create), route_name="rules", request_method="POST")
        config.add_view(wrap(rule_enable), route_name="rule_enable", request_method="POST")
        config.add_view(wrap(rule_apply), route_name="rule_apply", request_method="POST")
        config.add_view(wrap(audits_list), route_name="audits", request_method="GET")
        config.add_view(wrap(page_merge_dash), route_name="page_merge_dash", request_method="GET")
        config.add_view(wrap(page_merge_commit), route_name="page_merge_commit", request_method="POST")
        config.add_view(wrap(page_merge_half), route_name="page_merge_half", request_method="POST")
        config.add_view(wrap(page_merge_snap), route_name="page_merge_snap", request_method="GET")
        config.add_view(wrap(page_merge_cutover), route_name="page_merge_cutover", request_method="POST")
        config.add_view(wrap(page_merge_dual), route_name="page_merge_dual", request_method="POST")


        return config.make_wsgi_app()
