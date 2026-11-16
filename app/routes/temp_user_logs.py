"""
Temp user text logs — Bridger /api/open parity, scoped by SynCore HRMS user_id.

Base URL: /api/syncore/temp
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, current_app, jsonify, request

from app.extensions import db
from app.middleware.scope import require_synapse_user_id
from app.middleware.service_key import require_service_key
from app.models.employee import SynCoreEmployee
from app.models.temp_user_log import TempUserLog
from app.routes import helpers as h

logger = logging.getLogger(__name__)

temp_logs_bp = Blueprint(
    "temp_user_logs",
    __name__,
    url_prefix="/api/syncore/temp",
)


@temp_logs_bp.before_request
def _auth():
    return require_service_key()


def _parse_log_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _get_ist_today() -> date:
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_now.date()


def _get_ist_current_month_bounds() -> tuple[date, date]:
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    start_date = ist_now.replace(day=1).date()
    if ist_now.month == 12:
        last_date = ist_now.replace(year=ist_now.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_date = ist_now.replace(month=ist_now.month + 1, day=1) - timedelta(days=1)
    return start_date, last_date.date()


def _require_synapse_user(user_id: str):
    uid = str(user_id).strip()
    if not uid:
        return None, h.api_error("user_id is required", 400)
    scope_err = require_synapse_user_id(uid)
    if scope_err:
        return None, scope_err
    employee = SynCoreEmployee.query.filter_by(user_id=uid).first()
    if not employee:
        return None, h.api_error(f"No SynCore employee found with user_id {uid!r}", 404)
    return uid, None


def _query_logs_range(synapse_user_id: str, start_date: date, end_date: date) -> list:
    return (
        TempUserLog.query.filter(
            TempUserLog.synapse_user_id == synapse_user_id,
            TempUserLog.log_date >= start_date,
            TempUserLog.log_date <= end_date,
        )
        .order_by(TempUserLog.log_date.desc(), TempUserLog.created_at.desc())
        .all()
    )


def _query_logs_chronological(synapse_user_id: str, log_date: date) -> list:
    return (
        TempUserLog.query.filter_by(synapse_user_id=synapse_user_id, log_date=log_date)
        .order_by(TempUserLog.created_at.asc())
        .all()
    )


def _format_today_logs_text(log_date: date, logs: list) -> str:
    date_label = log_date.strftime("%d-%B-%Y")
    lines = [f"Worked On {date_label}", ""]
    lines.extend(f"- {log.log_text}" for log in logs)
    return "\n".join(lines)


def _paginate_query(query, page: int, per_page: int) -> dict:
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages or 1,
        "has_prev": pagination.has_prev,
        "has_next": pagination.has_next,
        "prev_num": pagination.prev_num,
        "next_num": pagination.next_num,
    }


@temp_logs_bp.route("/")
def index():
    registered = sorted(
        r.rule
        for r in current_app.url_map.iter_rules()
        if r.rule.startswith("/api/syncore/temp")
    )
    return jsonify(
        {
            "success": True,
            "service": "SynCore Temp User Logs API",
            "authentication": "X-Service-Key header",
            "user_scope": "SynCore HRMS user_id in URL (syncore_employees.user_id)",
            "base_url": "/api/syncore/temp",
            "registered_route_count": len(registered),
            "registered_routes": registered,
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs", methods=["GET"])
def list_user_logs(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 50, type=int), 1), 200)

    query = TempUserLog.query.filter_by(synapse_user_id=synapse_user_id)

    exact_date = _parse_log_date(request.args.get("date"))
    start_date = _parse_log_date(request.args.get("start_date"))
    end_date = _parse_log_date(request.args.get("end_date"))

    if request.args.get("date") and exact_date is None:
        return h.api_error("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY.", 400)
    if request.args.get("start_date") and start_date is None:
        return h.api_error("Invalid start_date format. Use YYYY-MM-DD or MM/DD/YYYY.", 400)
    if request.args.get("end_date") and end_date is None:
        return h.api_error("Invalid end_date format. Use YYYY-MM-DD or MM/DD/YYYY.", 400)

    if exact_date:
        query = query.filter(TempUserLog.log_date == exact_date)
    else:
        if start_date:
            query = query.filter(TempUserLog.log_date >= start_date)
        if end_date:
            query = query.filter(TempUserLog.log_date <= end_date)

    query = query.order_by(TempUserLog.log_date.desc(), TempUserLog.created_at.desc())

    return jsonify(
        {
            "success": True,
            "user_id": synapse_user_id,
            "pagination": _paginate_query(query, page, per_page),
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs/today", methods=["GET"])
def list_user_logs_today(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    today = _get_ist_today()
    logs = _query_logs_range(synapse_user_id, today, today)

    return jsonify(
        {
            "success": True,
            "user_id": synapse_user_id,
            "date": today.isoformat(),
            "total_logs": len(logs),
            "logs": [log.to_dict() for log in logs],
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs/today/text", methods=["GET"])
def user_logs_today_text(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    today = _get_ist_today()
    logs = _query_logs_chronological(synapse_user_id, today)
    return Response(_format_today_logs_text(today, logs), mimetype="text/plain; charset=utf-8")


@temp_logs_bp.route("/users/<user_id>/logs/current-month", methods=["GET"])
def list_user_logs_current_month(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    start_date, end_date = _get_ist_current_month_bounds()
    logs = _query_logs_range(synapse_user_id, start_date, end_date)

    return jsonify(
        {
            "success": True,
            "user_id": synapse_user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_logs": len(logs),
            "logs": [log.to_dict() for log in logs],
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs/purge", methods=["DELETE"])
def purge_user_logs(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    deleted_count = TempUserLog.query.filter_by(synapse_user_id=synapse_user_id).delete()
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "All logs purged successfully",
            "user_id": synapse_user_id,
            "deleted_count": deleted_count,
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs/<int:log_id>", methods=["GET"])
def get_user_log(user_id: str, log_id: int):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    log = TempUserLog.query.filter_by(id=log_id, synapse_user_id=synapse_user_id).first()
    if not log:
        return h.api_error(f"No log found with id {log_id} for user_id {synapse_user_id!r}", 404)

    return jsonify({"success": True, "log": log.to_dict()})


@temp_logs_bp.route("/users/<user_id>/logs", methods=["POST"])
def create_user_log(user_id: str):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    data = h.request_json_or_form()
    raw_log = str(data.get("log", "")).strip()
    if not raw_log:
        return h.api_error("log is required", 400)

    log_text = h.strip_keyword_prefix(raw_log, data.get("keyword"))
    if not log_text:
        return h.api_error("log is empty after removing keyword prefix", 400)

    if data.get("date"):
        log_date = _parse_log_date(data.get("date"))
        if log_date is None:
            return h.api_error("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY.", 400)
    else:
        log_date = _get_ist_today()

    log = TempUserLog(
        synapse_user_id=synapse_user_id,
        log_text=log_text,
        log_date=log_date,
    )
    db.session.add(log)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": "Log created successfully",
                "log": log.to_dict(),
            }
        ),
        201,
    )


@temp_logs_bp.route("/users/<user_id>/logs/<int:log_id>", methods=["PUT", "PATCH"])
def update_user_log(user_id: str, log_id: int):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    log = TempUserLog.query.filter_by(id=log_id, synapse_user_id=synapse_user_id).first()
    if not log:
        return h.api_error(f"No log found with id {log_id} for user_id {synapse_user_id!r}", 404)

    data = h.request_json_or_form()

    if "log" in data:
        log_text = str(data.get("log", "")).strip()
        if not log_text:
            return h.api_error("log cannot be empty", 400)
        log.log_text = log_text

    if "date" in data:
        parsed = _parse_log_date(data.get("date"))
        if not parsed:
            return h.api_error("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY.", 400)
        log.log_date = parsed

    if request.method == "PUT" and "log" not in data:
        return h.api_error("log is required for PUT", 400)

    if not any(key in data for key in ("log", "date")):
        return h.api_error("Provide at least one of: log, date", 400)

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "Log updated successfully",
            "log": log.to_dict(),
        }
    )


@temp_logs_bp.route("/users/<user_id>/logs/<int:log_id>", methods=["DELETE"])
def delete_user_log(user_id: str, log_id: int):
    synapse_user_id, err = _require_synapse_user(user_id)
    if err:
        return err

    log = TempUserLog.query.filter_by(id=log_id, synapse_user_id=synapse_user_id).first()
    if not log:
        return h.api_error(f"No log found with id {log_id} for user_id {synapse_user_id!r}", 404)

    db.session.delete(log)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": "Log deleted successfully",
            "log_id": log_id,
        }
    )