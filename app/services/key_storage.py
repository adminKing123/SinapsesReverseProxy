"""Encrypt registered API keys at rest for admin display (Fernet + SECRET_KEY)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_service_key(plaintext: str, secret_key: str) -> str:
    return _fernet(secret_key).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_service_key(ciphertext: str, secret_key: str) -> str | None:
    if not ciphertext:
        return None
    try:
        return _fernet(secret_key).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None