"""SQLAlchemy ORM models for the assessment use-case.

A focused subset of db/schema.sql (the canonical schema) — enough to run the
`complete-assessment` flow against a real database. ORM objects never leave the
repository layer; repositories map them to the domain ``AssessmentRecord`` /
``Recommendation`` shapes (ADR-0002).

Every tenant-owned table carries ``organization_id`` (ADR-0006).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base, JSONType


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "invited_email", name="uq_member_org_email"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, nullable=True)  # null until invite accepted
    invited_email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="org_user")
    status: Mapped[str] = mapped_column(String, nullable=False, default="invited")
    invited_by: Mapped[str] = mapped_column(String, nullable=True)
    invite_token_hash: Mapped[str] = mapped_column(String, nullable=True)  # store hash, never raw
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    ruleset_name: Mapped[str] = mapped_column(String, nullable=False)
    ruleset_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")

    responses: Mapped[list[Response]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class Response(Base):
    __tablename__ = "responses"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_key: Mapped[str] = mapped_column(String, nullable=False)
    value = mapped_column(JSONType, nullable=False)  # typed per question (ADR-0008)


class RecommendationRow(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    finding: Mapped[str] = mapped_column(Text, nullable=False)  # deterministic source of truth
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    remediation: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "llm" | "fallback"
    grounding_passed: Mapped[bool] = mapped_column(nullable=True)
    grounding_reasons = mapped_column(JSONType, nullable=False, default=list)
    # consultant-workspace lifecycle
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    edited_by: Mapped[str] = mapped_column(String, nullable=True)


class ReportRow(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    pdf_storage_key: Mapped[str] = mapped_column(String, nullable=True)


class EvaluationRunRow(Base):
    """An evaluation run's aggregate scores (Module 6 → admin/eval dashboard).

    Not tenant-owned — evaluation is a system/global concern run by admins against
    curated datasets, so there is no organization_id here.
    """

    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String, nullable=False)
    ruleset_name: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    accuracy: Mapped[float] = mapped_column(Float, nullable=True)
    consistency: Mapped[float] = mapped_column(Float, nullable=True)
    completeness: Mapped[float] = mapped_column(Float, nullable=True)
    hallucination_rate: Mapped[float] = mapped_column(Float, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLogRow(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=True)
    organization_id: Mapped[str] = mapped_column(String, index=True, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
