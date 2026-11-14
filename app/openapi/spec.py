"""OpenAPI 3.0 specification for SynCore proxy APIs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _emp_id() -> dict:
    return {
        "name": "employee_id",
        "in": "path",
        "required": True,
        "schema": {"type": "integer"},
        "description": "Local DB primary key (`syncore_employees.id`), not HRMS user_id.",
    }


def _json_ok(description: str = "Success") -> dict:
    return {
        "200": {
            "description": description,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SuccessEnvelope"},
                }
            },
        }
    }


def _error_responses() -> dict:
    return {
        "401": {"$ref": "#/components/responses/Unauthorized"},
        "404": {"$ref": "#/components/responses/NotFound"},
        "500": {"$ref": "#/components/responses/ServerError"},
    }


def build_openapi_spec(server_url: str) -> dict[str, Any]:
    secured = [{"ServiceKey": []}]

    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "Synapses SynCore Proxy API",
            "version": "1.0.0",
            "description": (
                "JSON REST proxy for SynCore HRMS. Use **Authorize** to set "
                "**X-Service-Key** (`SYNCORE_SERVICE_KEY` from server `.env`). "
                "Run **POST /sync** first to populate local employee IDs."
            ),
        },
        "servers": [{"url": server_url}],
        "tags": [
            {"name": "Overview"},
            {"name": "Employees"},
            {"name": "Sync"},
            {"name": "Attendance"},
            {"name": "Leaves & holidays"},
            {"name": "Projects & logs"},
            {"name": "Worklog"},
            {"name": "Other"},
            {"name": "Health"},
        ],
        "paths": {},
        "components": {
            "securitySchemes": {
                "ServiceKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Service-Key",
                    "description": "Value of SYNCORE_SERVICE_KEY from server .env",
                }
            },
            "schemas": {
                "SuccessEnvelope": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                    },
                    "additionalProperties": True,
                },
                "ErrorEnvelope": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {"type": "string"},
                    },
                },
                "WorklogFill": {
                    "type": "object",
                    "required": [
                        "project_id",
                        "module_id",
                        "activity_id",
                        "work_desc",
                        "hour_clocked",
                    ],
                    "properties": {
                        "project_id": {"type": "string", "example": "12"},
                        "module_id": {"type": "string", "example": "3"},
                        "activity_id": {"type": "string", "example": "7"},
                        "work_desc": {"type": "string"},
                        "hour_clocked": {"type": "string", "example": "2"},
                        "keyword": {
                            "type": "string",
                            "description": "Optional prefix stripped from work_desc",
                        },
                    },
                },
                "OverrideComment": {
                    "type": "object",
                    "properties": {
                        "override_comment": {"type": "string", "default": ""},
                    },
                },
            },
            "responses": {
                "Unauthorized": {
                    "description": "Missing or invalid service key",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                        }
                    },
                },
                "NotFound": {
                    "description": "Employee not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                        }
                    },
                },
                "ServerError": {
                    "description": "Server error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                        }
                    },
                },
            },
        },
    }

    paths = spec["paths"]

    def add(path: str, method: str, op: dict, *, auth: bool = True) -> None:
        paths.setdefault(path, {})[method] = op
        if auth:
            op["security"] = deepcopy(secured)

    # ── Health (no auth) ───────────────────────────────────────────────────
    paths["/health"] = {
        "get": {
            "tags": ["Health"],
            "summary": "Liveness check",
            "security": [],
            "responses": _json_ok(),
        }
    }
    paths["/health/hrms"] = {
        "get": {
            "tags": ["Health"],
            "summary": "HRMS API_BASE connectivity",
            "security": [],
            "responses": _json_ok(),
        }
    }

    pfx = "/api/syncore/open"

    add(
        f"{pfx}/",
        "get",
        {
            "tags": ["Overview"],
            "summary": "API index",
            "description": "Lists registered routes.",
            "responses": _json_ok(),
        },
    )
    add(
        f"{pfx}/stats",
        "get",
        {"tags": ["Overview"], "summary": "Dashboard stats", "responses": _json_ok()},
    )
    add(
        f"{pfx}/sync",
        "post",
        {
            "tags": ["Sync"],
            "summary": "Sync employees (SSE)",
            "description": (
                "Streams **Server-Sent Events** (`text/event-stream`, HTTP 200). "
                "Events: `log`, `progress`, `done`. Use curl `-N` or read the response stream."
            ),
            "responses": {
                "200": {
                    "description": "SSE stream",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                },
                **_error_responses(),
            },
        },
    )

    add(
        f"{pfx}/employees",
        "get",
        {
            "tags": ["Employees"],
            "summary": "List employees",
            "parameters": [
                {"name": "q", "in": "query", "schema": {"type": "string"}},
                {
                    "name": "status",
                    "in": "query",
                    "schema": {
                        "type": "string",
                        "enum": ["all", "active", "inactive"],
                        "default": "all",
                    },
                },
                {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                {
                    "name": "per_page",
                    "in": "query",
                    "schema": {"type": "integer", "default": 25, "maximum": 100},
                },
            ],
            "responses": {**_json_ok(), **_error_responses()},
        },
    )
    add(
        f"{pfx}/employees/by-email",
        "get",
        {
            "tags": ["Employees"],
            "summary": "Employee by email",
            "parameters": [
                {
                    "name": "email",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string", "format": "email"},
                }
            ],
            "responses": {**_json_ok(), **_error_responses()},
        },
    )
    add(
        f"{pfx}/employees/{{employee_id}}",
        "get",
        {
            "tags": ["Employees"],
            "summary": "Employee detail",
            "parameters": [_emp_id()],
            "responses": {**_json_ok(), **_error_responses()},
        },
    )

    emp = _emp_id()
    date_range = [
        {
            "name": "start_date",
            "in": "query",
            "schema": {"type": "string", "example": "11/01/2025"},
            "description": "MM/DD/YYYY",
        },
        {
            "name": "end_date",
            "in": "query",
            "schema": {"type": "string", "example": "11/30/2025"},
            "description": "MM/DD/YYYY",
        },
    ]
    page_params = [
        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
        {
            "name": "per_page",
            "in": "query",
            "schema": {"type": "integer"},
        },
    ]

    def emp_get(path_suffix: str, summary: str, tag: str, extra_params=None):
        add(
            f"{pfx}/employees/{{employee_id}}{path_suffix}",
            "get",
            {
                "tags": [tag],
                "summary": summary,
                "parameters": [emp] + (extra_params or []),
                "responses": {**_json_ok(), **_error_responses()},
            },
        )

    def emp_post(path_suffix: str, summary: str, tag: str, body_ref: str | None = None):
        op: dict = {
            "tags": [tag],
            "summary": summary,
            "parameters": [emp],
            "responses": {**_json_ok(), **_error_responses()},
        }
        if body_ref:
            op["requestBody"] = {
                "required": False,
                "content": {
                    "application/json": {"schema": {"$ref": f"#/components/schemas/{body_ref}"}}
                },
            }
        add(f"{pfx}/employees/{{employee_id}}{path_suffix}", "post", op)

    emp_get("/logs", "Today's attendance logs", "Attendance")
    emp_get(
        "/attendance",
        "Attendance range",
        "Attendance",
        date_range
        + [
            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
            {
                "name": "per_page",
                "in": "query",
                "schema": {"type": "integer", "default": 50, "maximum": 200},
            },
        ],
    )
    emp_get("/attendance/current-month", "Attendance current month (IST)", "Attendance")
    emp_get("/leaves", "Leave records", "Leaves & holidays", date_range + page_params)
    emp_get(
        "/leaves/current-month",
        "Leaves current month (IST)",
        "Leaves & holidays",
    )
    emp_get(
        "/holiday-calendar",
        "Holiday & leave calendar",
        "Leaves & holidays",
        [
            {
                "name": "start_date",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "end_date",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            },
        ],
    )
    emp_get(
        "/holiday-calendar/current-month",
        "Holiday calendar current month",
        "Leaves & holidays",
    )
    emp_get("/today-leaves-holidays", "Today's leaves & holidays", "Leaves & holidays")
    emp_get("/today-working-status", "Today working status", "Leaves & holidays")
    emp_get("/webex-token", "Webex token from HRMS", "Other")
    emp_get(
        "/image",
        "Employee avatar URL",
        "Other",
        [
            {
                "name": "access_token",
                "in": "query",
                "schema": {"type": "string"},
                "description": "Optional; skips HRMS token lookup",
            }
        ],
    )
    emp_get(
        "/projects",
        "Assigned projects",
        "Projects & logs",
        [
            {
                "name": "status",
                "in": "query",
                "schema": {"type": "string", "enum": ["all", "active", "inactive"]},
            },
            {"name": "q", "in": "query", "schema": {"type": "string"}},
            *page_params,
        ],
    )
    add(
        f"{pfx}/employees/{{employee_id}}/projects/{{project_id}}",
        "get",
        {
            "tags": ["Projects & logs"],
            "summary": "Project modules & activities",
            "parameters": [
                emp,
                {
                    "name": "project_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            ],
            "responses": {**_json_ok(), **_error_responses()},
        },
    )
    emp_get(
        "/project-logs",
        "Project work logs",
        "Projects & logs",
        date_range
        + [
            {"name": "project_id", "in": "query", "schema": {"type": "string"}},
            {"name": "module_id", "in": "query", "schema": {"type": "string"}},
            {"name": "activity_id", "in": "query", "schema": {"type": "string"}},
            *page_params,
        ],
    )
    emp_get(
        "/project-logs/current-month",
        "Project logs current month",
        "Projects & logs",
    )
    emp_get("/email-settings", "Email notification settings", "Other")
    emp_post("/login", "Mark login (clock in)", "Attendance", "OverrideComment")
    emp_post("/logout", "Mark logout (clock out)", "Attendance", "OverrideComment")
    emp_get("/worklog/projects", "Worklog — list projects", "Worklog")
    emp_get(
        "/worklog/project-details",
        "Worklog — modules & activities",
        "Worklog",
        [
            {
                "name": "project_id",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }
        ],
    )
    emp_post("/worklog/fill", "Submit daily work log", "Worklog", "WorklogFill")

    return spec