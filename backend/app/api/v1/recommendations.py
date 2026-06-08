"""Consultant workspace routes (Module 9).

PATCH edits narrative and/or moves the review status. The route picks the permission
to enforce based on what's being done: editing requires RECOMMENDATION_EDIT, a status
change requires RECOMMENDATION_APPROVE. Both are default-deny guarded.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CallerContext, get_caller, get_db, get_recommendation_service, require
from app.domain.access import Permission
from app.schemas.recommendation import RecommendationOut, RecommendationPatch
from app.services.recommendation_service import RecommendationService

router = APIRouter(tags=["Recommendations"])


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def patch_recommendation(
    recommendation_id: str,
    patch: RecommendationPatch,
    # Editing requires the edit permission; approving/rejecting additionally requires
    # the approve permission (enforced in the service). The guard here gates entry.
    _scope=Depends(require(Permission.RECOMMENDATION_EDIT)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationOut:
    org = caller.organization_id
    result = None
    if any(v is not None for v in (patch.title, patch.finding, patch.rationale, patch.remediation)):
        result = svc.edit(
            caller.principal, org, recommendation_id,
            title=patch.title, finding=patch.finding,
            rationale=patch.rationale, remediation=patch.remediation,
        )
    if patch.status is not None:
        result = svc.set_status(caller.principal, org, recommendation_id, patch.status)
    if result is None:
        # Nothing to do — re-read current state (still authorized + scoped).
        result = svc.edit(caller.principal, org, recommendation_id)  # no-op edit returns current
    db.commit()
    return RecommendationOut.from_domain(result)
