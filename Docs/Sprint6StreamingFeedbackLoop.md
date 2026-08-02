# Sprint 6 Streaming and Feedback Loop

Sprint 6 is complete for the verified scope. The existing non-streaming answer route stays available for Sprint 5 clients, and the new browser streaming, feedback, admin URL display, query preprocessing, and browser QA work are all backed by accepted Sprint 6 evidence.

## Verified scope summary

- Added `POST /api/v1/nlp/index/answer/{knowledge_base_id}/stream` for browser answer streaming.
- Kept `POST /api/v1/nlp/index/answer/{knowledge_base_id}` compatible with the existing final answer contract.
- Added frontend SSE parsing, streamed chat rendering, final answer reconciliation, and focused browser coverage.
- Added feedback persistence, backend feedback submission, frontend feedback controls, and best-effort Langfuse scoring.
- Added public admin monitoring and service URL display rows.
- Added bounded query preprocessing with opt-in expansion and decomposition.

## SSE answer stream contract

Verified by `.omo/evidence/task-7-verification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-8-reverification-sprint-6-finish-microplan.txt`, and `.omo/evidence/task-11-verification-sprint-6-finish-microplan.txt`.

- Endpoint: `POST /api/v1/nlp/index/answer/{knowledge_base_id}/stream`
- Media type: `text/event-stream`
- Framing: `event: NAME\ndata: JSON\n\n`
- Allowed event sequence on success: `token*`, then `final`, then `done`
- Allowed terminal failure sequence after headers: `error`, then `done`
- No-results path skips provider token generation and emits `final`, then `done`

Event payloads:

| Event | Payload |
| --- | --- |
| `token` | `{"content":"..."}` |
| `final` | `{"response": <ChatAnswerResponse>}` |
| `error` | `{"detail":"...","message":"..."}` |
| `done` | `{}` |

NDJSON remains reserved for backend data and chunk pipelines. Sprint 6 does not use NDJSON for the user-facing answer stream.

## Frontend streaming behavior

Verified by `.omo/evidence/task-8-reverification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-11-verification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-15-focused-browser-sprint-6-finish-microplan.txt`, and `.omo/evidence/task-16-full-qa-sprint-6-finish-microplan.txt`.

- The frontend uses `fetch()` with a JSON `POST` body, `Accept: text/event-stream`, `Content-Type: application/json`, and optional `X-API-Key` when `NEXT_PUBLIC_API_KEY` is configured.
- The stream helper buffers partial chunks, parses SSE `event:` and `data:` lines, and does not use `EventSource` or the non-streaming `apiFetch<T>` helper.
- Chat state distinguishes `user`, `assistant_streaming`, `assistant_complete`, and `assistant_error` messages.
- Submitting a question appends one user message and one stable assistant placeholder.
- `token` events append provisional text.
- `final.response.answer` replaces the provisional text and attaches authoritative citations, source chunks, confidence, retrieval metadata, and `trace_id`.
- `done` closes the active stream. Abort on clear and unmount was verified. Late events are ignored after terminal completion or error.
- Feedback controls render only for `assistant_complete`. Streaming and error states do not expose rating controls.

## Feedback persistence and Langfuse behavior

Verified by `.omo/evidence/task-2-reverification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-3-verification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-12-reverification-sprint-6-finish-microplan.txt`, and `.omo/evidence/task-13-verification-sprint-6-finish-microplan.txt`.

- Backend endpoint: `POST /api/v1/nlp/index/answer/{knowledge_base_id}/feedback`
- `FeedbackRequest` requires `trace_id`, `knowledge_base_id`, `rating`, `question`, `answer`, `citations`, and `source_chunks`. `comment` is optional. Empty `citations` and `source_chunks` arrays are allowed when they are sent explicitly.
- Persistence is upsert-based, with one mutable record per `trace_id`.
- Persistence happens before Langfuse scoring.
- Persistence success still returns HTTP 200 when Langfuse is disabled or scoring fails.
- Persistence failures are not converted into fake success responses.
- Langfuse score mapping is fixed: `thumbs_up -> 1.0`, `thumbs_down -> 0.0`.
- The scoring wrapper reports `disabled`, `sent`, or `failed` and flushes only when the client exposes a callable flush method.
- The frontend sends the final answer snapshot, question snapshot, citations, and source chunks with each completed-message feedback submission.

## Admin monitoring and service URLs

Verified by `.omo/evidence/task-9-verification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-10-verification-sprint-6-finish-microplan.txt`, `.omo/evidence/task-15-focused-browser-sprint-6-finish-microplan.txt`, and `.omo/evidence/task-16-full-qa-sprint-6-finish-microplan.txt`.

Public display-only env vars:

```env
NEXT_PUBLIC_FASTAPI_URL
NEXT_PUBLIC_FLOWER_URL
NEXT_PUBLIC_PROMETHEUS_URL
NEXT_PUBLIC_GRAFANA_URL
NEXT_PUBLIC_LANGFUSE_URL
NEXT_PUBLIC_POSTGRESQL_URL
NEXT_PUBLIC_RABBITMQ_URL
NEXT_PUBLIC_REDIS_URL
NEXT_PUBLIC_CELERY_WORKER_URL
NEXT_PUBLIC_QDRANT_URL
```

Verified rendering rules:

- Blank or whitespace-only values render exactly `Not configured`.
- Parsed `http:` and `https:` values render as external links with `target="_blank"` and `rel="noopener noreferrer"`.
- Non-HTTP values such as `postgresql:`, `amqp:`, `redis:`, and Celery worker identifiers render as text only.
- Unsafe or malformed values, including `javascript:` URLs, render as text only.
- These values are public by design. Do not place credentials in them.

## Query preprocessing controls and defaults

Verified by `.omo/evidence/task-4-verification-sprint-6-finish-microplan.txt` and `.omo/evidence/task-16-full-qa-sprint-6-finish-microplan.txt`.

- Request field: `preprocessing`
- Supported controls:

```json
{
  "expand": true,
  "decompose": true,
  "max_generated_queries": 4
}
```

- Default behavior is off. Omitting `preprocessing`, or sending `expand=false` and `decompose=false`, keeps retrieval on the original query only.
- Decomposition runs before expansion.
- The original query stays in position zero.
- Generated queries are whitespace-normalized, casefold-deduplicated, and limited by one shared generated-query cap.
- External preprocessing failures and timeouts fall back to original-query-only retrieval with fallback metadata.
- Verified metadata states include `disabled` for no-op preprocessing and `fallback` for external-generation failure paths.

## Verification commands and accepted evidence

Accepted evidence paths consulted for Sprint 6 status:

- `.omo/evidence/task-1-acceptance-sprint-6-finish-microplan-post-fix.txt`
- `.omo/evidence/task-2-reverification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-3-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-4-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-7-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-8-reverification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-9-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-10-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-11-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-12-reverification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-13-verification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-14-reverification-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-15-focused-browser-sprint-6-finish-microplan.txt`
- `.omo/evidence/task-16-full-qa-sprint-6-finish-microplan.txt`

Representative accepted commands:

```bash
cd src && PYTHONPATH=. uv run --with pytest python -m pytest -q tests/test_core_behaviors.py tests/test_sprint6_contracts.py
cd src && PYTHONPATH=. uv run --with pytest python -m pytest -q tests/test_sprint6_query_preprocessing.py tests/test_hybrid_retrieval.py
cd src && PYTHONPATH=. uv run --with pytest python -m pytest -q tests/test_sprint6_streaming_route.py tests/test_sprint3_prompting_langfuse.py
cd src && PYTHONPATH=. uv run --with pytest python -m pytest -q tests/test_sprint6_feedback.py tests/test_sprint3_prompting_langfuse.py
cd src && PYTHONPATH=. uv run --with pytest python -m pytest -q
cd frontend && pnpm run lint && pnpm run build
cd frontend && pnpm exec playwright test tests/smoke.spec.ts --project=chromium
cd frontend && pnpm exec playwright test tests/sprint6-streaming.spec.ts --project=chromium
cd frontend && pnpm exec playwright test tests/sprint6-feedback.spec.ts --project=chromium
cd frontend && pnpm exec playwright test tests/admin-settings.spec.ts --project=chromium
cd frontend && pnpm exec playwright test tests/evidence-ui.spec.ts --project=chromium
cd frontend && pnpm run lint && pnpm run build && pnpm exec playwright test
GIT_MASTER=1 git diff --check
```

## Known limitations

- Auth and session handling are still out of scope.
- The deferred admin review workflow is still out of scope.
- Upload and document-management screens are still not part of Sprint 6.
- Sprint 6 QA was confirmed with mocked browser and backend flows. It did not require a live LLM, VPS, Langfuse service, or external services.
- Live PostgreSQL deployment behavior is still an environment risk because the accepted feedback verification uses available repository fixtures and in-memory adapters, not a standard live PostgreSQL fixture.
