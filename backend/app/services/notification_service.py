"""Transactional notifications (service layer).

Builds the verification and password-reset emails (subjects, links, bodies) and hands
them to an :class:`EmailProvider`. Delivery is best-effort: a transport failure is
logged but never propagated, so a flaky mail provider can't break signup or leak
(via differing behaviour) whether an account exists during password reset.

The :class:`Notifier` protocol is what the auth service depends on, so tests can inject
a fake that records sends without any real transport.
"""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import quote

from app.infra.config import Settings
from app.infra.email import EmailDeliveryError, EmailMessage, EmailProvider

logger = logging.getLogger("app.notifications")


class Notifier(Protocol):
    def send_email_verification(self, email: str, token: str) -> None: ...
    def send_password_reset(self, email: str, token: str) -> None: ...


class NotificationService:
    def __init__(self, provider: EmailProvider, settings: Settings) -> None:
        self._provider = provider
        self._base = settings.app_base_url.rstrip("/")
        self._reset_minutes = settings.password_reset_ttl_minutes
        self._verify_hours = settings.email_verification_ttl_hours

    def send_email_verification(self, email: str, token: str) -> None:
        link = f"{self._base}/verify-email?token={quote(token)}"
        self._send(
            email,
            subject="Verify your email",
            heading="Confirm your email address",
            body=(
                "Welcome to the AI Advisory Platform. Confirm your email to activate "
                f"your account. This link expires in {self._verify_hours} hours."
            ),
            cta_label="Verify email",
            link=link,
        )

    def send_password_reset(self, email: str, token: str) -> None:
        link = f"{self._base}/reset-password?token={quote(token)}"
        self._send(
            email,
            subject="Reset your password",
            heading="Reset your password",
            body=(
                "We received a request to reset your password. If this was you, choose a "
                f"new password using the link below. It expires in {self._reset_minutes} "
                "minutes. If you didn't request this, you can safely ignore this email."
            ),
            cta_label="Reset password",
            link=link,
        )

    def _send(
        self, to: str, *, subject: str, heading: str, body: str, cta_label: str, link: str
    ) -> None:
        text = f"{heading}\n\n{body}\n\n{cta_label}: {link}\n"
        html = (
            f'<div style="font-family:system-ui,sans-serif;max-width:480px">'
            f"<h2>{heading}</h2><p>{body}</p>"
            f'<p><a href="{link}" '
            f'style="display:inline-block;padding:10px 16px;background:#111;color:#fff;'
            f'border-radius:6px;text-decoration:none">{cta_label}</a></p>'
            f'<p style="color:#666;font-size:13px">Or paste this link into your browser:<br>'
            f'<a href="{link}">{link}</a></p></div>'
        )
        try:
            self._provider.send(EmailMessage(to=to, subject=subject, html=html, text=text))
        except EmailDeliveryError:
            # Best-effort: never let a mail failure break the auth flow or change its
            # observable behaviour. The user can re-request the email.
            logger.exception("failed to deliver %r email to %s", subject, to)
