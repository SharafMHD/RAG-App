# RAG Evaluation Datasets

Golden datasets use JSON Lines (`.jsonl`), one question per line.

## Commands

Validate the default golden dataset:

```bash
PYTHONPATH=. uv run python -m evals.run_eval
```

Score a predictions file:

```bash
PYTHONPATH=. uv run python -m evals.run_eval \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --predictions path/to/predictions.jsonl \
  --k 5
```

Run eval foundation tests:

```bash
PYTHONPATH=. uv run pytest tests/test_eval_foundation.py -q
```

## Current datasets

- `golden_dataset/pension_law_arabic.jsonl` — Arabic baseline questions generated from `Docs/Pension law arabic.pdf`.

## Record shape

```json
{
  "id": "pension_ar_001",
  "document": "Pension law arabic.pdf",
  "language": "ar",
  "question": "...",
  "expected_answer": "...",
  "expected_source": {
    "page_numbers": [1],
    "required_terms": ["term"]
  },
  "tags": ["arabic", "pension-law"]
}
```

`expected_source.page_numbers` and `expected_source.required_terms` are used as the initial source-grounding contract until ingestion/indexing can provide stable chunk IDs. After indexing the PDF, records can be enriched with `expected_source_chunks`.
