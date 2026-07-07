"""
SQLAlchemy models for cases, audit_logs (insert-only), feedback_corrections,
and a users stub (no real auth — hardcoded Patient/Reviewer roles).

// DEMO-REAL
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Stub only — no real auth. Two hardcoded roles: patient, reviewer."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("patient", "reviewer", name="user_role"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class Case(Base):
    """One row per Prior Authorization case. Payloads mirror AgenticPAState."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_number: Mapped[int] = mapped_column(
        Integer, Identity(always=False), nullable=False, unique=True
    )
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clinical_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    financial_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    policy_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    routing_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="case")
    feedback_corrections: Mapped[list["FeedbackCorrection"]] = relationship(
        back_populates="case"
    )


class AuditLog(Base):
    """Insert-only trace of agent activity for the Admin trace view.

    Enforced insert-only both at the app layer (no update()/delete() calls
    should ever be issued against this model) and at the DB layer via a
    trigger installed in the initial migration that rejects UPDATE/DELETE.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="audit_logs")


class FeedbackCorrection(Base):
    """Reviewer corrections keyed by (icd10_family, cpt_family) for the
    self-improving feedback loop — the next case sharing an ICD-10 family
    vector-searches this table and injects the top-3 matches as few-shot
    examples into Intake. `id` is the true primary key (multiple corrections
    can share the same family pair, e.g. PA-005 reusing PA-001's); the
    composite (icd10_family, cpt_family) is indexed for that lookup, not
    unique.
    """

    __tablename__ = "feedback_corrections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    icd10_family: Mapped[str] = mapped_column(String(16), nullable=False)
    cpt_family: Mapped[str] = mapped_column(String(16), nullable=False)

    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id"), nullable=False
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    corrected_field: Mapped[str] = mapped_column(String(128), nullable=False)
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    case: Mapped["Case"] = relationship(back_populates="feedback_corrections")

    __table_args__ = (
        Index("ix_feedback_corrections_family", "icd10_family", "cpt_family"),
    )


class RvuValue(Base):
    """Physician Fee Schedule RVUs per CPT/HCPCS code, ingested verbatim from
    CMS PPRRVU2026_Jan_nonQPP.csv (backend/data/rates/).

    // DEMO-REAL
    """

    __tablename__ = "rvu_values"

    cpt: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[str] = mapped_column(String(4), nullable=False)
    work_rvu: Mapped[float] = mapped_column(Float, nullable=False)
    pe_rvu_nonfacility: Mapped[float] = mapped_column(Float, nullable=False)
    mp_rvu: Mapped[float] = mapped_column(Float, nullable=False)


class GpciValue(Base):
    """Geographic Practice Cost Indices per (state, locality), ingested
    verbatim from CMS GPCI2026.csv (backend/data/rates/).

    // DEMO-REAL
    """

    __tablename__ = "gpci_values"

    state: Mapped[str] = mapped_column(String(2), primary_key=True)
    locality_number: Mapped[str] = mapped_column(String(4), primary_key=True)
    locality_name: Mapped[str] = mapped_column(String(255), nullable=False)
    work_gpci: Mapped[float] = mapped_column(Float, nullable=False)
    pe_gpci: Mapped[float] = mapped_column(Float, nullable=False)
    mp_gpci: Mapped[float] = mapped_column(Float, nullable=False)


class LocalityCounty(Base):
    """State/locality -> county-list rows, ingested verbatim from CMS
    26LOCCO.csv (backend/data/rates/). One row per (state, locality); the
    `counties_raw` text is the CMS free-text field, kept as-is for audit.

    // DEMO-REAL
    """

    __tablename__ = "locality_counties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mac: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    locality_number: Mapped[str] = mapped_column(String(4), nullable=False)
    fee_schedule_area: Mapped[str] = mapped_column(String(255), nullable=False)
    counties_raw: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_locality_counties_state", "state"),
    )


class AdminSettings(Base):
    """Single-row (id=1) table of admin-tunable thresholds that used to be
    hardcoded constants (SLA window, expedite window, confidence threshold,
    which downstream agents are enabled). Read by supervisor.py /
    peer_review_agent.py at call time so a change takes effect on the next
    case without a redeploy.

    // DEMO-REAL
    """

    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sla_hours: Mapped[float] = mapped_column(Float, nullable=False)
    expedite_hours: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    agents_enabled: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ZipLocality(Base):
    """zip -> (state, locality) resolved by matching zip_county_subset.csv
    against locality_counties. Covers only the 5 Hero Case zips.

    // DEMO-REAL (the zip itself comes from general public geography, see
    backend/app/data/zip_county_subset.csv; the locality resolution and every
    rate computed from it is real CMS data)
    """

    __tablename__ = "zip_locality"

    zip_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    county: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    locality_number: Mapped[str] = mapped_column(String(4), nullable=False)
