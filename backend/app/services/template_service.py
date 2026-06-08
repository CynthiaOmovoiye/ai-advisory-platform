"""Assessment-template authoring (Module 3).

Consultants author versioned, reusable assessment definitions (sections + typed
questions). Templates are a **global catalog** (not tenant-owned), so authoring is
gated by TEMPLATE_MANAGE; any authenticated user may list/read published templates to
start an assessment from them. Question ``key``s are the stable identifiers the rule
engine evaluates against (ADR-0003).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.access import Permission, Principal, authorize, has_permission
from app.errors import Conflict, NotFound
from app.repositories.base import (
    QuestionRecord,
    SectionRecord,
    TemplateRecord,
    TemplateRepository,
)

_QUESTION_TYPES = {"text", "long_text", "number", "single_select", "multi_select", "file_upload"}


@dataclass
class TemplateService:
    templates: TemplateRepository

    def create_template(
        self,
        principal: Principal,
        active_org: str,
        *,
        category: str,
        title: str,
        description: str | None,
        sections: list[dict],
    ) -> TemplateRecord:
        authorize(principal, Permission.TEMPLATE_MANAGE, active_org)
        section_records: list[SectionRecord] = []
        for si, sec in enumerate(sections):
            questions: list[QuestionRecord] = []
            for qi, q in enumerate(sec.get("questions", [])):
                if q["type"] not in _QUESTION_TYPES:
                    raise Conflict(f"unknown question type {q['type']!r}")
                questions.append(
                    QuestionRecord(
                        id=str(uuid.uuid4()),
                        key=q["key"],
                        prompt=q["prompt"],
                        type=q["type"],
                        config=q.get("config", {}),
                        order_index=qi,
                    )
                )
            section_records.append(
                SectionRecord(
                    id=str(uuid.uuid4()),
                    title=sec["title"],
                    order_index=si,
                    questions=tuple(questions),
                )
            )
        template = TemplateRecord(
            id=str(uuid.uuid4()),
            category=category,
            title=title,
            description=description,
            version=1,
            status="draft",
            sections=tuple(section_records),
        )
        self.templates.create(template)
        return template

    def list_templates(self, principal: Principal, active_org: str) -> list[TemplateRecord]:
        authorize(principal, Permission.ASSESSMENT_READ, active_org)
        templates = self.templates.list_all()
        # Drafts (and archived) are authoring artifacts — only authors see them; ordinary
        # readers see published templates (the ones they can start an assessment from).
        if has_permission(principal, Permission.TEMPLATE_MANAGE, active_org):
            return templates
        return [t for t in templates if t.status == "published"]

    def get_template(
        self, principal: Principal, active_org: str, template_id: str
    ) -> TemplateRecord:
        authorize(principal, Permission.ASSESSMENT_READ, active_org)
        t = self.templates.get(template_id)
        # Don't reveal a draft's existence to a non-author (404, not 403).
        if t is None or (
            t.status != "published"
            and not has_permission(principal, Permission.TEMPLATE_MANAGE, active_org)
        ):
            raise NotFound("template not found")
        return t

    def publish_template(
        self, principal: Principal, active_org: str, template_id: str
    ) -> TemplateRecord:
        authorize(principal, Permission.TEMPLATE_MANAGE, active_org)
        if self.templates.get(template_id) is None:
            raise NotFound("template not found")
        return self.templates.set_status(template_id, "published")
