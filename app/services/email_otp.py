"""OTP email delivery (placeholder — logs only for now)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def send_otp_email(to_email: str, otp: str, *, synapse_user_id: str, name: str = "") -> None:
    """Send OTP email. Current implementation logs to the application logger."""
    logger.info(
        "[OTP email — not sent] to=%s user_id=%s name=%r otp=%s",
        to_email,
        synapse_user_id,
        name,
        otp,
    )