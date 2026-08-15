from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


SOURCE_ID_PATTERN = re.compile(r"\[?(source_\d+)\]?")
ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF]")


class GeneratedAnswer(BaseModel):
    answer: str = Field(..., min_length=1)
    cited_source_ids: list[str] = Field(default_factory=list)
    is_answered: bool = True
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("answer must not be blank")
        return value


def no_answer_text(query_text: str) -> str:
    if ARABIC_PATTERN.search(query_text or ""):
        return "لا أملك معلومات كافية في المصادر المتاحة للإجابة على هذا السؤال."
    return "I do not have enough information in the available sources to answer this question."


def extract_source_ids(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in SOURCE_ID_PATTERN.findall(text or ""):
        if match not in seen:
            seen.add(match)
            ordered.append(match)
    return ordered


def parse_generated_answer(raw_answer: str | dict[str, Any] | GeneratedAnswer, *, query_text: str) -> GeneratedAnswer:
    if isinstance(raw_answer, GeneratedAnswer):
        return raw_answer
    if isinstance(raw_answer, dict):
        return GeneratedAnswer.model_validate(raw_answer)

    text = (raw_answer or "").strip()
    if not text:
        return GeneratedAnswer(answer=no_answer_text(query_text), cited_source_ids=[], is_answered=False, confidence=0.0)

    parsed: Any = None
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, dict):
        return GeneratedAnswer.model_validate(parsed)

    return GeneratedAnswer(
        answer=text,
        cited_source_ids=extract_source_ids(text),
        is_answered=True,
        confidence=None,
    )


def validate_generated_answer(
    raw_answer: str | dict[str, Any] | GeneratedAnswer,
    *,
    available_source_ids: list[str],
    query_text: str,
    require_citations: bool = True,
    strict_citation_validation: bool = True,
) -> GeneratedAnswer:
    if not available_source_ids:
        return GeneratedAnswer(answer=no_answer_text(query_text), cited_source_ids=[], is_answered=False, confidence=0.0)

    generated = parse_generated_answer(raw_answer, query_text=query_text)
    available = set(available_source_ids)
    cited = generated.cited_source_ids or extract_source_ids(generated.answer)
    invalid = [source_id for source_id in cited if source_id not in available]

    if invalid and strict_citation_validation:
        return GeneratedAnswer(answer=no_answer_text(query_text), cited_source_ids=[], is_answered=False, confidence=0.0)

    cited = [source_id for source_id in cited if source_id in available]
    answer = generated.answer
    if generated.is_answered and require_citations and not cited:
        return GeneratedAnswer(answer=no_answer_text(query_text), cited_source_ids=[], is_answered=False, confidence=0.0)

    return GeneratedAnswer(
        answer=answer,
        cited_source_ids=cited,
        is_answered=generated.is_answered,
        confidence=generated.confidence,
    )
