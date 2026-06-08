"""HTML → PDF rendering (Module 8: render with Playwright).

The renderer is an interface so the report service is testable without a browser. The
production :class:`PlaywrightRenderer` drives headless Chromium; :class:`FakeRenderer`
is used in tests. Playwright renders in an **isolated, offline context** — no network
access during render — which is the control against SSRF / data exfiltration from a
malicious link smuggled into report content (threat-model: stored XSS / SSRF).
"""

from __future__ import annotations

from typing import Protocol


class ReportRenderer(Protocol):
    def render_pdf(self, html: str) -> bytes: ...


class FakeRenderer:
    """Deterministic stand-in. Returns a minimal valid PDF header + a content hash so
    tests can assert "a PDF was produced from this html" without a browser."""

    def render_pdf(self, html: str) -> bytes:
        return b"%PDF-1.4\n% fake-render len=" + str(len(html)).encode() + b"\n"


class PlaywrightRenderer:
    """Headless-Chromium renderer. Requires `playwright install chromium`.

    Uses the sync API; intended to run inside a Celery worker (off the request path).
    Routes are blocked so the page cannot fetch anything while rendering.
    """

    def __init__(self, *, print_background: bool = True) -> None:
        self._print_background = print_background

    def render_pdf(self, html: str) -> bytes:  # pragma: no cover - needs browser binary
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                page = browser.new_page()
                # Block ALL network during render — content is untrusted (defense vs SSRF).
                page.route("**/*", lambda route: route.abort())
                page.set_content(html, wait_until="load")
                return page.pdf(print_background=self._print_background, format="A4")
            finally:
                browser.close()
