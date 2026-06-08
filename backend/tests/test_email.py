import unittest
from unittest.mock import MagicMock, patch

from app.infra.config import Settings
from app.infra.email import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    EmailMessage,
    ResendEmailProvider,
    build_email_provider,
)

_MSG = EmailMessage(to="user@example.com", subject="Hi", html="<p>hi</p>", text="hi")


class TestEmailProviderSelection(unittest.TestCase):
    def test_console_is_default_and_needs_no_creds(self):
        provider = build_email_provider(Settings(email_provider="console"))
        self.assertIsInstance(provider, ConsoleEmailProvider)

    def test_missing_credentials_falls_back_to_console(self):
        # Asked for resend but no key ⇒ degrade to console rather than crash signup.
        provider = build_email_provider(Settings(email_provider="resend", resend_api_key=""))
        self.assertIsInstance(provider, ConsoleEmailProvider)

    def test_resend_selected_when_key_present(self):
        provider = build_email_provider(Settings(email_provider="resend", resend_api_key="re_test"))
        self.assertIsInstance(provider, ResendEmailProvider)


class TestResendProvider(unittest.TestCase):
    def test_posts_to_resend_api_with_auth_and_payload(self):
        provider = ResendEmailProvider(api_key="re_test", sender="from@example.com")
        with patch("app.infra.email.httpx.post") as post:
            post.return_value = MagicMock(status_code=200, text="{}")
            provider.send(_MSG)
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")
        self.assertEqual(kwargs["json"]["to"], ["user@example.com"])
        self.assertEqual(kwargs["json"]["from"], "from@example.com")

    def test_api_error_raises_delivery_error(self):
        provider = ResendEmailProvider(api_key="re_test", sender="from@example.com")
        with patch("app.infra.email.httpx.post") as post:
            post.return_value = MagicMock(status_code=422, text="bad")
            with self.assertRaises(EmailDeliveryError):
                provider.send(_MSG)


if __name__ == "__main__":
    unittest.main()
