from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


class RegisteredApiKey(db.Model):
    __tablename__ = "registered_api_keys"

    id = db.Column(db.Integer, primary_key=True)
    synapse_user_id = db.Column(db.String(50), nullable=False, index=True)
    email = db.Column(db.String(200), nullable=False, index=True)
    key_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    key_ciphertext = db.Column(db.Text, nullable=True)
    otp_ciphertext = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RegisteredApiKey user_id={self.synapse_user_id!r} email={self.email!r}>"