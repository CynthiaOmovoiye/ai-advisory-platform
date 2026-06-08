"""Document DTOs (Module 3 / security-review §5)."""

from __future__ import annotations

from pydantic import BaseModel

from app.repositories.base import DocumentRecord


class DocumentOut(BaseModel):
    id: str
    original_filename: str
    mime_type: str
    byte_size: int
    scan_status: str

    @classmethod
    def from_domain(cls, d: DocumentRecord) -> DocumentOut:
        return cls(
            id=d.id,
            original_filename=d.original_filename,
            mime_type=d.mime_type,
            byte_size=d.byte_size,
            scan_status=d.scan_status,
        )


class DownloadResponse(BaseModel):
    url: str
