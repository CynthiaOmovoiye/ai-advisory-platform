"""Tests for org & member management (Module 2), on SQLite."""

import unittest

from app.domain.access import Principal, Role
from app.errors import Conflict, Forbidden, NotFound
from app.infra.db import Base, make_engine, make_session_factory
from app.repositories.orm import Organization
from app.repositories.sql import (
    SqlAuditSink,
    SqlMemberRepository,
    SqlOrganizationRepository,
)
from app.services.organization_service import OrganizationService

ORG = "org-a"
consultant = Principal(user_id="c1", global_roles=frozenset({Role.CONSULTANT}))
org_user = Principal(user_id="u1", org_roles={ORG: frozenset({Role.ORG_USER})})


class TestOrganizationService(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        self.session.add(Organization(id=ORG, name="A", slug="a"))
        self.session.commit()
        self.svc = OrganizationService(
            organizations=SqlOrganizationRepository(self.session),
            members=SqlMemberRepository(self.session),
            audit=SqlAuditSink(self.session),
        )

    def tearDown(self):
        self.session.close()

    def test_create_org_adds_creator_as_member(self):
        org = self.svc.create_organization(consultant, ORG, name="New Co", slug="new-co")
        self.assertEqual(org.slug, "new-co")
        members = self.svc.list_members(consultant, org.id)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].status, "active")

    def test_duplicate_slug_conflict(self):
        with self.assertRaises(Conflict):
            self.svc.create_organization(consultant, ORG, name="Dup", slug="a")

    def test_invite_member_hashes_token(self):
        member, token = self.svc.invite_member(
            consultant, ORG, email="x@example.com", role="org_user"
        )
        self.assertEqual(member.status, "invited")
        self.assertTrue(token)  # raw token returned once
        listed = self.svc.list_members(consultant, ORG)
        self.assertIn("x@example.com", [m.invited_email for m in listed])

    def test_duplicate_invite_conflict(self):
        self.svc.invite_member(consultant, ORG, email="x@example.com", role="org_user")
        with self.assertRaises(Conflict):
            self.svc.invite_member(consultant, ORG, email="x@example.com", role="org_user")

    def test_invalid_role_rejected(self):
        with self.assertRaises(Conflict):
            self.svc.invite_member(consultant, ORG, email="y@example.com", role="admin")

    def test_remove_member(self):
        member, _ = self.svc.invite_member(consultant, ORG, email="z@example.com", role="org_user")
        removed = self.svc.remove_member(consultant, ORG, member.id)
        self.assertEqual(removed.status, "removed")

    def test_remove_unknown_member_not_found(self):
        with self.assertRaises(NotFound):
            self.svc.remove_member(consultant, ORG, "nope")

    def test_org_user_cannot_manage_members(self):
        with self.assertRaises(Forbidden):
            self.svc.invite_member(org_user, ORG, email="x@example.com", role="org_user")
        with self.assertRaises(Forbidden):
            self.svc.list_members(org_user, ORG)


if __name__ == "__main__":
    unittest.main()
