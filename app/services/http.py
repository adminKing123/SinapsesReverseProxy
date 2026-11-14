"""Low-level HTTP helpers (function-based). Uses a shared Session with trust_env=False."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Mapping, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


@lru_cache(maxsize=1)
def get_http_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def get(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout: int = 15,
) -> requests.Response:
    return get_http_session().get(url, headers=dict(headers or {}), timeout=timeout)


def post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    return get_http_session().post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


def check_hrms_reachable(api_base: str, timeout: int = 15) -> dict:
    """Light connectivity check against the HRMS host (GET root)."""
    url = api_base.rstrip("/")
    try:
        response = get(url, timeout=timeout)
        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "snippet": (response.text or "")[:500],
        }
    except requests.exceptions.RequestException as exc:
        logger.error("HRMS connectivity check failed: %s", exc)
        return {"ok": False, "error": str(exc)}