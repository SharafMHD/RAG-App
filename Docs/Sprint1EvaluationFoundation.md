# Sprint 1 — Evaluation Foundation

## Goal

Create a measurable RAG evaluation baseline before changing retrieval, prompting, reranking, or chunking behavior.

## Dataset

Golden dataset created from:

```text
Docs/Pension law arabic.pdf
```

Dataset file:

```text
src/evals/golden_dataset/pension_law_arabic.jsonl
```

The dataset currently contains **20 Arabic golden questions**, including:

```text
من هو المؤمن عليه؟
```

Expected answer:

```text
المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون.
```

Source grounding:

```json
{
  "page_numbers": [11],
  "required_terms": ["المؤمن عليه", "كل شخص", "تسري عليه أحكام هذا القانون"]
}
```

## Golden record format

Each dataset line is JSONL:

```json
{
  "id": "pension_ar_004",
  "document": "Pension law arabic.pdf",
  "language": "ar",
  "question": "من هو المؤمن عليه؟",
  "expected_answer": "المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون.",
  "expected_source": {
    "page_numbers": [11],
    "required_terms": ["المؤمن عليه", "كل شخص", "تسري عليه أحكام هذا القانون"],
    "chunk_ids": []
  },
  "tags": ["arabic", "pension-law", "definition", "user-requested"]
}
```

## Evaluation code

Added evaluation package:

```text
src/evals/
├── __init__.py
├── README.md
├── metrics.py
├── run_eval.py
├── schemas.py
└── golden_dataset/
    └── pension_law_arabic.jsonl
```

## Metrics implemented

Retrieval metrics:

- `recall@k`
- `precision@k`
- `MRR`

Source/answer grounding checks:

- page recall
- required-term coverage
- citation correctness

## Commands

Validate the golden dataset:

```bash
cd src
PYTHONPATH=. uv run python -m evals.run_eval
```

Run all tests:

```bash
cd src
PYTHONPATH=. uv run pytest -q
```

Run only evaluation tests:

```bash
cd src
PYTHONPATH=. uv run pytest tests/test_eval_foundation.py -q
```

Score a future predictions file:

```bash
cd src
PYTHONPATH=. uv run python -m evals.run_eval \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --predictions path/to/predictions.jsonl \
  --k 5
```

## Test coverage

Added:

```text
src/tests/test_eval_foundation.py
```

Covers:

- metric correctness
- empty expected/retrieved edge cases
- Arabic source grounding checks
- dataset validation
- presence of the requested Arabic question
- eval runner behavior with and without predictions

## Current validation result

```text
15 passed
```

## Notes

- The first dataset version uses `page_numbers` and `required_terms` because stable indexed chunk IDs are not available until the PDF is ingested and indexed.
- After ingestion/indexing, records can be enriched with `expected_source.chunk_ids` for stricter retrieval metrics.
- RAGAS or LLM-as-judge evaluation is intentionally left for later.
