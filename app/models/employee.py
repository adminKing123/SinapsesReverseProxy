from __future__ import annotations

from datetime import date, datetime, timezone

from app.extensions import db


class SynCoreEmployee(db.Model):
    __tablename__ = "syncore_employees"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False, index=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    signed_array = db.Column(db.String(255), nullable=True)

    name = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(200), nullable=True, index=True)
    gender = db.Column(db.String(20), nullable=True)

    firm_id = db.Column(db.String(50), nullable=True, index=True)
    firm_name = db.Column(db.String(200), nullable=True)
    org_team_id = db.Column(db.String(50), nullable=True)
    org_name = db.Column(db.String(200), nullable=True)
    is_org_manager = db.Column(db.Boolean, default=False, nullable=False)

    designation = db.Column(db.String(200), nullable=True)
    user_type = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True, index=True)

    team_lead_id = db.Column(db.String(50), nullable=True)
    team_lead_name = db.Column(db.String(200), nullable=True)

    reporting_time = db.Column(db.String(20), nullable=True)
    working_hours = db.Column(db.String(20), nullable=True)
    monthly_worklog_hours = db.Column(db.String(20), nullable=True)

    joining_date = db.Column(db.Date, nullable=True, index=True)
    leaving_date = db.Column(db.Date, nullable=True)
    training_completion_date = db.Column(db.Date, nullable=True)

    comp_off = db.Column(db.String(20), nullable=True)
    emergency_leave = db.Column(db.String(20), nullable=True)
    casual_leave = db.Column(db.String(20), nullable=True)
    extended_leave = db.Column(db.String(20), nullable=True)

    syn_coin = db.Column(db.String(20), nullable=True)
    overrides = db.Column(db.String(20), nullable=True)

    created_by = db.Column(db.String(200), nullable=True)
    modified_by = db.Column(db.String(200), nullable=True)

    last_synced_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def is_active(self) -> bool:
        return bool(self.status and self.status.lower() == "active")