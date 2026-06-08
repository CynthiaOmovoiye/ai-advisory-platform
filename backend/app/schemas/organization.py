"""Organization & member DTOs (Module 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.repositories.base import MemberRecord, OrganizationRecord


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{3,40}$")


class OrganizationOut(BaseModel):
    id: str
    name: str
    slug: str

    @classmethod
    def from_domain(cls, o: OrganizationRecord) -> OrganizationOut:
        return cls(id=o.id, name=o.name, slug=o.slug)


class InviteMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: Literal["org_user", "consultant"] = "org_user"


class MemberOut(BaseModel):
    id: str
    invited_email: str
    role: str
    status: str

    @classmethod
    def from_domain(cls, m: MemberRecord) -> MemberOut:
        return cls(id=m.id, invited_email=m.invited_email, role=m.role, status=m.status)


class InviteMemberResponse(BaseModel):
    member: MemberOut
    # Returned once so it can be delivered out-of-band; only its hash is stored.
    invite_token: str
