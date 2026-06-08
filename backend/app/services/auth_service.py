"""Credential authentication and account onboarding.

Auth.js owns browser sessions, but credentials are verified here against persisted
users and memberships. Passwords are Argon2 hashes; plaintext passwords never leave
this service boundary except as the one input being verified.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import Conflict, Forbidden, Unauthorized, Unprocessable
from app.infra.db import set_rls_bypass, set_tenant_scope
from app.repositories.orm import EmailVerificationToken, Organization, OrganizationMember, User

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_ROLES = {"admin", "consultant", "org_user"}
_hasher = PasswordHasher()
# Verified when no user matches so login response time doesn't reveal whether an account
# exists (timing-based user enumeration). Computed once at import.
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")


@dataclass(frozen=True)
class Membership:
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str


@dataclass(frozen=True)
class AuthProfile:
    id: str
    email: str
    name: str | None
    email_verified: bool
    status: str
    active_org: str
    global_roles: tuple[str, ...]
    memberships: tuple[Membership, ...]

    @property
    def org_roles(self) -> dict[str, list[str]]:
        roles: dict[str, list[str]] = {}
        for membership in self.memberships:
            roles.setdefault(membership.organization_id, []).append(membership.role)
        return roles


@dataclass(frozen=True)
class SignupResult:
    profile: AuthProfile
    verification_token: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:40].strip("-") or "organization"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError):
        return False


def validate_password(password: str) -> None:
    if len(password) < 12:
        raise Unprocessable("password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        raise Unprocessable("password must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise Unprocessable("password must include a lowercase letter")
    if not re.search(r"\d", password):
        raise Unprocessable("password must include a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise Unprocessable("password must include a symbol")


class AuthService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def signup(
        self, *, email: str, password: str, name: str | None, organization_name: str
    ) -> SignupResult:
        email = _normalize_email(email)
        if not _EMAIL_RE.match(email):
            raise Unprocessable("email is invalid")
        validate_password(password)
        if self._s.execute(select(User.id).where(User.email == email)).first() is not None:
            raise Conflict("an account with that email already exists")

        user_id = str(uuid.uuid4())
        org_id = str(uuid.uuid4())
        org_slug = self._unique_slug(_slugify(organization_name))
        user = User(
            id=user_id,
            email=email,
            password_hash=hash_password(password),
            name=name.strip() or None if name else None,
            status="active",
        )
        org = Organization(id=org_id, name=organization_name.strip(), slug=org_slug)
        member = OrganizationMember(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            user_id=user_id,
            invited_email=email,
            role="consultant",
            status="active",
            invited_by=user_id,
        )
        # Persist the FK parents (user, org) first. A single flush of the whole graph
        # can emit the dependent inserts (membership, verification token, audit row)
        # before the user/org rows and trip Postgres FK constraints; SQLite tests don't
        # enforce FKs by default, so this only surfaces against Postgres.
        self._s.add_all([user, org])
        try:
            self._s.flush()
        except IntegrityError as exc:
            raise Conflict("an account with that email already exists") from exc
        # The membership row is RLS-protected (FORCE policy). Signup has no session/org
        # context yet, so scope this transaction to the just-created org to satisfy the
        # policy's WITH CHECK. Transaction-local; cleared at commit.
        set_tenant_scope(self._s, org_id)
        token = secrets.token_urlsafe(32)
        self._s.add_all(
            [
                member,
                EmailVerificationToken(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    token_hash=_hash_token(token),
                    expires_at=_now() + timedelta(hours=24),
                ),
            ]
        )
        self._audit(user_id, org_id, "auth.signup", user_id)
        try:
            self._s.flush()
        except IntegrityError as exc:
            raise Conflict("account or organization already exists") from exc
        return SignupResult(
            profile=self.profile_for_user(user_id, active_org=org_id),
            verification_token=token,
        )

    def verify_email(self, token: str) -> AuthProfile:
        row = self._s.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == _hash_token(token)
            )
        ).scalar_one_or_none()
        if row is None or row.used_at is not None or _as_utc(row.expires_at) < _now():
            raise Unauthorized("invalid verification token")
        user = self._s.get(User, row.user_id)
        if user is None:
            raise Unauthorized("invalid verification token")
        user.email_verified_at = _now()
        row.used_at = _now()
        self._audit(user.id, None, "auth.email_verified", user.id)
        self._s.flush()
        return self.profile_for_user(user.id)

    def authenticate(self, *, email: str, password: str) -> AuthProfile:
        user = self._s.execute(
            select(User).where(User.email == _normalize_email(email))
        ).scalar_one_or_none()
        # Always run one Argon2 verification (against a dummy hash when no user matches)
        # so login latency can't be used to enumerate accounts.
        password_ok = verify_password(user.password_hash if user else _DUMMY_HASH, password)
        if user is None or user.status != "active" or not password_ok:
            self._audit(None, None, "auth.signin_failed", None)
            raise Unauthorized("invalid email or password")
        if user.email_verified_at is None:
            self._audit(user.id, None, "auth.signin_unverified", user.id)
            raise Forbidden("email verification required")
        profile = self.profile_for_user(user.id)
        self._audit(user.id, profile.active_org, "auth.signin_success", user.id)
        return profile

    def profile_for_user(self, user_id: str, active_org: str | None = None) -> AuthProfile:
        user = self._s.get(User, user_id)
        if user is None or user.status != "active":
            raise Unauthorized("user is not active")
        memberships = self._memberships(user.id)
        if not memberships:
            raise Forbidden("user has no active organization membership")
        selected_org = active_org or memberships[0].organization_id
        if selected_org not in {m.organization_id for m in memberships}:
            raise Forbidden("user is not a member of that organization")
        return AuthProfile(
            id=user.id,
            email=user.email,
            name=user.name,
            email_verified=user.email_verified_at is not None,
            status=user.status,
            active_org=selected_org,
            global_roles=(),
            memberships=memberships,
        )

    def switch_active_org(self, *, user_id: str, organization_id: str) -> AuthProfile:
        return self.profile_for_user(user_id, active_org=organization_id)

    def _memberships(self, user_id: str) -> tuple[Membership, ...]:
        # Loading a user's own memberships is an identity operation that spans orgs and
        # happens before any single org is scoped (signin, /me, get_caller). The
        # organization_members table is RLS-scoped to one org, so this read must bypass
        # RLS — it stays safe because the query is filtered strictly to this user's rows.
        # Enforcement is restored immediately so the rest of the request transaction
        # (the actual tenant-data queries) remains org-scoped.
        set_rls_bypass(self._s)
        try:
            rows = self._s.execute(
                select(OrganizationMember, Organization)
                .join(Organization, Organization.id == OrganizationMember.organization_id)
                .where(
                    OrganizationMember.user_id == user_id,
                    OrganizationMember.status == "active",
                )
                .order_by(OrganizationMember.created_at)
            ).all()
        finally:
            set_rls_bypass(self._s, on=False)
        memberships: list[Membership] = []
        for member, org in rows:
            if member.role not in _VALID_ROLES:
                raise Forbidden("membership contains unknown role")
            memberships.append(
                Membership(
                    organization_id=org.id,
                    organization_name=org.name,
                    organization_slug=org.slug,
                    role=member.role,
                )
            )
        return tuple(memberships)

    def _unique_slug(self, base: str) -> str:
        candidate = base
        i = 2
        while self._s.execute(
            select(Organization.id).where(Organization.slug == candidate)
        ).first():
            suffix = f"-{i}"
            candidate = f"{base[: 40 - len(suffix)]}{suffix}"
            i += 1
        return candidate

    def _audit(
        self,
        actor_user_id: str | None,
        organization_id: str | None,
        action: str,
        entity_id: str | None,
    ) -> None:
        from app.repositories.orm import AuditLogRow

        self._s.add(
            AuditLogRow(
                id=str(uuid.uuid4()),
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                action=action,
                entity_id=entity_id,
            )
        )
