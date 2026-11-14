"""SynCore payload encoding (function-based)."""

from __future__ import annotations

import base64
import json


def atob(b64: str) -> str:
    raw = base64.b64decode(b64)
    return raw.decode("latin-1")


def btoa(binary_str: str) -> str:
    if not isinstance(binary_str, str):
        raise TypeError("btoa expects a str")
    raw = binary_str.encode("latin-1")
    return base64.b64encode(raw).decode("ascii")


def encode(data: dict) -> dict:
    return {"data": base64.b64encode(json.dumps(data).encode()).decode()}


def decode(res: dict) -> dict:
    data = res["res"]
    return json.loads(base64.b64decode(data).decode())


def get_code(data: dict) -> str:
    string = (
        f'{data["user_id"]}|{data["employee_id"]}|{data["username"]}|'
        f'{data["user_type"]}'
    )
    return btoa(string)