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
    template_id: str | None = None


# --------------------------------------------------------------------------- #
# Protocols — the service depends on these, not on concrete implementations.
# --------------------------------------------------------------------------- #
class AssessmentRepository(Protocol):
    def get(self, assessment_id: str, scope: TenantScope) -> AssessmentRecord | None: ...
    def list(self, scope: TenantScope) -> list[AssessmentRecord]: ...
    def set_status(
        self, assessment_id: str, status: str, scope: TenantScope
    ) -> AssessmentRecord: ...
    def create(self, record: AssessmentRecord, scope: TenantScope) -> AssessmentRecord: ...
    def save_responses(
        self, assessment_id: str, responses: list[dict], scope: TenantScope
    ) -> None: ...


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


@dataclass(frozen=True)
class OrganizationRecord:
    id: str
    name: str
    slug: str


@dataclass(frozen=True)
class MemberRecord:
    id: str
    organization_id: str
    invited_email: str
    role: str
    status: str
    user_id: str | None = None


class OrganizationRepository(Protocol):
    def create(self, record: OrganizationRecord) -> None: ...
    def get(self, organization_id: str) -> OrganizationRecord | None: ...
    def slug_exists(self, slug: str) -> bool: ...


class MemberRepository(Protocol):
    def add(
        self,
        member: MemberRecord,
        scope: TenantScope,
        *,
        invite_token_hash: str | None,
        invited_by: str,
    ) -> None: ...
    def list(self, scope: TenantScope) -> list[MemberRecord]: ...
    def get(self, member_id: str, scope: TenantScope) -> MemberRecord | None: ...
    def set_status(self, member_id: str, status: str, scope: TenantScope) -> MemberRecord: ...
    def email_exists(self, email: str, scope: TenantScope) -> bool: ...


# --- Assessment templates (Module 3) — global catalog, not tenant-owned ------ #
@dataclass(frozen=True)
class QuestionRecord:
    id: str
    key: str
    prompt: str
    type: str
    config: dict
    order_index: int


@dataclass(frozen=True)
class SectionRecord:
    id: str
    title: str
    order_index: int
    questions: tuple[QuestionRecord, ...]


@dataclass(frozen=True)
class TemplateRecord:
    id: str
    category: str
    title: str
    description: str | None
    version: int
    status: str
    sections: tuple[SectionRecord, ...]


class TemplateRepository(Protocol):
    def create(self, template: TemplateRecord) -> None: ...
    def list(self) -> list[TemplateRecord]: ...
    def get(self, template_id: str) -> TemplateRecord | None: ...
    def set_status(self, template_id: str, status: str) -> TemplateRecord: ...


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    organization_id: str
    assessment_id: str | None
    original_filename: str
    storage_key: str
    mime_type: str
    byte_size: int
    sha256: str
    scan_status: str


class DocumentRepository(Protocol):
    def create(self, document: DocumentRecord, scope: TenantScope) -> None: ...
    def list_for_assessment(
        self, assessment_id: str, scope: TenantScope
    ) -> list[DocumentRecord]: ...
    def get(self, document_id: str, scope: TenantScope) -> DocumentRecord | None: ...
    def set_scan_status(
        self, document_id: str, status: str, scope: TenantScope
    ) -> DocumentRecord: ...
