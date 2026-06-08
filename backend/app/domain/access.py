"""Authorization kernel: default-deny RBAC composed with tenant scope.

This is the executable form of ADR-0007 (managed auth, but RBAC is ours and
default-deny) and one half of ADR-0006 (tenant isolation). It is pure domain logic —
no I/O, no framework — so the security model is unit-testable in isolation.

Two ideas do all the work:

1. **A principal's permissions are computed per organization.** Effective roles for an
   org = the principal's global roles (admin / cross-tenant consultant) ∪ the roles
   they hold *in that org*. An ``org_user`` of org A has **no roles at all** in org B,
   so they get **no permissions** there — tenant isolation falls out of the same
   mechanism that does authorization, for free.

2. **Default deny.** A permission is granted only if some effective role explicitly
   grants it. Absence of a grant is a denial, raised as :class:`Forbidden`.

The API layer enforces this via an injected guard on every route; a route with no
declared permission is forbidden by construction (and a CI test asserts every route
declares one).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from app.errors import Forbidden


class Role(str, Enum):
    ADMIN = "admin"
    CONSULTANT = "consultant"
    ORG_USER = "org_user"


class Permission(str, Enum):
    ASSESSMENT_READ = "assessment:read"
    ASSESSMENT_COMPLETE = "assessment:complete"
    RECOMMENDATION_EDIT = "recommendation:edit"
    RECOMMENDATION_APPROVE = "recommendation:approve"
    REPORT_PUBLISH = "report:publish"
    RULE_READ = "rule:read"
    RULE_EDIT = "rule:edit"
    ADMIN_METRICS = "admin:metrics"
    ORGANIZATION_CREATE = "organization:create"
    MEMBER_MANAGE = "member:manage"
    TEMPLATE_MANAGE = "template:manage"


# Role → granted permissions. The single source of truth for "who may do what".
# Mirrors the role_permissions table in db/schema.sql.
_POLICY: Mapping[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),  # admin holds every permission
    Role.CONSULTANT: frozenset(
        {
            Permission.ASSESSMENT_READ,
            Permission.ASSESSMENT_COMPLETE,
            Permission.RECOMMENDATION_EDIT,
            Permission.RECOMMENDATION_APPROVE,
            Permission.REPORT_PUBLISH,
            Permission.RULE_READ,
            Permission.ORGANIZATION_CREATE,
            Permission.MEMBER_MANAGE,
            Permission.TEMPLATE_MANAGE,
        }
    ),
    Role.ORG_USER: frozenset(
        {
            Permission.ASSESSMENT_READ,
            Permission.ASSESSMENT_COMPLETE,
        }
    ),
}


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Built by the auth layer from the verified session —
    NEVER from request input (ADR-0006/0007)."""

    user_id: str
    # Cross-tenant roles not bound to a single org (admin; a consultant operating
    # across tenants). An audited *widening* of scope, not an absence of scope.
    global_roles: frozenset[Role] = field(default_factory=frozenset)
    # Roles held within a specific org (the org_user case, and org-scoped consultants).
    org_roles: Mapping[str, frozenset[Role]] = field(default_factory=dict)

    def effective_roles(self, organization_id: str) -> frozenset[Role]:
        return self.global_roles | self.org_roles.get(organization_id, frozenset())

    def permissions_in(self, organization_id: str) -> frozenset[Permission]:
        perms: set[Permission] = set()
        for role in self.effective_roles(organization_id):
            perms |= _POLICY.get(role, frozenset())
        return frozenset(perms)


def has_permission(principal: Principal, permission: Permission, organization_id: str) -> bool:
    return permission in principal.permissions_in(organization_id)


def authorize(principal: Principal, permission: Permission, organization_id: str) -> None:
    """Default-deny guard. Raises :class:`Forbidden` unless the principal explicitly
    holds ``permission`` in ``organization_id``. This is the call every service makes
    before doing anything tenant-scoped."""
    if not has_permission(principal, permission, organization_id):
        raise Forbidden(f"{permission.value} not permitted")
