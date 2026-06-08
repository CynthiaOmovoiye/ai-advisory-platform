"""Credential auth endpoints used by the Next.js Auth.js BFF."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CallerContext, get_caller, get_db, get_notifier
from app.infra.config import Settings, get_settings
from app.schemas.auth import (
    ActiveOrganizationRequest,
    AuthProfileOut,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    SigninRequest,
    SigninResponse,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService
from app.services.notification_service import Notifier

router = APIRouter(tags=["Auth"])

# Shown for the password-reset endpoints, which must respond identically whether or not
# the email matched a real account (no enumeration).
_RESET_GENERIC = "If an account exists for that email, a password reset link has been sent."


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
def signup(
    body: SignupRequest,
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
    notifier: Notifier = Depends(get_notifier),
) -> SignupResponse:
    result = AuthService(db, notifier).signup(
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


@router.post("/auth/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    db=Depends(get_db),
    notifier: Notifier = Depends(get_notifier),
) -> MessageResponse:
    AuthService(db, notifier).request_password_reset(body.email)
    db.commit()
    return MessageResponse(message=_RESET_GENERIC)


@router.post("/auth/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db=Depends(get_db)) -> MessageResponse:
    AuthService(db).reset_password(token=body.token, new_password=body.password)
    db.commit()
    return MessageResponse(message="Your password has been reset. Please sign in.")


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
