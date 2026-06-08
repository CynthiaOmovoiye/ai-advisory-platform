"""Assessment-template & dynamic-question DTOs (Module 3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.repositories.base import AssessmentRecord, TemplateRecord

QuestionType = Literal[
    "text", "long_text", "number", "single_select", "multi_select", "file_upload"
]
Category = Literal[
    "ai_readiness",
    "data_maturity",
    "security",
    "governance",
    "compliance",
    "operations",
    "infrastructure",
]


class QuestionIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,60}$")
    prompt: str = Field(min_length=1)
    type: QuestionType
    config: dict[str, Any] = Field(default_factory=dict)


class SectionIn(BaseModel):
    title: str = Field(min_length=1)
    questions: list[QuestionIn] = Field(default_factory=list)


class CreateTemplateRequest(BaseModel):
    category: Category
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    sections: list[SectionIn] = Field(default_factory=list)


class QuestionOut(BaseModel):
    id: str
    key: str
    prompt: str
    type: str
    config: dict[str, Any]


class SectionOut(BaseModel):
    id: str
    title: str
    questions: list[QuestionOut]


class TemplateOut(BaseModel):
    id: str
    category: str
    title: str
    description: str | None
    version: int
    status: str
    sections: list[SectionOut]

    @classmethod
    def from_domain(cls, t: TemplateRecord) -> TemplateOut:
        return cls(
            id=t.id,
            category=t.category,
            title=t.title,
            description=t.description,
            version=t.version,
            status=t.status,
            sections=[
                SectionOut(
                    id=s.id,
                    title=s.title,
                    questions=[
                        QuestionOut(
                            id=q.id, key=q.key, prompt=q.prompt, type=q.type, config=q.config
                        )
                        for q in s.questions
                    ],
                )
                for s in t.sections
            ],
        )


class CreateAssessmentRequest(BaseModel):
    template_id: str


class ResponseInput(BaseModel):
    key: str
    value: Any


class SaveResponsesRequest(BaseModel):
    responses: list[ResponseInput]


class AssessmentOut(BaseModel):
    id: str
    template_id: str | None
    template_name: str
    status: str

    @classmethod
    def from_domain(cls, a: AssessmentRecord) -> AssessmentOut:
        return cls(
            id=a.id, template_id=a.template_id, template_name=a.template_name, status=a.status
        )
