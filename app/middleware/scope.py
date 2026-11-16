"""Per-user API scope (non-admin keys)."""

from __future__ import annotations

from flask import g

from app.models.employee import SynCoreEmployee
from app.routes.helpers import api_error


def is_admin() -> bool:
    return getattr(g, "auth_mode", None) == "admin"


def require_admin():
    if not is_admin():
        return api_error("Admin service key required for this endpoint", 403)
    return None


def require_synapse_user_id(synapse_user_id: str):
    if is_admin():
        return None
    if str(getattr(g, "synapse_user_id", "")) != str(synapse_user_id):
        return api_error("This key is not allowed to access that user_id", 403)
    return None


def require_employee_access(employee: SynCoreEmployee):
    if is_admin():
        return None
    if str(employee.user_id) != str(getattr(g, "synapse_user_id", "")):
        return api_error("This key is not allowed to access this employee", 403)
    return None


def require_email_access(email: str):
    if is_admin():
        return None
    registered_email = (getattr(g, "registered_email", "") or "").lower()
    if registered_email != email.strip().lower():
        return api_error("This key may only access your own email", 403)
    return None