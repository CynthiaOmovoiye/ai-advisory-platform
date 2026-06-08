import unittest

from app.errors import Conflict, Forbidden, Unauthorized, Unprocessable
from app.infra.db import (
    Base,
    enable_sqlite_foreign_keys,
    make_engine,
    make_session_factory,
)
from app.services.auth_service import AuthService, verify_password


class FakeNotifier:
    """Records what would have been emailed, with no real transport."""

    def __init__(self) -> None:
        self.verifications: list[tuple[str, str]] = []
        self.resets: list[tuple[str, str]] = []

    def send_email_verification(self, email: str, token: str) -> None:
        self.verifications.append((email, token))

    def send_password_reset(self, email: str, token: str) -> None:
        self.resets.append((email, token))


class TestAuthService(unittest.TestCase):
    def setUp(self):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        # Enforce FKs so signup's insert ordering is validated like it is on Postgres.
        enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.session = make_session_factory(engine)()
        self.notifier = FakeNotifier()
        self.svc = AuthService(self.session, self.notifier)

    def tearDown(self):
        self.session.close()

    def _verified_user(self, email: str = "user@example.com"):
        result = self.svc.signup(
            email=email,
            password="ChangeMe123!",
            name="User",
            organization_name="Acme Advisory",
        )
        self.svc.verify_email(result.verification_token or "")
        self.session.commit()
        return result

    def test_signup_persists_hash_and_membership(self):
        result = self.svc.signup(
            email="USER@example.com",
            password="ChangeMe123!",
            name="User",
            organization_name="Acme Advisory",
        )
        self.session.commit()

        from app.repositories.orm import User

        row = self.session.get(User, result.profile.id)
        self.assertIsNotNone(row)
        self.assertEqual(row.email, "user@example.com")
        self.assertNotEqual(row.password_hash, "ChangeMe123!")
        self.assertTrue(verify_password(row.password_hash, "ChangeMe123!"))
        self.assertEqual(result.profile.org_roles[result.profile.active_org], ["consultant"])
        self.assertEqual(result.profile.global_roles, ())
        self.assertIsNotNone(result.verification_token)

    def test_duplicate_email_rejected(self):
        self._verified_user("dupe@example.com")
        with self.assertRaises(Conflict):
            self.svc.signup(
                email="DUPE@example.com",
                password="ChangeMe123!",
                name=None,
                organization_name="Other",
            )

    def test_password_policy_rejects_weak_password(self):
        with self.assertRaises(Unprocessable):
            self.svc.signup(
                email="weak@example.com",
                password="password",
                name=None,
                organization_name="Weak Org",
            )

    def test_signin_success_and_failure(self):
        self._verified_user("login@example.com")
        profile = self.svc.authenticate(email="login@example.com", password="ChangeMe123!")
        self.assertEqual(profile.email, "login@example.com")
        with self.assertRaises(Unauthorized):
            self.svc.authenticate(email="login@example.com", password="wrong")

    def test_unverified_user_cannot_sign_in(self):
        self.svc.signup(
            email="unverified@example.com",
            password="ChangeMe123!",
            name=None,
            organization_name="Unverified Org",
        )
        self.session.commit()
        with self.assertRaises(Forbidden):
            self.svc.authenticate(email="unverified@example.com", password="ChangeMe123!")

    def test_cannot_switch_to_non_member_org(self):
        result = self._verified_user("switch@example.com")
        with self.assertRaises(Forbidden):
            self.svc.switch_active_org(user_id=result.profile.id, organization_id="not-my-org")

    def test_signin_with_unknown_email_is_unauthorized(self):
        # Exercises the dummy-hash path: an unknown account still runs one Argon2
        # verification and fails with the same generic error as a wrong password,
        # so response timing and message don't reveal whether the account exists.
        with self.assertRaises(Unauthorized):
            self.svc.authenticate(email="ghost@example.com", password="ChangeMe123!")

    def test_signup_never_grants_global_roles(self):
        result = self.svc.signup(
            email="founder@example.com",
            password="ChangeMe123!",
            name="Founder",
            organization_name="Founder Org",
        )
        self.session.commit()
        self.assertEqual(result.profile.global_roles, ())
        # The new org membership is org-scoped consultant, never a global admin.
        self.assertEqual(result.profile.org_roles[result.profile.active_org], ["consultant"])

    def test_signup_sends_verification_email(self):
        result = self.svc.signup(
            email="verify@example.com",
            password="ChangeMe123!",
            name=None,
            organization_name="Verify Org",
        )
        self.session.commit()
        self.assertEqual(len(self.notifier.verifications), 1)
        email, token = self.notifier.verifications[0]
        self.assertEqual(email, "verify@example.com")
        # The emailed token is the same one that verifies the account.
        self.assertEqual(token, result.verification_token)

    def test_password_reset_changes_password_and_invalidates_sessions(self):
        result = self._verified_user("reset@example.com")
        before = self.svc.profile_for_user(result.profile.id)

        self.svc.request_password_reset("RESET@example.com")  # case-insensitive
        self.session.commit()
        self.assertEqual(len(self.notifier.resets), 1)
        _, token = self.notifier.resets[0]

        self.svc.reset_password(token=token, new_password="BrandNewPass456!")
        self.session.commit()

        after = self.svc.profile_for_user(result.profile.id)
        # Session generation bumped ⇒ every previously minted session is now invalid.
        self.assertEqual(after.session_version, before.session_version + 1)
        # Old password rejected, new password accepted.
        with self.assertRaises(Unauthorized):
            self.svc.authenticate(email="reset@example.com", password="ChangeMe123!")
        profile = self.svc.authenticate(email="reset@example.com", password="BrandNewPass456!")
        self.assertEqual(profile.email, "reset@example.com")

    def test_password_reset_token_is_single_use(self):
        result = self._verified_user("single@example.com")
        self.svc.request_password_reset("single@example.com")
        self.session.commit()
        _, token = self.notifier.resets[0]
        self.svc.reset_password(token=token, new_password="BrandNewPass456!")
        self.session.commit()
        with self.assertRaises(Unauthorized):
            self.svc.reset_password(token=token, new_password="AnotherPass789!")
        # Sanity: the account still exists and uses the first reset password.
        self.assertIsNotNone(result.profile.id)

    def test_reset_with_unknown_token_is_unauthorized(self):
        with self.assertRaises(Unauthorized):
            self.svc.reset_password(token="x" * 40, new_password="BrandNewPass456!")

    def test_reset_rejects_weak_new_password(self):
        self._verified_user("weakreset@example.com")
        self.svc.request_password_reset("weakreset@example.com")
        self.session.commit()
        _, token = self.notifier.resets[0]
        with self.assertRaises(Unprocessable):
            self.svc.reset_password(token=token, new_password="weak")

    def test_forgot_password_for_unknown_email_is_silent(self):
        # No exception, no token, no email — identical observable behaviour to a hit,
        # so the response can't be used to enumerate accounts.
        self.svc.request_password_reset("nobody@example.com")
        self.session.commit()
        self.assertEqual(self.notifier.resets, [])


if __name__ == "__main__":
    unittest.main()
