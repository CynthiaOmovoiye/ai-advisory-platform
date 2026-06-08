"""Organization & member routes (Module 2).

Tenant scope is implicit: member operations act on the caller's active organization
(from the verified session), never an org id from request input. Org creation is the
one global action; the creator becomes a member of the new org.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CallerContext, get_caller, get_db, get_organization_service, require
from app.domain.access import Permission
from app.schemas.organization import (
    CreateOrganizationRequest,
    InviteMemberRequest,
    InviteMemberResponse,
    MemberOut,
    OrganizationOut,
)
from app.services.organization_service import OrganizationService

router = APIRouter(tags=["Organizations"])


@router.post("/organizations", status_code=status.HTTP_201_CREATED, response_model=OrganizationOut)
def create_organization(
    body: CreateOrganizationRequest,
    _scope=Depends(require(Permission.ORGANIZATION_CREATE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: OrganizationService = Depends(get_organization_service),
) -> OrganizationOut:
    org = svc.create_organization(
        caller.principal, caller.organization_id, name=body.name, slug=body.slug
    )
    db.commit()
    return OrganizationOut.from_domain(org)


@router.get("/members", response_model=list[MemberOut])
def list_members(
    _scope=Depends(require(Permission.MEMBER_MANAGE)),
    caller: CallerContext = Depends(get_caller),
    svc: OrganizationService = Depends(get_organization_service),
) -> list[MemberOut]:
    members = svc.list_members(caller.principal, caller.organization_id)
    return [MemberOut.from_domain(m) for m in members]


@router.post("/members", status_code=status.HTTP_201_CREATED, response_model=InviteMemberResponse)
def invite_member(
    body: InviteMemberRequest,
    _scope=Depends(require(Permission.MEMBER_MANAGE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: OrganizationService = Depends(get_organization_service),
) -> InviteMemberResponse:
    member, token = svc.invite_member(
        caller.principal, caller.organization_id, email=body.email, role=body.role
    )
    db.commit()
    return InviteMemberResponse(member=MemberOut.from_domain(member), invite_token=token)


@router.delete("/members/{member_id}", response_model=MemberOut)
def remove_member(
    member_id: str,
    _scope=Depends(require(Permission.MEMBER_MANAGE)),
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
    svc: OrganizationService = Depends(get_organization_service),
) -> MemberOut:
    member = svc.remove_member(caller.principal, caller.organization_id, member_id)
    db.commit()
    return MemberOut.from_domain(member)
