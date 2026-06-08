"""Tests for the authorization kernel — default-deny RBAC (ADR-0007)."""

import unittest

from app.domain.access import Permission, Principal, Role, authorize, has_permission
from app.errors import Forbidden

ORG_A = "org-a"
ORG_B = "org-b"

org_user_a = Principal(user_id="u1", org_roles={ORG_A: frozenset({Role.ORG_USER})})
consultant = Principal(user_id="c1", global_roles=frozenset({Role.CONSULTANT}))
admin = Principal(user_id="a1", global_roles=frozenset({Role.ADMIN}))


class TestAccess(unittest.TestCase):
    def test_org_user_can_complete_in_their_org(self):
        self.assertTrue(has_permission(org_user_a, Permission.ASSESSMENT_COMPLETE, ORG_A))

    def test_org_user_has_no_permissions_in_other_org(self):
        # Isolation falls out of the same mechanism: no roles in org B ⇒ no permissions.
        self.assertEqual(org_user_a.permissions_in(ORG_B), frozenset())
        with self.assertRaises(Forbidden):
            authorize(org_user_a, Permission.ASSESSMENT_READ, ORG_B)

    def test_default_deny_for_unheld_permission(self):
        # An org_user cannot edit rules anywhere — not granted by their role.
        with self.assertRaises(Forbidden):
            authorize(org_user_a, Permission.RULE_EDIT, ORG_A)

    def test_consultant_is_cross_tenant_but_bounded(self):
        # Cross-tenant read/publish, but NOT rule editing (admin-only).
        self.assertTrue(has_permission(consultant, Permission.REPORT_PUBLISH, ORG_A))
        self.assertTrue(has_permission(consultant, Permission.REPORT_PUBLISH, ORG_B))
        self.assertFalse(has_permission(consultant, Permission.RULE_EDIT, ORG_A))

    def test_admin_holds_everything_everywhere(self):
        for perm in Permission:
            self.assertTrue(has_permission(admin, perm, ORG_A))
            self.assertTrue(has_permission(admin, perm, ORG_B))

    def test_empty_principal_is_denied_everything(self):
        nobody = Principal(user_id="x")
        for perm in Permission:
            with self.assertRaises(Forbidden):
                authorize(nobody, perm, ORG_A)


if __name__ == "__main__":
    unittest.main()
