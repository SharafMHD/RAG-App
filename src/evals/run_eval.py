import argparse
import json
from pathlib import Path

from evals.metrics import (
    citation_correctness,
    mean,
    mrr,
    page_recall,
    precision_at_k,
    recall_at_k,
    required_term_coverage,
)
from evals.schemas import EvaluationResult, load_golden_dataset, load_predictions


DEFAULT_DATASET = Path(__file__).parent / "golden_dataset" / "pension_law_arabic.jsonl"


def evaluate(dataset_path: str | Path = DEFAULT_DATASET, predictions_path: str | Path | None = None, k: int = 5) -> EvaluationResult:
    dataset = load_golden_dataset(dataset_path)
    result = EvaluationResult(
        dataset_path=str(dataset_path),
        dataset_size=len(dataset),
        predictions_path=str(predictions_path) if predictions_path else None,
    )

    if predictions_path is None:
        result.metrics = {
            "dataset_valid": 1,
            "golden_records": len(dataset),
        }
        return result

    predictions = load_predictions(predictions_path)
    recall_scores = []
    precision_scores = []
    mrr_scores = []
    page_recall_scores = []
    term_coverage_scores = []
    citation_scores = []

    for record in dataset:
        prediction = predictions.get(record.id)
        if prediction is None:
            continue

        expected_chunk_ids = record.expected_source.chunk_ids
        if expected_chunk_ids:
            recall_scores.append(recall_at_k(expected_chunk_ids, prediction.retrieved_chunk_ids, k))
            precision_scores.append(precision_at_k(expected_chunk_ids, prediction.retrieved_chunk_ids, k))
            mrr_scores.append(mrr(expected_chunk_ids, prediction.retrieved_chunk_ids))

        page_recall_scores.append(page_recall(record.expected_source.page_numbers, prediction.retrieved_page_numbers))
        term_coverage_scores.append(required_term_coverage(record.expected_source.required_terms, prediction.retrieved_texts))
        citation_scores.append(citation_correctness(record.expected_source.page_numbers, prediction.citations))

    result.evaluated_predictions = len([record for record in dataset if record.id in predictions])
    result.metrics = {
        f"recall@{k}": mean(recall_scores) if recall_scores else None,
        f"precision@{k}": mean(precision_scores) if precision_scores else None,
        "mrr": mean(mrr_scores) if mrr_scores else None,
        "page_recall": mean(page_recall_scores),
        "required_term_coverage": mean(term_coverage_scores),
        "citation_correctness": mean(citation_scores),
        "missing_predictions": len(dataset) - result.evaluated_predictions,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline RAG evaluation against a golden dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to golden JSONL dataset")
    parser.add_argument("--predictions", default=None, help="Optional JSONL predictions file")
    parser.add_argument("--k", type=int, default=5, help="Top-k cutoff for retrieval metrics")
    args = parser.parse_args()

    result = evaluate(dataset_path=args.dataset, predictions_path=args.predictions, k=args.k)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
