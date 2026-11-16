"""Public registration UI and OTP API (no service key on start/verify)."""

from __future__ import annotations

import logging

from flask import Blueprint, Response, jsonify, render_template, request, stream_with_context

from app.routes.helpers import api_error, request_json_or_form
from app.routes.sse import format_sse
from app.services.registration import iter_registration_start, verify_registration

logger = logging.getLogger(__name__)

register_bp = Blueprint("register", __name__)


@register_bp.route("/register")
def register_page():
    return render_template("register.html")


@register_bp.route("/api/register/start", methods=["POST"])
def register_start():
    """SSE: lookup user, Webex token check, send OTP."""
    data = request_json_or_form()
    email = str(data.get("email", "")).strip()

    @stream_with_context
    def generate():
        yield format_sse("log", {"level": "info", "message": "Registration started"})
        try:
            for event_name, payload in iter_registration_start(email):
                yield format_sse(event_name, payload)
        except Exception as exc:
            logger.error("Registration start error: %s", exc, exc_info=True)
            yield format_sse("error", {"success": False, "error": str(exc)})

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


@register_bp.route("/api/register/verify", methods=["POST"])
def register_verify():
    data = request_json_or_form()
    result = verify_registration(
        str(data.get("email", "")),
        str(data.get("otp", "")),
    )
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 201