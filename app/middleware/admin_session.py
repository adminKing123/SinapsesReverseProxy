from __future__ import annotations

from functools import wraps

from flask import current_app, redirect, session, url_for


def admin_logged_in() -> bool:
    return bool(session.get("admin_authenticated"))


def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_logged_in():
            from flask import request

            nxt = request.path
            if request.query_string:
                nxt = request.full_path.rstrip("?")
            return redirect(url_for("admin.login", next=nxt))
        if not current_app.config.get("ADMIN_PASSWORD"):
            return redirect(url_for("admin.login", error="disabled"))
        return view(*args, **kwargs)

    return wrapped