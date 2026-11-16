"""User registration flow (SSE) and OTP verification."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.employee import SynCoreEmployee
from app.models.registered_api_key import RegisteredApiKey
from app.models.registration_otp import RegistrationOtp
from app.services.api_keys import generate_api_key, hash_api_key
from app.services.email_otp import send_otp_email
from app.services.syncore import get_syn_core_client

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
RegEvent = tuple[str, dict]


def _sse_log(message: str, level: str = "info") -> RegEvent:
    return ("log", {"level": level, "message": message})


def iter_registration_start(email: str) -> Iterator[RegEvent]:
    email_norm = email.strip().lower()
    if not email_norm:
        yield _sse_log("Email is required", "error")
        yield ("error", {"success": False, "error": "Email is required"})
        return

    yield _sse_log(f"Looking up employee with email {email_norm}")

    employee = SynCoreEmployee.query.filter(
        db.func.lower(SynCoreEmployee.email) == email_norm
    ).first()

    if not employee:
        yield _sse_log("No synced employee found for this email", "error")
        yield (
            "user",
            {"found": False, "email": email_norm},
        )
        yield ("error", {"success": False, "error": "User not found in database. Run admin sync first."})
        return

    yield (
        "user",
        {
            "found": True,
            "email": employee.email,
            "user_id": employee.user_id,
            "name": employee.name,
            "employee_id": employee.id,
        },
    )
    yield _sse_log(f"User found: {employee.name} (HRMS user_id={employee.user_id})")

    yield _sse_log("Checking Webex token from HRMS…")
    client = get_syn_core_client()
    token_result = client.get_webex_token(employee.user_id, employee.signed_array)
    webex_found = "error" not in token_result
    yield (
        "webex",
        {
            "found": webex_found,
            "message": (
                "Webex token retrieved from HRMS"
                if webex_found
                else token_result.get("error", "Webex token not available")
            ),
        },
    )
    if webex_found:
        yield _sse_log("Webex token: found", "info")
    else:
        yield _sse_log("Webex token: not found", "warning")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = hash_api_key(otp)
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)

    RegistrationOtp.query.filter(
        RegistrationOtp.email == email_norm,
        RegistrationOtp.consumed_at.is_(None),
    ).update(
        {RegistrationOtp.consumed_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )

    db.session.add(
        RegistrationOtp(
            email=email_norm,
            synapse_user_id=employee.user_id,
            otp_hash=otp_hash,
            expires_at=expires,
        )
    )
    db.session.commit()

    send_otp_email(
        employee.email or email_norm,
        otp,
        synapse_user_id=employee.user_id,
        name=employee.name or "",
    )

    yield _sse_log("OTP sent (see server logs in dev until email is wired up)", "info")
    yield ("otp_sent", {"success": True, "email": email_norm, "expires_in_minutes": OTP_TTL_MINUTES})
    yield (
        "done",
        {
            "success": True,
            "requires_otp": True,
            "email": email_norm,
            "user_id": employee.user_id,
            "message": "Enter the 6-digit OTP sent to your email.",
        },
    )


def verify_registration(email: str, otp: str) -> dict:
    email_norm = email.strip().lower()
    otp_clean = str(otp).strip()
    if not email_norm or not otp_clean:
        return {"success": False, "error": "email and otp are required"}

    record = (
        RegistrationOtp.query.filter_by(email=email_norm, consumed_at=None)
        .order_by(RegistrationOtp.created_at.desc())
        .first()
    )
    if not record:
        return {"success": False, "error": "No pending OTP for this email"}

    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return {"success": False, "error": "OTP expired. Start registration again."}

    if hash_api_key(otp_clean) != record.otp_hash:
        return {"success": False, "error": "Invalid OTP"}

    employee = SynCoreEmployee.query.filter_by(user_id=record.synapse_user_id).first()
    if not employee:
        return {"success": False, "error": "Employee record missing"}

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    RegisteredApiKey.query.filter_by(synapse_user_id=record.synapse_user_id).update(
        {"is_active": False},
        synchronize_session=False,
    )

    db.session.add(
        RegisteredApiKey(
            synapse_user_id=record.synapse_user_id,
            email=email_norm,
            key_hash=key_hash,
            is_active=True,
        )
    )
    record.consumed_at = datetime.now(timezone.utc)
    db.session.commit()

    logger.info("Issued user API key for user_id=%s email=%s", record.synapse_user_id, email_norm)

    return {
        "success": True,
        "message": "Registration complete. Store your service key securely — it is shown only once.",
        "user_id": record.synapse_user_id,
        "email": email_norm,
        "name": employee.name,
        "service_key": raw_key,
    }