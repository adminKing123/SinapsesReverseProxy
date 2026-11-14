from __future__ import annotations

from datetime import date, datetime, timezone

from app.extensions import db


class TempUserLog(db.Model):
    """Free-form text logs keyed by SynCore HRMS ``user_id`` (not local employee PK)."""

    __tablename__ = "temp_user_logs"

    id = db.Column(db.Integer, primary_key=True)
    synapse_user_id = db.Column(db.String(50), nullable=False, index=True)
    log_text = db.Column(db.Text, nullable=False)
    log_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.Index("ix_temp_user_logs_user_date", "synapse_user_id", "log_date"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.synapse_user_id,
            "log": self.log_text,
            "date": self.log_date.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }