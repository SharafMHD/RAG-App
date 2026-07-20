# Sprint 2 Retrieval Quality Report

Sprint 2 retrieval tooling has been implemented. Populate this report with live metrics after the pension-law PDF is ingested and predictions are generated for the target knowledge base.

## Commands

```bash
cd src

PYTHONPATH=. uv run python -m evals.generate_predictions \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --knowledge-base-id <knowledge-base-id> \
  --mode vector \
  --limit 5 \
  --output evals/predictions/vector_baseline.jsonl

PYTHONPATH=. uv run python -m evals.generate_predictions \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --knowledge-base-id <knowledge-base-id> \
  --mode bm25 \
  --limit 5 \
  --output evals/predictions/bm25_baseline.jsonl

PYTHONPATH=. uv run python -m evals.generate_predictions \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --knowledge-base-id <knowledge-base-id> \
  --mode hybrid \
  --limit 5 \
  --output evals/predictions/hybrid_baseline.jsonl

PYTHONPATH=. uv run python -m evals.compare_runs \
  --runs \
    vector=evals/predictions/vector_baseline.jsonl \
    bm25=evals/predictions/bm25_baseline.jsonl \
    hybrid=evals/predictions/hybrid_baseline.jsonl \
  --output ../Docs/Sprint2RetrievalQualityReport.md
```

## Implemented

- Citation-capable retrieval records: `chunk_id`, metadata, page number, source, retrieval mode.
- Vector retrieval predictions exporter.
- BM25-like lexical retrieval over stored chunks.
- Hybrid retrieval via Reciprocal Rank Fusion.
- Multi-run eval comparison report generator.
- Tests for fusion and prediction/report format.
