"""
SynCore JSON REST APIs — Bridger-compatible routes, secured by SYNCORE_SERVICE_KEY.

Base URL: /api/syncore/open
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from app.extensions import db
from app.middleware.service_key import require_service_key
from app.models.employee import SynCoreEmployee
from app.routes import helpers as h
from app.routes.sse import format_sse
from app.services.syncore import get_syn_core_client
from app.services.syncore.sync import iter_sync_employees_to_db
from app.services.webex import get_employee_image

logger = logging.getLogger(__name__)

syncore_open_bp = Blueprint(
    "syncore_open",
    __name__,
    url_prefix="/api/syncore/open",
)


@syncore_open_bp.before_request
def _auth():
    return require_service_key()


def _get_employee(employee_id: int) -> SynCoreEmployee:
    employee = db.session.get(SynCoreEmployee, employee_id)
    if not employee:
        from flask import abort

        abort(404)
    return employee


@syncore_open_bp.route("/")
def index():
    registered = sorted(
        r.rule
        for r in current_app.url_map.iter_rules()
        if r.rule.startswith("/api/syncore/open")
    )
    return jsonify(
        {
            "success": True,
            "service": "SynCore Proxy APIs",
            "authentication": "X-Service-Key or Authorization: Bearer <SYNCORE_SERVICE_KEY>",
            "base_url": "/api/syncore/open",
            "registered_route_count": len(registered),
            "registered_routes": registered,
        }
    )


@syncore_open_bp.route("/stats")
def stats():
    last_synced = db.session.query(db.func.max(SynCoreEmployee.last_synced_at)).scalar()
    return jsonify(
        {
            "success": True,
            "total_employees": SynCoreEmployee.query.count(),
            "active_employees": SynCoreEmployee.query.filter_by(status="Active").count(),
            "last_synced_at": last_synced.isoformat() if last_synced else None,
        }
    )


@syncore_open_bp.route("/employees")
def list_employees():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)

    query = SynCoreEmployee.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                SynCoreEmployee.name.ilike(like),
                SynCoreEmployee.email.ilike(like),
                SynCoreEmployee.employee_id.ilike(like),
                SynCoreEmployee.designation.ilike(like),
            )
        )
    if status_filter == "active":
        query = query.filter_by(status="Active")
    elif status_filter == "inactive":
        query = query.filter(
            db.or_(
                SynCoreEmployee.status == "In-Active",
                SynCoreEmployee.status == "Inactive",
            )
        )

    employees = query.order_by(SynCoreEmployee.name.asc()).all()
    pagination = h.paginate_list([h.employee_to_dict(e) for e in employees], page, per_page)
    return jsonify(
        {
            "success": True,
            "pagination": pagination,
            "total_employees": SynCoreEmployee.query.count(),
            "active_employees": SynCoreEmployee.query.filter_by(status="Active").count(),
        }
    )


@syncore_open_bp.route("/employees/by-email")
def employee_by_email():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return h.api_error("email query parameter is required", 400)
    employee = SynCoreEmployee.query.filter(
        db.func.lower(SynCoreEmployee.email) == email
    ).first()
    if not employee:
        return h.api_error(f"No employee found with email {email!r}", 404)
    return jsonify({"success": True, "employee": h.employee_to_dict(employee)})


@syncore_open_bp.route("/employees/<int:employee_id>")
def employee_detail(employee_id: int):
    employee = _get_employee(employee_id)
    return jsonify({"success": True, "employee": h.employee_to_dict(employee)})


@syncore_open_bp.route("/sync", methods=["POST"])
def sync_employees():
    """
    Stream employee sync progress as Server-Sent Events (HTTP 200).

    Events:
        log      — {level, message}
        progress — {current, total, employee_id, name, action}
        done     — {success, stats, message} (terminal)
        error    — {success, error} (fatal, before done)
    """

    @stream_with_context
    def generate():
        yield format_sse("log", {"level": "info", "message": "SSE connection ready"})
        try:
            client = get_syn_core_client()
            for event_name, payload in iter_sync_employees_to_db(client):
                yield format_sse(event_name, payload)
        except Exception as exc:
            logger.error("Sync error: %s", exc, exc_info=True)
            yield format_sse("error", {"success": False, "error": str(exc)})
            yield format_sse(
                "done",
                {"success": False, "message": f"Sync failed: {exc}", "stats": None},
            )

    return Response(
        generate(),
        status=200,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@syncore_open_bp.route("/employees/<int:employee_id>/logs")
def employee_today_logs(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    try:
        logs = client.get_today_log_status(employee.user_id, employee.signed_array)
        return jsonify(
            {
                "success": True,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "is_logged_in": h.is_logged_in_from_logs(logs),
                "logs": logs,
            }
        )
    except Exception as exc:
        logger.error("Today logs error emp %s: %s", employee_id, exc, exc_info=True)
        return h.api_error(f"Failed to fetch logs: {exc}", 500)


def _attendance_summary(all_records: list) -> dict:
    late_count = sum(
        1 for r in all_records if r.get("is_came_late", "-") not in ("-", None, "")
    )
    total_logged = 0.0
    for r in all_records:
        lh = r.get("logged_hours", "") or ""
        parts = lh.split(":")
        try:
            total_logged += int(parts[0]) + int(parts[1]) / 60 if len(parts) == 2 else 0
        except (ValueError, IndexError):
            pass
    total_hours_int = int(total_logged)
    total_minutes_int = round((total_logged - total_hours_int) * 60)
    return {
        "total_days": len(all_records),
        "late_count": late_count,
        "total_hours": total_hours_int,
        "total_minutes": total_minutes_int,
    }


@syncore_open_bp.route("/employees/<int:employee_id>/attendance")
def employee_attendance(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    default_start, default_end = h.build_date_defaults()
    start_date = request.args.get("start_date", default_start).strip()
    end_date = request.args.get("end_date", default_end).strip()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    try:
        records = client.get_attendance(
            start_date, end_date, employee.user_id, employee.signed_array
        )
        return jsonify(
            {
                "success": True,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "start_date": start_date,
                "end_date": end_date,
                "summary": _attendance_summary(records),
                "pagination": h.paginate_list(records, page, per_page),
            }
        )
    except Exception as exc:
        logger.error("Attendance error emp %s: %s", employee_id, exc, exc_info=True)
        return h.api_error(f"Failed to fetch attendance: {exc}", 500)


@syncore_open_bp.route("/employees/<int:employee_id>/attendance/current-month")
def employee_attendance_current_month(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    start_date, end_date = h.get_ist_current_month_bounds()
    try:
        records = client.get_attendance(
            start_date, end_date, employee.user_id, employee.signed_array
        )
        try:
            records.sort(
                key=lambda r: datetime.strptime(r.get("log_date", "01/01/1970"), "%m/%d/%Y"),
                reverse=True,
            )
        except (ValueError, TypeError):
            pass
        return jsonify(
            {
                "success": True,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "start_date": start_date,
                "end_date": end_date,
                "summary": _attendance_summary(records),
                "records": records,
            }
        )
    except Exception as exc:
        return h.api_error(f"Failed to fetch attendance for current month: {exc}", 500)


@syncore_open_bp.route("/employees/<int:employee_id>/leaves")
def employee_leaves(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    try:
        leaves = client.get_employee_leaves(
            employee.user_id, employee.signed_array, start_date, end_date
        )
        return jsonify(
            {
                "success": True,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "start_date": start_date,
                "end_date": end_date,
                "total_leaves": len(leaves),
                "pagination": h.paginate_list(leaves, page, per_page),
            }
        )
    except Exception as exc:
        return h.api_error(f"Failed to fetch leave records: {exc}", 500)


@syncore_open_bp.route("/employees/<int:employee_id>/leaves/current-month")
def employee_leaves_current_month(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    start_date, end_date = h.get_ist_current_month_bounds()
    leaves = client.get_employee_leaves(
        employee.user_id, employee.signed_array, start_date, end_date
    )
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "start_date": start_date,
            "end_date": end_date,
            "total_leaves": len(leaves),
            "leaves": leaves,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/holiday-calendar")
def employee_holiday_calendar(employee_id: int):
    employee = _get_employee(employee_id)
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    if not start_date or not end_date:
        return h.api_error("start_date and end_date query parameters are required", 400)
    client = get_syn_core_client()
    try:
        calendar = client.get_holiday_and_leave_calendar(
            employee.user_id, employee.signed_array, start_date, end_date
        )
        if calendar.get("error"):
            return h.api_error(calendar["error"], 502)
        return jsonify(
            {
                "success": True,
                "employee_id": employee.id,
                "employee_name": employee.name,
                "start_date": start_date,
                "end_date": end_date,
                "holidays": calendar["holidays"],
                "leaves": calendar["leaves"],
            }
        )
    except ValueError as exc:
        return h.api_error(str(exc), 400)


@syncore_open_bp.route("/employees/<int:employee_id>/holiday-calendar/current-month")
def employee_holiday_calendar_current_month(employee_id: int):
    employee = _get_employee(employee_id)
    start_date, end_date = h.get_ist_current_month_bounds()
    client = get_syn_core_client()
    calendar = client.get_holiday_and_leave_calendar(
        employee.user_id, employee.signed_array, start_date, end_date
    )
    if calendar.get("error"):
        return h.api_error(calendar["error"], 502)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "start_date": start_date,
            "end_date": end_date,
            "holidays": calendar.get("holidays", []),
            "leaves": calendar.get("leaves", []),
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/today-leaves-holidays")
def employee_today_leaves_holidays(employee_id: int):
    employee = _get_employee(employee_id)
    _, today_str = h.get_ist_today()
    client = get_syn_core_client()
    calendar = client.get_holiday_and_leave_calendar(
        employee.user_id, employee.signed_array, today_str, today_str
    )
    if calendar.get("error"):
        return h.api_error(calendar["error"], 502)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "date": today_str,
            "holidays": calendar.get("holidays", []),
            "leaves": calendar.get("leaves", []),
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/today-working-status")
def employee_today_working_status(employee_id: int):
    employee = _get_employee(employee_id)
    today, today_str = h.get_ist_today()
    client = get_syn_core_client()
    all_leaves = client.get_employee_leaves(employee.user_id, employee.signed_array)
    today_leaves = h.filter_leaves_for_date(all_leaves, today)
    calendar = client.get_holiday_and_leave_calendar(
        employee.user_id, employee.signed_array, today_str, today_str
    )
    if calendar.get("error"):
        return h.api_error(calendar["error"], 502)
    today_holidays = calendar.get("holidays", [])
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "date": today_str,
            "working_status": h.resolve_working_status(today_holidays, today_leaves),
            "holidays": today_holidays,
            "leaves": today_leaves,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/webex-token")
def employee_webex_token(employee_id: int):
    employee = _get_employee(employee_id)
    result = get_syn_core_client().get_webex_token(employee.user_id, employee.signed_array)
    if "error" in result:
        return h.api_error(result["error"], 400)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "token": result["token"],
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/image")
def employee_image(employee_id: int):
    employee = _get_employee(employee_id)
    access_token = request.args.get("access_token", "").strip()
    if not access_token:
        token_result = get_syn_core_client().get_webex_token(
            employee.user_id, employee.signed_array
        )
        if "error" in token_result:
            return h.api_error(token_result["error"], 400)
        access_token = h.resolve_webex_access_token(token_result)
        if not access_token:
            return h.api_error("Could not resolve Webex access token from HRMS response", 400)
    image_result = get_employee_image(access_token)
    if "error" in image_result:
        return h.api_error(image_result["error"], 502)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "image_url": image_result["image_url"],
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/projects")
def employee_projects(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    all_projects = client.get_emp_projects(employee.user_id, employee.signed_array)
    status_filter = request.args.get("status", "all")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    filtered = all_projects
    if status_filter == "active":
        filtered = [p for p in filtered if p.get("project_status") == "Active"]
    elif status_filter == "inactive":
        filtered = [p for p in filtered if p.get("project_status") != "Active"]
    if q:
        filtered = [p for p in filtered if q.lower() in (p.get("project_name") or "").lower()]
    active_count = sum(1 for p in all_projects if p.get("project_status") == "Active")
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "active_count": active_count,
            "inactive_count": len(all_projects) - active_count,
            "total_count": len(all_projects),
            "pagination": h.paginate_list(filtered, page, per_page),
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/projects/<project_id>")
def employee_project_detail(employee_id: int, project_id: str):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    modules = client.get_project_modules(employee.user_id, employee.signed_array, project_id)
    activities = client.get_project_activities(
        employee.user_id, employee.signed_array, project_id
    )
    project_name = (
        (modules[0].get("project_name") if modules else None)
        or (activities[0].get("project_name") if activities else None)
        or f"Project #{project_id}"
    )
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "project_id": project_id,
            "project_name": project_name,
            "modules": modules,
            "activities": activities,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/project-logs")
def employee_project_logs(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    default_start, default_end = h.build_date_defaults()
    start_date = request.args.get("start_date", default_start).strip()
    end_date = request.args.get("end_date", default_end).strip()
    project_id = request.args.get("project_id", "").strip()
    module_id = request.args.get("module_id", "").strip()
    activity_id = request.args.get("activity_id", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    all_projects = client.get_emp_projects(employee.user_id, employee.signed_array)
    project_modules = []
    project_activities = []
    if project_id:
        project_modules = client.get_project_modules(
            employee.user_id, employee.signed_array, project_id
        )
        project_activities = client.get_project_activities(
            employee.user_id, employee.signed_array, project_id
        )
    logs = client.get_emp_project_log(
        start_date,
        end_date,
        employee.user_id,
        employee.signed_array,
        int(project_id) if project_id else 0,
        int(module_id) if module_id else 0,
        int(activity_id) if activity_id else 0,
    )
    total_hours = sum(float(r.get("hour_clocked", 0) or 0) for r in logs)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "project_id": project_id or None,
                "module_id": module_id or None,
                "activity_id": activity_id or None,
            },
            "all_projects": all_projects,
            "project_modules": project_modules,
            "project_activities": project_activities,
            "total_hours": total_hours,
            "total_logs": len(logs),
            "pagination": h.paginate_list(logs, page, per_page),
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/project-logs/current-month")
def employee_project_logs_current_month(employee_id: int):
    employee = _get_employee(employee_id)
    client = get_syn_core_client()
    start_date, end_date = h.get_ist_current_month_bounds()
    logs = client.get_emp_project_log(
        start_date,
        end_date,
        employee.user_id,
        employee.signed_array,
    )
    total_hours = sum(float(r.get("hour_clocked", 0) or 0) for r in logs)
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "filters": {"start_date": start_date, "end_date": end_date},
            "total_hours": total_hours,
            "total_logs": len(logs),
            "logs": logs,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/email-settings")
def employee_email_settings(employee_id: int):
    employee = _get_employee(employee_id)
    settings = get_syn_core_client().get_user_mail_setting(
        employee.user_id, employee.signed_array
    )
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "settings": settings,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/login", methods=["POST"])
def employee_login(employee_id: int):
    employee = _get_employee(employee_id)
    data = h.request_json_or_form()
    result = get_syn_core_client().login(
        employee.user_id, employee.signed_array, data.get("override_comment", "")
    )
    if "error" in result:
        return h.api_error(result.get("error", "Failed to mark login"), 400)
    return jsonify(
        {
            "success": True,
            "message": result.get("message", "Login marked successfully"),
            "employee_id": employee.id,
            "employee_name": employee.name,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/logout", methods=["POST"])
def employee_logout(employee_id: int):
    employee = _get_employee(employee_id)
    data = h.request_json_or_form()
    result = get_syn_core_client().logout(
        employee.user_id, employee.signed_array, data.get("override_comment", "")
    )
    if "error" in result:
        return h.api_error(result.get("error", "Failed to mark logout"), 400)
    return jsonify(
        {
            "success": True,
            "message": result.get("message", "Logout marked successfully"),
            "employee_id": employee.id,
            "employee_name": employee.name,
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/worklog/projects")
def worklog_projects(employee_id: int):
    employee = _get_employee(employee_id)
    projects = get_syn_core_client().get_emp_projects(employee.user_id, employee.signed_array)
    return jsonify({"success": True, "employee_id": employee.id, "projects": projects})


@syncore_open_bp.route("/employees/<int:employee_id>/worklog/project-details")
def worklog_project_details(employee_id: int):
    employee = _get_employee(employee_id)
    project_id = request.args.get("project_id", "").strip()
    if not project_id:
        return h.api_error("project_id is required", 400)
    client = get_syn_core_client()
    return jsonify(
        {
            "success": True,
            "employee_id": employee.id,
            "project_id": project_id,
            "modules": client.get_project_modules(
                employee.user_id, employee.signed_array, project_id
            ),
            "activities": client.get_project_activities(
                employee.user_id, employee.signed_array, project_id
            ),
        }
    )


@syncore_open_bp.route("/employees/<int:employee_id>/worklog/fill", methods=["POST"])
def worklog_fill(employee_id: int):
    employee = _get_employee(employee_id)
    data = h.request_json_or_form()
    project_id = str(data.get("project_id", "")).strip()
    module_id = str(data.get("module_id", "")).strip()
    activity_id = str(data.get("activity_id", "")).strip()
    raw_work_desc = str(data.get("work_desc", "")).strip()
    hour_clocked = str(data.get("hour_clocked", "")).strip()
    if not all([project_id, module_id, activity_id, raw_work_desc, hour_clocked]):
        return h.api_error(
            "project_id, module_id, activity_id, work_desc, and hour_clocked are required",
            400,
        )
    work_desc = h.strip_keyword_prefix(raw_work_desc, data.get("keyword"))
    if not work_desc:
        return h.api_error("work_desc is empty after removing keyword prefix", 400)
    result = get_syn_core_client().fill_work_log(
        project_id,
        module_id,
        activity_id,
        work_desc,
        hour_clocked,
        employee.user_id,
        employee.signed_array,
    )
    if "error" in result:
        return h.api_error(result["error"], 400)
    return jsonify(
        {
            "success": True,
            "message": result.get("message", "Work log submitted successfully."),
            "employee_id": employee.id,
            "employee_name": employee.name,
            "token": result.get("token"),
        }
    )