"""Webex API helpers (function-based)."""

from __future__ import annotations

import logging

import requests

from app.services.http import get

logger = logging.getLogger(__name__)

_WEBEX_API_BASE = "https://webexapis.com/v1"
_REQUEST_TIMEOUT = 20


def get_employee_image(access_token: str) -> dict:
    """Return ``{"image_url": ...}`` or ``{"error": ...}``."""
    try:
        response = get(
            f"{_WEBEX_API_BASE}/people/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Webex people/me failed: %s", exc)
        return {"error": "Failed to fetch employee image."}

    return {"image_url": data.get("avatar", "image is not available.")}