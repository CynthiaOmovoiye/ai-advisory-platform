"""Credential auth endpoints used by the Next.js Auth.js BFF."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CallerContext, get_caller, get_db
from app.infra.config import Settings, get_settings
from app.schemas.auth import (
    ActiveOrganizationRequest,
    AuthProfileOut,
    SigninRequest,
    SigninResponse,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["Auth"])


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
def signup(
    body: SignupRequest,
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SignupResponse:
    result = AuthService(db).signup(
        email=body.email,
        password=body.password,
        name=body.name,
        organization_name=body.organization_name,
    )
    db.commit()
    return SignupResponse(
        user=AuthProfileOut.from_domain(result.profile),
        verification_token=result.verification_token
        if settings.local_email_verification_tokens
        else None,
    )


@router.post("/auth/verify-email", response_model=AuthProfileOut)
def verify_email(body: VerifyEmailRequest, db=Depends(get_db)) -> AuthProfileOut:
    profile = AuthService(db).verify_email(body.token)
    db.commit()
    return AuthProfileOut.from_domain(profile)


@router.post("/auth/signin", response_model=SigninResponse)
def signin(body: SigninRequest, db=Depends(get_db)) -> SigninResponse:
    profile = AuthService(db).authenticate(email=body.email, password=body.password)
    db.commit()
    return SigninResponse(user=AuthProfileOut.from_domain(profile))


@router.get("/auth/me", response_model=AuthProfileOut)
def me(caller: CallerContext = Depends(get_caller), db=Depends(get_db)) -> AuthProfileOut:
    profile = AuthService(db).profile_for_user(caller.principal.user_id, caller.organization_id)
    return AuthProfileOut.from_domain(profile)


@router.patch("/auth/active-organization", response_model=AuthProfileOut)
def active_organization(
    body: ActiveOrganizationRequest,
    caller: CallerContext = Depends(get_caller),
    db=Depends(get_db),
) -> AuthProfileOut:
    profile = AuthService(db).switch_active_org(
        user_id=caller.principal.user_id,
        organization_id=body.organization_id,
    )
    return AuthProfileOut.from_domain(profile)
