"""Report DTOs (Module 8)."""

from __future__ import annotations

from pydantic import BaseModel

from app.repositories.base import ReportRecord


class ReportOut(BaseModel):
    id: str
    assessment_id: str
    title: str
    status: str
    pdf_url: str | None  # short-lived pre-signed URL; null until rendered

    @classmethod
    def from_domain(cls, report: ReportRecord, pdf_url: str | None) -> ReportOut:
        return cls(
            id=report.id,
            assessment_id=report.assessment_id,
            title=report.title,
            status=report.status,
            pdf_url=pdf_url,
        )
