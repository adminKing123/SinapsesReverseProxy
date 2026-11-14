"""Require SYNCORE_SERVICE_KEY on protected API routes."""

from __future__ import annotations

import secrets

from flask import current_app, jsonify, request


def extract_service_key() -> str | None:
    header = request.headers.get("X-Service-Key", "").strip()
    if header:
        return header
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def require_service_key():
    if request.method == "OPTIONS":
        return None

    expected = (current_app.config.get("SYNCORE_SERVICE_KEY") or "").strip()
    if not expected:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "SYNCORE_SERVICE_KEY is not configured on the server",
                }
            ),
            503,
        )

    provided = extract_service_key()
    if not provided or not secrets.compare_digest(provided, expected):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Missing or invalid service key (X-Service-Key or Authorization: Bearer)",
                }
            ),
            401,
        )
    return None