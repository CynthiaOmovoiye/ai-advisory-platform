"""Document upload/download routes (Module 3 / security-review §5).

Uploads are validated (extension + MIME + magic bytes) and size-bounded, stored
outside any public path, and scanned in the worker. A document is not downloadable
until its scan_status is 'clean' (the gate).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.api.deps import (
    CallerContext,
    get_caller,
    get_db,
    get_document_service,
    get_scan_enqueuer,
    require,
)
from app.domain.access import Permission
from app.errors import AppError
from app.schemas.document import DocumentOut, DownloadResponse
from app.services.document_service import DocumentService

router = APIRouter(tags=["Documents"])


class PayloadTooLarge(AppError):
    code = "payload_too_large"
    http_status = 413


@router.post(
    "/assessments/{assessment_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentOut,
)
async def upload_document(
    assessment_id: str,
    request: Request,
    file: UploadFile = File(...),
    _scope=Depends(require(Permission.ASSESSMENT_COMPLETE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: DocumentService = Depends(get_document_service),
    enqueue: Callable[..., None] = Depends(get_scan_enqueuer),
) -> DocumentOut:
    # Bound the read so a huge upload can't exhaust memory (defense before validation).
    data = await file.read(svc.max_upload_bytes + 1)
    if len(data) > svc.max_upload_bytes:
        raise PayloadTooLarge("file exceeds the maximum upload size")
    doc = svc.upload(
        caller.principal,
        caller.organization_id,
        assessment_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        data=data,
    )
    db.commit()
    enqueue(
        document_id=doc.id,
        organization_id=caller.organization_id,
        actor_user_id=caller.principal.user_id,
    )
    return DocumentOut.from_domain(doc)


@router.get("/assessments/{assessment_id}/documents", response_model=list[DocumentOut])
def list_documents(
    assessment_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: DocumentService = Depends(get_document_service),
) -> list[DocumentOut]:
    docs = svc.list_documents(caller.principal, caller.organization_id, assessment_id)
    return [DocumentOut.from_domain(d) for d in docs]


@router.get("/documents/{document_id}/download", response_model=DownloadResponse)
def download_document(
    document_id: str,
    _scope=Depends(require(Permission.ASSESSMENT_READ)),
    caller: CallerContext = Depends(get_caller),
    svc: DocumentService = Depends(get_document_service),
) -> DownloadResponse:
    # 409 until the malware scan marks the document clean.
    url = svc.download_url(caller.principal, caller.organization_id, document_id)
    return DownloadResponse(url=url)
