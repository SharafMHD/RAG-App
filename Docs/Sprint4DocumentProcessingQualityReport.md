# Sprint 4 — Document Processing Quality Report

## Summary

Sprint 4 is complete as a document-processing foundation sprint. The ingestion pipeline now creates page-aware, metadata-rich chunks that support better retrieval debugging, citations, and future chunking experiments.

## What changed

- PDF extraction is isolated behind `PDFExtractor` so parser improvements can be made without changing the rest of ingestion.
- PDF page indexes are normalized to one-based `page_number` values for user-facing citations.
- Text extraction now adds the same source/page metadata shape as PDF extraction.
- Chunking now uses `page_recursive_v1`:
  - page-first splitting
  - configurable chunk size and overlap
  - boundary-aware splitting on paragraph/newline/sentence/space where possible
  - empty page skipping
- Chunk metadata now records processing/version information:
  - `chunk_index`
  - `page_chunk_index`
  - `chunking_strategy`
  - `embedding_model`
  - `content_hash`
  - `parent_chunk_id`
- Database model and migration now include common chunk-version columns.
- Qdrant search results now return the same metadata-rich shape expected by the frontend/RAG contract.

## Validation

Commands run:

```bash
cd src
PYTHONPATH=. uv run pytest -q
PYTHONPATH=. uv run python -m evals.run_eval
```

Results:

```text
28 passed
```

```json
{
  "dataset_valid": 1,
  "golden_records": 20
}
```

## Evaluation status

The golden dataset validates successfully. Full retrieval-quality comparison requires applying the migration, reprocessing documents, and regenerating prediction files against the re-indexed knowledge base.

Recommended post-migration comparison flow:

```bash
cd src/models/db_schemes/rag_app_db
PYTHONPATH=../../../../ uv run alembic upgrade head

# Reprocess/re-index the target knowledge base through the API or Celery workflow.

cd ../../../..
PYTHONPATH=. uv run python -m evals.generate_predictions --help
PYTHONPATH=. uv run python -m evals.run_eval
```

## Exit criteria

- [x] Page-aware PDF/text extraction foundation exists.
- [x] Chunks preserve source and page metadata.
- [x] Chunks store chunking and embedding version metadata.
- [x] Parent-child chunking is scaffolded through nullable metadata and DB field.
- [x] Qdrant and PGVector retrieval can expose citation metadata.
- [x] Unit tests cover Sprint 4 text cleaning and chunking behavior.
- [x] Existing test suite passes.
- [x] Golden dataset validation still passes.

## Deferred follow-up items

- Full table extraction and table-aware chunking.
- Heading/section/caption detection.
- True parent-child retrieval behavior.
- Re-indexed production retrieval comparison report after a real knowledge base is migrated and reprocessed.
