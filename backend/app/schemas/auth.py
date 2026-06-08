"""Authentication DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.auth_service import AuthProfile, Membership


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=256)
    name: str | None = Field(default=None, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)


class SigninRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=12, max_length=256)


class MessageResponse(BaseModel):
    message: str


class ActiveOrganizationRequest(BaseModel):
    organization_id: str = Field(min_length=1)


class MembershipOut(BaseModel):
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str

    @classmethod
    def from_domain(cls, m: Membership) -> MembershipOut:
        return cls(
            organization_id=m.organization_id,
            organization_name=m.organization_name,
            organization_slug=m.organization_slug,
            role=m.role,
        )


class AuthProfileOut(BaseModel):
    id: str
    email: str
    name: str | None
    email_verified: bool
    status: str
    active_org: str
    global_roles: list[str]
    org_roles: dict[str, list[str]]
    memberships: list[MembershipOut]
    session_version: int

    @classmethod
    def from_domain(cls, p: AuthProfile) -> AuthProfileOut:
        return cls(
            id=p.id,
            email=p.email,
            name=p.name,
            email_verified=p.email_verified,
            status=p.status,
            active_org=p.active_org,
            global_roles=list(p.global_roles),
            org_roles=p.org_roles,
            memberships=[MembershipOut.from_domain(m) for m in p.memberships],
            session_version=p.session_version,
        )


class SignupResponse(BaseModel):
    user: AuthProfileOut
    verification_token: str | None = None


class SigninResponse(BaseModel):
    user: AuthProfileOut
