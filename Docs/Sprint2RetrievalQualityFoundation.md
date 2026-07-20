# Sprint 2 — Retrieval Quality Foundation

## Status

Completed.

## Goal

Make retrieval quality measurable and improve the retriever from vector-only search to configurable vector, BM25-like lexical, and hybrid retrieval.

## Implemented Capabilities

### 1. Citation-capable retrieval records

`RetrievedDocuments` now supports:

- `chunk_id`
- `text`
- `score`
- `source`
- `page_number`
- `metadata`
- `retrieval_mode`

This lets API responses and eval predictions connect retrieved text back to chunks, source metadata, and page references.

### 2. Vector retrieval enrichment

PGVector search now returns:

- text
- score
- chunk ID
- metadata
- page/source fields derived from metadata
- `retrieval_mode="vector"`

### 3. BM25-like lexical retrieval

Added a simple BM25-style keyword retriever over stored `data_chunks`.

Implementation notes:

- Uses Arabic-compatible tokenization.
- Computes token overlap with IDF smoothing.
- Does not require extra PostgreSQL extensions.
- Useful for exact Arabic legal terms where vector search may miss precise wording.

### 4. Hybrid retrieval

Added hybrid retrieval using Reciprocal Rank Fusion over:

- vector search results
- BM25-like lexical results

The fused records use:

```text
retrieval_mode="hybrid"
```

### 5. Configurable retrieval settings

Added settings:

```env
HYBRID_SEARCH_ENABLED=false
BM25_ENABLED=false
VECTOR_TOP_K=30
BM25_TOP_K=30
HYBRID_TOP_N=10
RRF_K=60
MIN_RELEVANCE_SCORE=0.0
```

### 6. API strategy selection

Search and answer requests now accept an optional strategy:

```json
{
  "text": "من هو المؤمن عليه؟",
  "limit": 5,
  "strategy": "hybrid"
}
```

Valid values:

```text
vector
bm25
hybrid
```

If no strategy is supplied, the controller defaults to vector search unless `HYBRID_SEARCH_ENABLED=true`.

### 7. Evaluation prediction generation

Added:

```text
src/evals/generate_predictions.py
```

Example:

```bash
cd src
PYTHONPATH=. uv run python -m evals.generate_predictions \
  --dataset evals/golden_dataset/pension_law_arabic.jsonl \
  --knowledge-base-id <knowledge-base-id> \
  --mode hybrid \
  --limit 5 \
  --output evals/predictions/hybrid_baseline.jsonl
```

### 8. Run comparison report

Added:

```text
src/evals/compare_runs.py
```

Example:

```bash
cd src
PYTHONPATH=. uv run python -m evals.compare_runs \
  --runs \
    vector=evals/predictions/vector_baseline.jsonl \
    bm25=evals/predictions/bm25_baseline.jsonl \
    hybrid=evals/predictions/hybrid_baseline.jsonl \
  --output ../Docs/Sprint2RetrievalQualityReport.md
```

## Files Changed / Added

```text
src/controllers/NLPController.py
src/helpers/config.py
src/models/db_schemes/rag_app_db/schemes/data_chunk.py
src/routes/nlp.py
src/routes/schemes/nlp.py
src/stores/vectordb/Providers/PGVectorDBProvider.py
src/stores/retrieval/__init__.py
src/stores/retrieval/fusion.py
src/evals/generate_predictions.py
src/evals/compare_runs.py
src/tests/test_hybrid_retrieval.py
src/tests/test_eval_predictions.py
Docs/Sprint2RetrievalQualityReport.md
```

## Validation

Tests passed:

```text
19 passed
```

Sprint 1 eval validation still works:

```bash
cd src
PYTHONPATH=. uv run python -m evals.run_eval
```

Result:

```text
dataset_valid: 1
golden_records: 20
```

## Remaining Follow-up

The code foundation is complete. To populate final live metrics, ingest/index the pension law PDF into a knowledge base, then generate vector, BM25, and hybrid prediction files and run `evals.compare_runs`.

Reranking, query expansion, HyDE, and multi-vector retrieval remain future work.
