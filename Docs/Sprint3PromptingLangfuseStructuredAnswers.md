# Sprint 3 — Prompting, Langfuse, and Structured Answers

## Goal

Make RAG answers grounded, citation-aware, traceable, and stable for the future frontend.

## Implemented

- Added optional Langfuse wrapper:
  - `src/services/langfuse_service.py`
  - disabled/misconfigured Langfuse safely falls back to local UUID trace IDs.
- Added grounded prompt service:
  - `src/services/prompt_service.py`
  - local fallback prompt requires source-grounded answers and citations like `[source_1]`.
  - can fetch prompt `rag-grounded-answer` from Langfuse when enabled.
- Added structured answer validation:
  - `src/services/answer_validation.py`
  - internal `GeneratedAnswer` Pydantic schema.
  - citation extraction and validation.
  - no-answer behavior for empty retrieval or invalid citations.
  - automatic top-source citation repair when citation-required mode is enabled and the model omits citations.
- Updated answer endpoint:
  - `POST /api/v1/nlp/index/answer/{knowledge_base_id}`
  - returns Langfuse/local `trace_id`.
  - validates generated answer before building `ChatAnswerResponse`.
  - includes prompt metadata in `retrieval_metadata`.
- Updated NLP prompt construction:
  - retrieved chunks are labeled as stable `source_1`, `source_2`, etc.
  - system prompt treats retrieved content as untrusted.
- Initialized Langfuse/prompt services in FastAPI lifespan.
- Added Sprint 3 tests.

## New configuration

```env
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
LANGFUSE_ENVIRONMENT=local
LANGFUSE_RELEASE=sprint-3
LANGFUSE_TRACE_SAMPLE_RATE=1.0
RAG_PROMPT_NAME=rag-grounded-answer
RAG_PROMPT_LABEL=production
REQUIRE_ANSWER_CITATIONS=true
STRICT_CITATION_VALIDATION=true
```

Back-compatible lowercase Langfuse env names are still accepted.

## Response metadata additions

`retrieval_metadata` now may include:

```json
{
  "prompt_name": "rag-grounded-answer",
  "prompt_version": "7",
  "prompt_source": "langfuse"
}
```

When Langfuse is disabled, `prompt_source` is `local`.

## Validation commands

```bash
cd src
PYTHONPATH=. uv run pytest -q
PYTHONPATH=. uv run python -m evals.run_eval
```

Current result:

```text
25 passed
```

Eval dataset validation:

```text
dataset_valid: 1
golden_records: 20
```

## Notes

- Langfuse is optional. The API keeps working without Langfuse credentials.
- The API returns safe no-answer responses instead of 500s when retrieval context is insufficient.
- The current implementation validates/repairs citations after generation. A later sprint can move to strict provider-native JSON output where supported.
