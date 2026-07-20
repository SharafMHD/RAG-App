import json
from pathlib import Path

import pytest

from evals.metrics import (
    citation_correctness,
    mrr,
    page_recall,
    precision_at_k,
    recall_at_k,
    required_term_coverage,
)
from evals.run_eval import evaluate
from evals.schemas import load_golden_dataset


DATASET_PATH = Path(__file__).parents[1] / "evals" / "golden_dataset" / "pension_law_arabic.jsonl"


def test_retrieval_metrics_handle_order_and_k():
    expected = ["a", "c"]
    retrieved = ["b", "c", "a"]

    assert recall_at_k(expected, retrieved, k=2) == 0.5
    assert precision_at_k(expected, retrieved, k=2) == 0.5
    assert mrr(expected, retrieved) == 0.5


def test_retrieval_metrics_handle_empty_expected():
    assert recall_at_k([], ["a"], k=1) == 0.0
    assert mrr([], ["a"]) == 0.0
    with pytest.raises(ValueError):
        precision_at_k(["a"], ["a"], k=0)


def test_source_grounding_metrics_for_pages_terms_and_citations():
    assert page_recall([11, 12], [12]) == 0.5
    assert required_term_coverage(["المؤمن عليه", "كل شخص"], ["المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون"]) == 1.0
    assert citation_correctness([11], [{"page_number": 11}]) == 1.0


def test_pension_law_arabic_dataset_is_valid_and_contains_user_question():
    records = load_golden_dataset(DATASET_PATH)

    assert len(records) == 20
    assert any(record.question == "من هو المؤمن عليه؟" for record in records)
    user_record = next(record for record in records if record.question == "من هو المؤمن عليه؟")
    assert user_record.expected_answer == "المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون."
    assert user_record.expected_source.page_numbers == [11]


def test_eval_runner_validates_dataset_without_predictions():
    result = evaluate(DATASET_PATH)

    assert result.dataset_size == 20
    assert result.metrics["dataset_valid"] == 1


def test_eval_runner_scores_prediction_file(tmp_path):
    predictions_path = tmp_path / "predictions.jsonl"
    prediction = {
        "id": "pension_ar_004",
        "answer": "المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون.",
        "retrieved_page_numbers": [11],
        "retrieved_texts": ["المؤمن عليه: كل شخص تسري عليه أحكام هذا القانون"],
        "citations": [{"page_number": 11}],
    }
    predictions_path.write_text(json.dumps(prediction, ensure_ascii=False) + "\n", encoding="utf-8")

    result = evaluate(DATASET_PATH, predictions_path=predictions_path)

    assert result.evaluated_predictions == 1
    assert result.metrics["page_recall"] == 1.0
    assert result.metrics["citation_correctness"] == 1.0
    assert result.metrics["missing_predictions"] == 19
