"""Validate assessment responses against their template's questions.

Security-sensitive (so it lives in the domain layer, ADR-0002 + project constraints):
responses become *facts* the deterministic rule engine evaluates (ADR-0003). Without
this, a client could submit response keys that were never asked, with arbitrary types,
and manufacture or suppress findings. We reject any key not in the template and any
value whose type/options don't match the question — closing that hole and making the
"dynamic schemas validated per question type" claim true.

Pure: it takes lightweight :class:`QuestionSpec` values (mapped from the template by the
service) rather than importing the repository layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Number
from typing import Any


@dataclass(frozen=True)
class QuestionSpec:
    key: str
    type: str
    config: dict[str, Any]


class ResponseValidationError(Exception):
    """Raised on an invalid response. Mapped to 422 at the service/API boundary."""


def validate_responses(
    questions: Sequence[QuestionSpec], responses: Sequence[dict[str, Any]]
) -> None:
    allowed = {q.key: q for q in questions}
    for r in responses:
        key = r.get("key")
        if key not in allowed:
            raise ResponseValidationError(f"unknown question key {key!r}")
        value = r.get("value")
        if value is None:
            continue  # partial save / unanswered optional question is allowed
        _check_type(allowed[key], value)


def _options(q: QuestionSpec) -> list[Any] | None:
    opts = q.config.get("options")
    return opts if isinstance(opts, list) and opts else None


def _check_type(q: QuestionSpec, value: Any) -> None:
    t = q.type
    if t in ("text", "long_text"):
        if not isinstance(value, str):
            raise ResponseValidationError(f"{q.key!r} expects text")
    elif t == "number":
        # bool is a subclass of int; exclude it.
        if isinstance(value, bool) or not isinstance(value, Number):
            raise ResponseValidationError(f"{q.key!r} expects a number")
    elif t == "single_select":
        opts = _options(q)
        if opts is not None and value not in opts:
            raise ResponseValidationError(f"{q.key!r} value is not one of the allowed options")
    elif t == "multi_select":
        if not isinstance(value, list):
            raise ResponseValidationError(f"{q.key!r} expects a list of selections")
        opts = _options(q)
        if opts is not None and any(v not in opts for v in value):
            raise ResponseValidationError(f"{q.key!r} contains a value not in the allowed options")
    elif t == "file_upload":
        if not isinstance(value, str):
            raise ResponseValidationError(f"{q.key!r} expects an uploaded document id")
    # Unknown types can't occur — the template validated them on creation.
