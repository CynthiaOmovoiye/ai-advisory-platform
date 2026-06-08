"""Document upload service with the malware-scan gate (Module 3 / security-review §5).

Uploads are validated three ways (extension + MIME + magic bytes), stored under an
opaque key **outside any public path**, and recorded with ``scan_status='pending'``.
A document is **never servable until a scan marks it 'clean'** — that gate is the core
security control. The scan itself runs in the worker (off the request path); here it's
a stub that approves clean files, with an obvious integration point for ClamAV/a vendor.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.access import Permission, Principal, authorize
from app.domain.uploads import InvalidUpload, validate_upload
from app.errors import AppError, Conflict, NotFound
from app.infra.storage import ObjectStorage
from app.repositories.base import (
    AssessmentRepository,
    AuditSink,
    DocumentRecord,
    DocumentRepository,
    TenantScope,
)


class UnprocessableUpload(AppError):
    code = "invalid_upload"
    http_status = 422


@dataclass
class DocumentService:
    documents: DocumentRepository
    assessments: AssessmentRepository
    storage: ObjectStorage
    audit: AuditSink
    max_upload_bytes: int = 26_214_400

    def upload(
        self,
        principal: Principal,
        organization_id: str,
        assessment_id: str,
        *,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> DocumentRecord:
        authorize(principal, Permission.ASSESSMENT_COMPLETE, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        if self.assessments.get(assessment_id, scope) is None:
            raise NotFound("assessment not found")

        try:
            validated = validate_upload(
                filename=filename,
                content_type=content_type,
                data=data,
                max_bytes=self.max_upload_bytes,
            )
        except InvalidUpload as exc:
            raise UnprocessableUpload(str(exc)) from exc

        # Opaque, tenant-namespaced key — never a public path, never the user's filename.
        key = f"documents/{organization_id}/{uuid.uuid4()}{validated.extension}"
        self.storage.put(key, data, content_type=validated.mime_type)

        record = DocumentRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            assessment_id=assessment_id,
            original_filename=filename,
            storage_key=key,
            mime_type=validated.mime_type,
            byte_size=validated.byte_size,
            sha256=validated.sha256,
            scan_status="pending",  # NOT servable until a scan marks it clean
        )
        self.documents.create(record, scope)
        self.audit.record(
            actor_user_id=principal.user_id,
            organization_id=organization_id,
            action="document.uploaded",
            entity_id=record.id,
        )
        return record

    def list_documents(
        self, principal: Principal, organization_id: str, assessment_id: str
    ) -> list[DocumentRecord]:
        authorize(principal, Permission.ASSESSMENT_READ, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        return self.documents.list_for_assessment(assessment_id, scope)

    def download_url(self, principal: Principal, organization_id: str, document_id: str) -> str:
        authorize(principal, Permission.ASSESSMENT_READ, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        doc = self.documents.get(document_id, scope)
        if doc is None:
            raise NotFound("document not found")  # cross-tenant ids resolve here too
        # THE GATE: refuse to vend a document that hasn't passed the malware scan.
        if doc.scan_status != "clean":
            raise Conflict(f"document is not available (scan status: {doc.scan_status})")
        return self.storage.presigned_url(doc.storage_key)

    def scan(self, organization_id: str, document_id: str, actor_user_id: str) -> DocumentRecord:
        """Run by the worker. Stub: approves the file as clean. Integration point for a
        real scanner (ClamAV/vendor) — set 'infected' to quarantine instead."""
        scope = TenantScope(organization_id=organization_id, acting_user_id=actor_user_id)
        doc = self.documents.get(document_id, scope)
        if doc is None:
            raise NotFound("document not found")
        # ... a real scanner would fetch self.storage.get(doc.storage_key) and inspect it ...
        result = self.documents.set_scan_status(document_id, "clean", scope)
        self.audit.record(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="document.scanned",
            entity_id=document_id,
        )
        return result
