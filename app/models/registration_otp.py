from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


class RegistrationOtp(db.Model):
    __tablename__ = "registration_otps"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False, index=True)
    synapse_user_id = db.Column(db.String(50), nullable=False, index=True)
    otp_hash = db.Column(db.String(64), nullable=False)
    otp_ciphertext = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )