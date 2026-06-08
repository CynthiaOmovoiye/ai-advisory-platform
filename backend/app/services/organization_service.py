"""Organization & member management (Module 2).

Create organizations and invite/list/remove members, all authorization-gated and
tenant-scoped (ADR-0006/0007). Invite tokens are stored **hashed**, never raw
(threat-model: spoofing — forged invitation acceptance). The raw token is returned
once to the caller (to be delivered out-of-band); only its hash is persisted.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from app.domain.access import Permission, Principal, authorize
from app.errors import Conflict, NotFound
from app.repositories.base import (
    AuditSink,
    MemberRecord,
    MemberRepository,
    OrganizationRecord,
    OrganizationRepository,
    TenantScope,
)

_VALID_INVITE_ROLES = {"org_user", "consultant"}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class OrganizationService:
    organizations: OrganizationRepository
    members: MemberRepository
    audit: AuditSink

    def create_organization(
        self, principal: Principal, active_org: str, *, name: str, slug: str
    ) -> OrganizationRecord:
        authorize(principal, Permission.ORGANIZATION_CREATE, active_org)
        if self.organizations.slug_exists(slug):
            raise Conflict(f"slug '{slug}' is already taken")
        org = OrganizationRecord(id=str(uuid.uuid4()), name=name, slug=slug)
        self.organizations.create(org)
        # The creator becomes an active member of the new org.
        creator_scope = TenantScope(organization_id=org.id, acting_user_id=principal.user_id)
        self.members.add(
            MemberRecord(
                id=str(uuid.uuid4()),
                organization_id=org.id,
                invited_email=f"{principal.user_id}@self",
                role="consultant",
                status="active",
                user_id=principal.user_id,
            ),
            creator_scope,
            invite_token_hash=None,
            invited_by=principal.user_id,
        )
        self.audit.record(
            actor_user_id=principal.user_id,
            organization_id=org.id,
            action="organization.created",
            entity_id=org.id,
        )
        return org

    def invite_member(
        self, principal: Principal, organization_id: str, *, email: str, role: str
    ) -> tuple[MemberRecord, str]:
        if role not in _VALID_INVITE_ROLES:
            raise Conflict(f"role must be one of {sorted(_VALID_INVITE_ROLES)}")
        authorize(principal, Permission.MEMBER_MANAGE, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        if self.members.email_exists(email, scope):
            raise Conflict(f"{email} is already invited to this organization")

        raw_token = secrets.token_urlsafe(32)
        member = MemberRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            invited_email=email,
            role=role,
            status="invited",
        )
        self.members.add(
            member, scope, invite_token_hash=_hash_token(raw_token), invited_by=principal.user_id
        )
        self.audit.record(
            actor_user_id=principal.user_id,
            organization_id=organization_id,
            action="member.invited",
            entity_id=member.id,
        )
        return member, raw_token

    def list_members(self, principal: Principal, organization_id: str) -> list[MemberRecord]:
        authorize(principal, Permission.MEMBER_MANAGE, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        return self.members.list(scope)

    def remove_member(
        self, principal: Principal, organization_id: str, member_id: str
    ) -> MemberRecord:
        authorize(principal, Permission.MEMBER_MANAGE, organization_id)
        scope = TenantScope(organization_id=organization_id, acting_user_id=principal.user_id)
        if self.members.get(member_id, scope) is None:
            raise NotFound("member not found")  # cross-tenant ids resolve here too
        removed = self.members.set_status(member_id, "removed", scope)
        self.audit.record(
            actor_user_id=principal.user_id,
            organization_id=organization_id,
            action="member.removed",
            entity_id=member_id,
        )
        return removed
