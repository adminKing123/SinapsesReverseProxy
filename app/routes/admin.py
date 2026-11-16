"""Admin UI: password login and registered API key listing."""

from __future__ import annotations

import secrets
from datetime import timezone

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app.middleware.admin_session import admin_logged_in, require_admin
from app.models.registered_api_key import RegisteredApiKey
from app.services.key_storage import decrypt_service_key

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

PER_PAGE = 25


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if admin_logged_in():
        return redirect(url_for("admin.registered_users"))

    if request.method == "POST":
        password = current_app.config.get("ADMIN_PASSWORD") or ""
        if not password:
            return render_template(
                "admin_login.html",
                error="Admin login is not configured (set ADMIN_PASSWORD in .env).",
            )
        submitted = request.form.get("password", "")
        if secrets.compare_digest(submitted, password):
            session.clear()
            session["admin_authenticated"] = True
            session.permanent = True
            dest = request.args.get("next") or url_for("admin.registered_users")
            if not dest.startswith("/admin"):
                dest = url_for("admin.registered_users")
            return redirect(dest)
        return render_template("admin_login.html", error="Invalid password.")

    return render_template("admin_login.html", error=None)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/registered-users")
@require_admin
def registered_users():
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    pagination = (
        RegisteredApiKey.query.order_by(RegisteredApiKey.created_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )

    secret = current_app.config["SECRET_KEY"]
    rows = []
    for record in pagination.items:
        created = record.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        service_key = decrypt_service_key(record.key_ciphertext or "", secret)
        if service_key is None:
            service_key = "—" if not record.key_ciphertext else "(unreadable)"
        rows.append(
            {
                "email": record.email,
                "user_id": record.synapse_user_id,
                "service_key": service_key,
                "created_at": created,
                "is_active": record.is_active,
            }
        )

    return render_template(
        "admin_registered_users.html",
        rows=rows,
        pagination=pagination,
    )