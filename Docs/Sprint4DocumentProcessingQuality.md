# Sprint 4 — Document Processing Quality

Status: ✅ Completed

Companion report: [Sprint 4 — Document Processing Quality Report](Sprint4DocumentProcessingQualityReport.md)

## Goal

Improve indexed document quality by making extraction and chunking page-aware, metadata-rich, and measurable against the golden evaluation dataset.

## Implemented

- Added document-processing services:
  - `src/services/document_processing/pdf_extractor.py`
  - `src/services/document_processing/text_cleaner.py`
  - `src/services/document_processing/chunker.py`
- Replaced flat whole-document splitting with page-aware recursive chunking in `ProcessFileController`.
- PDF extraction now normalizes page numbers to one-based values for citations.
- Text ingestion now adds source/page metadata consistently.
- Chunk metadata now includes:
  - `source`
  - `document_name`
  - `file_name`
  - `page`
  - `page_number`
  - `chunk_index`
  - `page_chunk_index`
  - `chunking_strategy`
  - `embedding_model`
  - `content_hash`
  - `parent_chunk_id`
  - `parent_child_chunking_enabled`
- Added nullable relational columns for frequently queried/versioned chunk metadata:
  - `chunking_strategy`
  - `embedding_model`
  - `content_hash`
  - `parent_chunk_id`
- Added Alembic migration:
  - `src/models/db_schemes/rag_app_db/alembic/versions/c8d1e2f3a4b5_add_sprint4_chunk_metadata.py`
- Qdrant vector search now returns `chunk_id`, metadata, source, page number, and retrieval mode, matching PGVector behavior.
- Added Sprint 4 unit tests for text cleaning and chunking metadata.
- Added Sprint 4 completion report:
  - `Docs/Sprint4DocumentProcessingQualityReport.md`

## New configuration

```env
FILE_DEFAULT_CHUNK_SIZE=900
FILE_OVERLAP_SIZE=150
CHUNKING_STRATEGY=page_recursive_v1
CHUNK_SIZE=900
CHUNK_OVERLAP=150
MIN_CHUNK_CHARS=100
PARENT_CHILD_CHUNKING_ENABLED=false
```

`EMBEDDING_MODEL_ID` is stored in chunk metadata as the embedding model version.

## Validation commands

```bash
cd src
PYTHONPATH=. uv run pytest -q
PYTHONPATH=. uv run python -m evals.run_eval
```

Current result:

```text
28 passed
```

Eval dataset validation:

```text
dataset_valid: 1
golden_records: 20
```

## Migration and re-indexing

Apply the migration:

```bash
cd src/models/db_schemes/rag_app_db
PYTHONPATH=../../../../ uv run alembic upgrade head
```

Then reprocess and re-index each existing knowledge base so old chunks are regenerated with Sprint 4 metadata.

## Completion checklist

- [x] Page-aware PDF extraction boundary.
- [x] Page-aware text extraction metadata.
- [x] Recursive page-aware chunking.
- [x] Chunk metadata for source, page, chunking strategy, embedding model, hash, and parent-child scaffold.
- [x] DB migration for chunk metadata columns.
- [x] Qdrant retrieval metadata parity with PGVector.
- [x] Sprint 4 tests.
- [x] Sprint 4 report.

## Notes

- Parent-child chunking is scaffolded through metadata and a nullable `parent_chunk_id`, but remains disabled by default.
- Table extraction is not fully implemented yet; Sprint 4 creates the extraction boundary where a richer PDF/table parser can be added later.
- For existing indexed data, reprocess and re-index the knowledge base after running migrations to populate the new metadata.
