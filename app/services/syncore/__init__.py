from __future__ import annotations

from flask import current_app

from app.services.syncore.client import SynCoreClient

_client: SynCoreClient | None = None


def get_syn_core_client() -> SynCoreClient:
    global _client
    if _client is None:
        config = current_app.config.get("SYN_CORE_CONFIG") or {}
        _client = SynCoreClient(config)
    return _client


def reset_syn_core_client() -> None:
    global _client
    _client = None