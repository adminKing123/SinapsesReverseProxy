"""API key authentication: admin (.env) or per-user registered keys."""

from __future__ import annotations

import secrets

from flask import current_app, g, jsonify, request

from app.services.api_keys import hash_api_key


def extract_service_key() -> str | None:
    header = request.headers.get("X-Service-Key", "").strip()
    if header:
        return header
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def authenticate_request():
    """Set ``g.auth_mode`` to ``admin`` or ``user``. Return an error response or None."""
    if request.method == "OPTIONS":
        return None

    provided = extract_service_key()
    if not provided:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Missing service key (X-Service-Key or Authorization: Bearer)",
                }
            ),
            401,
        )

    admin = (current_app.config.get("SYNCORE_SERVICE_KEY") or "").strip()
    if admin and secrets.compare_digest(provided, admin):
        g.auth_mode = "admin"
        g.synapse_user_id = None
        g.registered_email = None
        return None

    from app.models.registered_api_key import RegisteredApiKey

    key_hash = hash_api_key(provided)
    record = RegisteredApiKey.query.filter_by(key_hash=key_hash, is_active=True).first()
    if record:
        g.auth_mode = "user"
        g.synapse_user_id = record.synapse_user_id
        g.registered_email = record.email
        return None

    return (
        jsonify({"success": False, "error": "Invalid service key"}),
        401,
    )


def require_service_key():
    return authenticate_request()