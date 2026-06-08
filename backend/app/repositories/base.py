"""Repository layer foundations: the tenant-scope primitive, the domain record
returned by repositories, and the Protocol interfaces the service depends on.

The repository layer is the **only** place persistence happens (ADR-0002) and the
place tenant isolation is *mechanically* enforced (ADR-0006). A tenant-scoped
read/write takes a :class:`TenantScope` as a **required** argument; the implementation
applies it to every row, so a developer cannot "forget" the
``WHERE organization_id = ...`` filter — they can't construct a scoped query without a
scope.

Crucially, repositories return **domain records** (:class:`AssessmentRecord`), not ORM
objects — so SQLAlchemy never leaks into the service layer, and the in-memory and SQL
implementations are interchangeable behind the same Protocols. The service is written
against these Protocols and works with either backend unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.llm.enhancement import Recommendation


@dataclass(frozen=True)
class TenantScope:
    """The organization a request operates within, plus who is acting.

    Derived by the service from the authenticated principal + the authorized target
    org — never from raw request input. Carrying the acting user id lets the
    repository/audit layer record provenance and (on Postgres) set the RLS session
    variable that is the independent second isolation layer.
    """

    organization_id: str
    acting_user_id: str

    def owns(self, organization_id: str) -> bool:
        return organization_id == self.organization_id


@dataclass(frozen=True)
class AssessmentRecord:
    """The repository's return contract for an assessment (subset of db/schema.sql).
    Storage-agnostic: both the in-memory and SQL repositories map to this shape."""

    id: str
    organization_id: str
    template_name: str
    ruleset_name: str
    ruleset_version: int
    responses: tuple[dict, ...]  # [{"key": ..., "value": ...}]
    status: str = "in_progress"


# --------------------------------------------------------------------------- #
# Protocols — the service depends on these, not on concrete implementations.
# --------------------------------------------------------------------------- #
class AssessmentRepository(Protocol):
    def get(self, assessment_id: str, scope: TenantScope) -> AssessmentRecord | None: ...
    def list(self, scope: TenantScope) -> list[AssessmentRecord]: ...
    def set_status(
        self, assessment_id: str, status: str, scope: TenantScope
    ) -> AssessmentRecord: ...


class RecommendationRepository(Protocol):
    def save_for_assessment(
        self, assessment_id: str, recommendations: list[Recommendation], scope: TenantScope
    ) -> None: ...
    def list_for_assessment(
        self, assessment_id: str, scope: TenantScope
    ) -> list[Recommendation]: ...
    def get(self, recommendation_id: str, scope: TenantScope) -> Recommendation | None: ...
    def update(self, recommendation: Recommendation, scope: TenantScope) -> Recommendation: ...


class AuditSink(Protocol):
    def record(
        self, *, actor_user_id: str, organization_id: str, action: str, entity_id: str
    ) -> None: ...


@dataclass(frozen=True)
class ReportRecord:
    """The repository's return contract for a generated report (a ``reports`` row)."""

    id: str
    organization_id: str
    assessment_id: str
    title: str
    status: str
    pdf_storage_key: str | None


class ReportRepository(Protocol):
    def save(self, report: ReportRecord, scope: TenantScope) -> None: ...
    def get_for_assessment(self, assessment_id: str, scope: TenantScope) -> ReportRecord | None: ...
