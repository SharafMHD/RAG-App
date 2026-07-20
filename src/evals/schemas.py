from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ExpectedSource(BaseModel):
    page_numbers: list[int] = Field(default_factory=list)
    required_terms: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)

    @field_validator("page_numbers")
    @classmethod
    def page_numbers_must_be_positive(cls, value: list[int]) -> list[int]:
        if any(page < 1 for page in value):
            raise ValueError("page_numbers must be positive")
        return value

    @field_validator("required_terms", "chunk_ids")
    @classmethod
    def values_must_not_be_blank(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(value):
            raise ValueError("list values must not be blank")
        return cleaned


class GoldenRecord(BaseModel):
    id: str = Field(..., min_length=1)
    document: str = Field(..., min_length=1)
    language: Literal["ar", "en", "multilingual"] = "en"
    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    expected_source: ExpectedSource
    tags: list[str] = Field(default_factory=list)

    @field_validator("id", "document", "question", "expected_answer")
    @classmethod
    def required_strings_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def tags_must_not_be_blank(cls, value: list[str]) -> list[str]:
        return [tag.strip() for tag in value if tag and tag.strip()]


class PredictionRecord(BaseModel):
    id: str = Field(..., min_length=1)
    answer: str | None = None
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_page_numbers: list[int] = Field(default_factory=list)
    retrieved_texts: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    dataset_path: str
    dataset_size: int
    predictions_path: str | None = None
    evaluated_predictions: int = 0
    metrics: dict[str, float | int | None] = Field(default_factory=dict)


def load_golden_dataset(path: str | Path) -> list[GoldenRecord]:
    records: list[GoldenRecord] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(GoldenRecord.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"Invalid golden dataset record at line {line_number}: {exc}") from exc
    ids = [record.id for record in records]
    duplicates = sorted({record_id for record_id in ids if ids.count(record_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate golden dataset ids: {', '.join(duplicates)}")
    return records


def load_predictions(path: str | Path) -> dict[str, PredictionRecord]:
    predictions: dict[str, PredictionRecord] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            prediction = PredictionRecord.model_validate_json(line)
        except Exception as exc:
            raise ValueError(f"Invalid prediction record at line {line_number}: {exc}") from exc
        if prediction.id in predictions:
            raise ValueError(f"Duplicate prediction id: {prediction.id}")
        predictions[prediction.id] = prediction
    return predictions
