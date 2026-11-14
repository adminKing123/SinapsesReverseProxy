from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import request

from app.models.employee import SynCoreEmployee


def employee_to_dict(employee: SynCoreEmployee) -> dict:
    return {
        "id": employee.id,
        "user_id": employee.user_id,
        "employee_id": employee.employee_id,
        "name": employee.name,
        "email": employee.email,
        "gender": employee.gender,
        "firm_id": employee.firm_id,
        "firm_name": employee.firm_name,
        "org_team_id": employee.org_team_id,
        "org_name": employee.org_name,
        "is_org_manager": employee.is_org_manager,
        "designation": employee.designation,
        "user_type": employee.user_type,
        "status": employee.status,
        "team_lead_id": employee.team_lead_id,
        "team_lead_name": employee.team_lead_name,
        "reporting_time": employee.reporting_time,
        "working_hours": employee.working_hours,
        "monthly_worklog_hours": employee.monthly_worklog_hours,
        "joining_date": employee.joining_date.isoformat() if employee.joining_date else None,
        "leaving_date": employee.leaving_date.isoformat() if employee.leaving_date else None,
        "training_completion_date": (
            employee.training_completion_date.isoformat()
            if employee.training_completion_date
            else None
        ),
        "comp_off": employee.comp_off,
        "emergency_leave": employee.emergency_leave,
        "casual_leave": employee.casual_leave,
        "extended_leave": employee.extended_leave,
        "syn_coin": employee.syn_coin,
        "overrides": employee.overrides,
        "last_synced_at": (
            employee.last_synced_at.isoformat() if employee.last_synced_at else None
        ),
    }


def build_date_defaults() -> tuple[str, str]:
    today = datetime.now()
    start = today.replace(day=1).strftime("%m/%d/%Y")
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start, last.strftime("%m/%d/%Y")


def get_ist_current_month_bounds() -> tuple[str, str]:
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    start_date = ist_now.replace(day=1)
    if ist_now.month == 12:
        last_date = ist_now.replace(year=ist_now.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_date = ist_now.replace(month=ist_now.month + 1, day=1) - timedelta(days=1)
    return start_date.strftime("%m/%d/%Y"), last_date.strftime("%m/%d/%Y")


def paginate_list(items: list, page: int, per_page: int) -> dict:
    total = len(items)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    records = items[(page - 1) * per_page : page * per_page]
    return {
        "items": records,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_num": page - 1 if page > 1 else None,
        "next_num": page + 1 if page < total_pages else None,
    }


def request_json_or_form() -> dict:
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    return request.form.to_dict()


def resolve_webex_access_token(token_result: dict):
    if "error" in token_result:
        return None
    token = token_result.get("token")
    if isinstance(token, str):
        return token
    if isinstance(token, dict):
        for key in ("access_token", "token", "spark_token"):
            if token.get(key):
                return str(token[key])
    return str(token) if token else None


def api_error(message: str, status: int = 400):
    from flask import jsonify

    return jsonify({"success": False, "error": message}), status


def is_logged_in_from_logs(logs: list) -> bool:
    if not logs:
        return False
    return logs[-1].get("logout") == "00:00"


def get_ist_today() -> tuple[date, str]:
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today = ist_now.date()
    return today, today.strftime("%m/%d/%Y")


def parse_date_mmddyyyy(date_str: str | None) -> date | None:
    if not date_str or date_str == "None":
        return None
    try:
        return datetime.strptime(str(date_str), "%m/%d/%Y").date()
    except (ValueError, TypeError):
        return None


def leave_covers_date(leave: dict, today: date) -> bool:
    if leave.get("leave_status") != "Approved":
        return False
    start = parse_date_mmddyyyy(leave.get("start_date"))
    end = parse_date_mmddyyyy(leave.get("end_date"))
    if not start or not end:
        return False
    return start <= today <= end


def filter_leaves_for_date(leaves: list, today: date) -> list:
    return [leave for leave in leaves if leave_covers_date(leave, today)]


def resolve_working_status(holidays: list, leaves: list) -> str:
    if holidays:
        return "HOLIDAY"
    if leaves:
        return "LEAVE"
    return "WORKING"


def strip_keyword_prefix(text: str, keyword: str | None) -> str:
    value = text.strip()
    if not keyword:
        return value
    prefix = str(keyword)
    if value.startswith(prefix):
        value = value[len(prefix) :]
    return value.lstrip()