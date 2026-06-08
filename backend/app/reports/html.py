"""HTML rendering for reports — pure, and security-conscious.

Report content includes recommendation text that originated from rules, consultant
edits, AND the LLM. All of it is treated as **untrusted data** and HTML-escaped before
rendering (threat-model: stored XSS via LLM/user text → PDF). We build the HTML by
escaping every dynamic value — no template engine that could be tricked into executing
content, and a strict inline stylesheet only.
"""

from __future__ import annotations

from html import escape

from .model import ReportModel, ReportSection

_STYLE = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: #1a1a1a; margin: 40px; }
h1 { font-size: 26px; } h2 { font-size: 19px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
.headline { font-size: 15px; color: #333; }
.counts span { display: inline-block; margin-right: 14px; font-weight: 600; }
.critical { color: #b00020; } .high { color: #d9480f; } .medium { color: #b8860b; }
.low { color: #2b6cb0; } .info { color: #555; }
.rec { margin: 14px 0; padding: 12px 14px; border-left: 4px solid #ccc; background: #fafafa; }
.rec .sev { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
.rec h3 { margin: 4px 0; font-size: 15px; }
.rec p { margin: 4px 0; font-size: 13px; }
.label { color: #666; font-weight: 600; }
"""


def _rec_html(rec) -> str:
    sev = rec.severity.name.lower()
    return (
        f'<div class="rec" style="border-left-color: var(--{sev})">'
        f'<div class="sev {sev}">{escape(sev)} · {escape(rec.rule_code)}</div>'
        f"<h3>{escape(rec.title)}</h3>"
        f'<p><span class="label">Finding:</span> {escape(rec.finding)}</p>'
        f'<p><span class="label">Rationale:</span> {escape(rec.rationale)}</p>'
        f'<p><span class="label">Remediation:</span> {escape(rec.remediation)}</p>'
        f"</div>"
    )


def _section_html(section: ReportSection) -> str:
    body = "".join(_rec_html(r) for r in section.recommendations)
    return f"<section><h2>{escape(section.title)}</h2>{body}</section>"


def render_report_html(model: ReportModel) -> str:
    counts = "".join(
        f'<span class="{sev}">{escape(sev.title())}: {n}</span>'
        for sev, n in model.severity_counts.items()
        if n
    )
    sections = "".join(_section_html(s) for s in model.sections)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_STYLE}</style></head><body>"
        f"<h1>AI Readiness Report</h1>"
        f"<p class='headline'><strong>{escape(model.organization_name)}</strong> — "
        f"{escape(model.assessment_title)}</p>"
        "<section><h2>Executive Summary</h2>"
        f"<p class='headline'>{escape(model.headline)}</p>"
        f"<p class='counts'>{counts}</p></section>"
        f"{sections}"
        "</body></html>"
    )
