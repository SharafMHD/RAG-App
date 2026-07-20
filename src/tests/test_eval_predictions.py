import json

from evals.compare_runs import compare_runs
from evals.schemas import PredictionRecord


def test_prediction_record_accepts_sprint2_shape():
    prediction = PredictionRecord(
        id="q1",
        answer=None,
        retrieved_chunk_ids=["chunk-1"],
        retrieved_page_numbers=[3],
        retrieved_texts=["النص"],
        citations=[{"chunk_id": "chunk-1", "page_number": 3, "score": 0.9}],
    )

    assert prediction.retrieved_chunk_ids == ["chunk-1"]
    assert prediction.citations[0]["page_number"] == 3


def test_compare_runs_writes_markdown_report(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    report = tmp_path / "report.md"

    dataset.write_text(json.dumps({
        "id": "q1",
        "document": "doc.pdf",
        "language": "ar",
        "question": "ما هو النص؟",
        "expected_answer": "النص",
        "expected_source": {"page_numbers": [3], "required_terms": ["النص"], "chunk_ids": ["chunk-1"]},
        "tags": [],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    predictions.write_text(json.dumps({
        "id": "q1",
        "answer": None,
        "retrieved_chunk_ids": ["chunk-1"],
        "retrieved_page_numbers": [3],
        "retrieved_texts": ["النص"],
        "citations": [{"page_number": 3}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    results = compare_runs(dataset_path=dataset, runs=[f"vector={predictions}"], k=5, output=report)

    assert results["vector"]["metrics"]["recall@5"] == 1.0
    assert "Sprint 2 Retrieval Quality Report" in report.read_text(encoding="utf-8")
