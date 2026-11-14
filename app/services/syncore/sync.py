"""Employee sync from HRMS into SQLite (function-based service layer)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Tuple

from app.extensions import db
from app.models.employee import SynCoreEmployee
from app.services.syncore.client import SynCoreClient

logger = logging.getLogger(__name__)

SyncEvent = Tuple[str, dict]


def _emit_log(message: str, level: str = "info") -> SyncEvent:
    logger.log(logging.INFO if level == "info" else logging.WARNING, message)
    return ("log", {"level": level, "message": message})


def iter_sync_employees_to_db(client: SynCoreClient) -> Iterator[SyncEvent]:
    """Yield SSE-friendly (event_name, data) tuples while syncing employees."""
    yield _emit_log("Starting employee sync")
    yield _emit_log("Fetching employees from SynCore HRMS…")

    employees = client.get_all_employees()
    stats = {
        "total": len(employees),
        "added": 0,
        "updated": 0,
        "errors": 0,
        "error_details": [],
    }

    if not employees:
        stats["error_details"].append("No employees returned from API")
        yield ("log", {"level": "warning", "message": "No employees returned from API"})
        yield (
            "done",
            {
                "success": False,
                "stats": stats,
                "message": "Sync finished with no employees from HRMS.",
            },
        )
        return

    yield _emit_log(f"Received {len(employees)} employee record(s) from HRMS")

    date_fmt = client.config["DATE_FMT"]

    def parse_date(date_str):
        if not date_str or date_str == "None":
            return None
        try:
            return datetime.strptime(str(date_str), date_fmt).date()
        except (ValueError, TypeError):
            return None

    now = datetime.now(timezone.utc)

    for index, emp_data in enumerate(employees, start=1):
        emp_id = emp_data.get("employee_id")
        name = emp_data.get("name") or "—"
        try:
            existing = SynCoreEmployee.query.filter_by(employee_id=emp_id).first()
            employee_dict = {
                "user_id": emp_data.get("user_id"),
                "employee_id": emp_id,
                "name": emp_data.get("name"),
                "firm_id": emp_data.get("firm_id"),
                "email": emp_data.get("username"),
                "gender": emp_data.get("gender"),
                "reporting_time": emp_data.get("reporting_time"),
                "org_team_id": emp_data.get("org_team_id"),
                "syn_coin": emp_data.get("syn_coin"),
                "team_lead_id": emp_data.get("team_lead_id"),
                "designation": emp_data.get("designation"),
                "user_type": emp_data.get("user_type"),
                "working_hours": emp_data.get("workinghour"),
                "monthly_worklog_hours": emp_data.get("monthly_worklog_hr"),
                "overrides": emp_data.get("overrides"),
                "modified_by": emp_data.get("modifiedby"),
                "created_by": emp_data.get("createdby"),
                "team_lead_name": emp_data.get("team_lead"),
                "status": emp_data.get("status"),
                "joining_date": parse_date(emp_data.get("joining_date")),
                "leaving_date": parse_date(emp_data.get("leaving_date")),
                "training_completion_date": parse_date(
                    emp_data.get("training_completion_date")
                ),
                "comp_off": emp_data.get("comp_off"),
                "emergency_leave": emp_data.get("emergency_leave"),
                "casual_leave": emp_data.get("casual_leave"),
                "extended_leave": emp_data.get("extended_leave"),
                "firm_name": emp_data.get("firm_name"),
                "org_name": emp_data.get("org_name"),
                "is_org_manager": bool(emp_data.get("is_org_manager", False)),
                "signed_array": emp_data.get("signed_array"),
                "last_synced_at": now,
            }
            if existing:
                for key, value in employee_dict.items():
                    setattr(existing, key, value)
                stats["updated"] += 1
                action = "updated"
            else:
                db.session.add(SynCoreEmployee(**employee_dict))
                stats["added"] += 1
                action = "added"

            yield (
                "progress",
                {
                    "current": index,
                    "total": len(employees),
                    "employee_id": emp_id,
                    "name": name,
                    "action": action,
                },
            )
            yield (
                "log",
                {
                    "level": "info",
                    "message": f"[{index}/{len(employees)}] {action}: {name} ({emp_id})",
                },
            )
        except Exception as exc:
            stats["errors"] += 1
            msg = f"Error processing employee {emp_id}: {exc}"
            stats["error_details"].append(msg)
            yield ("log", {"level": "error", "message": msg})
            logger.error(msg)

    yield _emit_log("Committing changes to local database…")

    try:
        db.session.commit()
        summary = (
            f"Sync complete: {stats['added']} added, {stats['updated']} updated, "
            f"{stats['errors']} error(s) out of {stats['total']} total."
        )
        yield _emit_log(summary)
        logger.info(summary)
        yield (
            "done",
            {
                "success": True,
                "stats": stats,
                "message": summary,
            },
        )
    except Exception as exc:
        db.session.rollback()
        msg = f"Database commit failed: {exc}"
        stats["error_details"].append(msg)
        stats["errors"] = stats["total"]
        stats["added"] = 0
        stats["updated"] = 0
        yield ("log", {"level": "error", "message": msg})
        logger.error(msg)
        yield (
            "done",
            {
                "success": False,
                "stats": stats,
                "message": msg,
            },
        )


def sync_employees_to_db(client: SynCoreClient) -> dict:
    """Run sync and return final stats (non-streaming)."""
    stats = {}
    for event, data in iter_sync_employees_to_db(client):
        if event == "done":
            stats = data.get("stats", {})
    return stats