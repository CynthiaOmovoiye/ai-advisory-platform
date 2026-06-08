"""Email delivery (infra layer).

A tiny transport abstraction with three implementations:

* ``ConsoleEmailProvider`` — logs the message; the safe default that needs no creds
  (local dev pairs it with ``local_email_verification_tokens``).
* ``SmtpEmailProvider`` — sends via any SMTP server. Mailtrap (sandbox or production
  sending) works here directly with its host/port/username/password.
* ``ResendEmailProvider`` — sends via the Resend HTTP API.

The "what to send" (subjects, link templates) lives one layer up in the notification
service; this module only knows how to put a message on the wire. Send failures raise
``EmailDeliveryError`` so callers can decide whether to swallow (best-effort
verification email) or stay generic (password reset).
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import httpx

from app.infra.config import Settings

logger = logging.getLogger("app.email")


class EmailDeliveryError(RuntimeError):
    """Raised when a provider fails to hand the message to its transport."""


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str


class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailProvider:
    """Logs the email instead of sending it. Used in local dev / tests."""

    def __init__(self, sender: str) -> None:
        self._sender = sender

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "email (console) from=%s to=%s subject=%s\n%s",
            self._sender,
            message.to,
            message.subject,
            message.text,
        )


class SmtpEmailProvider:
    """Sends via SMTP (Mailtrap and most providers). Synchronous — the auth endpoints
    are sync and a single transactional email is fast; callers bound failures."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        starttls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._starttls = starttls

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
                if self._starttls:
                    smtp.starttls()
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(mime)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError(f"SMTP send failed: {exc}") from exc


class ResendEmailProvider:
    """Sends via the Resend HTTP API (https://resend.com/docs)."""

    _URL = "https://api.resend.com/emails"

    def __init__(self, *, api_key: str, sender: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._sender = sender
        self._timeout = timeout

    def send(self, message: EmailMessage) -> None:
        try:
            resp = httpx.post(
                self._URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._sender,
                    "to": [message.to],
                    "subject": message.subject,
                    "html": message.html,
                    "text": message.text,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(f"Resend request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise EmailDeliveryError(f"Resend returned {resp.status_code}: {resp.text[:200]}")


def build_email_provider(settings: Settings) -> EmailProvider:
    """Pick the transport from configuration. Unknown/misconfigured values fall back to
    the console provider so a missing credential degrades to "logged", never to a crash
    that blocks signup."""
    provider = settings.email_provider.strip().lower()
    if provider == "smtp" and settings.smtp_host:
        return SmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            sender=settings.email_from,
            starttls=settings.smtp_starttls,
        )
    if provider == "resend" and settings.resend_api_key:
        return ResendEmailProvider(api_key=settings.resend_api_key, sender=settings.email_from)
    if provider not in ("console", "smtp", "resend"):
        logger.warning(
            "unknown EMAIL_PROVIDER=%r; falling back to console", settings.email_provider
        )
    elif provider != "console":
        logger.warning(
            "EMAIL_PROVIDER=%s is missing credentials; falling back to console", provider
        )
    return ConsoleEmailProvider(sender=settings.email_from)
