# Sprint 5 — Next.js Chat UI MVP

## Goal

Ship a usable non-streaming chat frontend for the FastAPI RAG backend.

The UI lets a user select one knowledge base, ask a question, and inspect the grounded answer with citations, retrieved source chunks, confidence, retrieval metadata, and trace ID.

## What changed

- Added a standalone Next.js frontend app in `frontend/`.
- Added a typed frontend API layer:
  - `frontend/lib/api/client.ts`
  - `frontend/lib/api/rag.ts`
  - `frontend/lib/api/types.ts`
- Added the main chat page at `frontend/app/page.tsx`.
- Added UI components for:
  - knowledge base selection/manual KB ID entry
  - answer metadata
  - citations
  - retrieved source chunks
- Added Arabic/RTL-friendly rendering by detecting Arabic text in messages.
- Added loading, empty, and error states.
- Added optional API-key forwarding through the `X-API-Key` header.
- Added backend endpoint for listing knowledge bases:
  - `GET /api/v1/data/knowledge-bases`
- Fixed paged knowledge-base listing in `KnowledgeBaseDataModel.get_all_paged_knowledge_bases`.

## Frontend setup

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm run dev
```

Default local URL:

```text
http://localhost:3000
```

## Frontend environment variables

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DEFAULT_KNOWLEDGE_BASE_ID=
NEXT_PUBLIC_API_KEY=
```

Notes:

- `NEXT_PUBLIC_API_BASE_URL` should point to the FastAPI backend.
- `NEXT_PUBLIC_DEFAULT_KNOWLEDGE_BASE_ID` is optional.
- `NEXT_PUBLIC_API_KEY` is optional and is sent as `X-API-Key` when backend `REQUIRE_API_KEY=true`.

## Backend contract used by the UI

Answer endpoint:

```http
POST /api/v1/nlp/index/answer/{knowledge_base_id}
Content-Type: application/json
```

Request:

```json
{
  "text": "What does the document say?",
  "limit": 5,
  "strategy": "hybrid"
}
```

Response fields rendered by the UI:

- `answer`
- `citations[].source_id`
- `citations[].document_name`
- `citations[].page_number`
- `citations[].score`
- `citations[].chunk_id`
- `source_chunks[].text`
- `source_chunks[].score`
- `confidence`
- `retrieval_metadata.strategy`
- `retrieval_metadata.returned_count`
- `trace_id`

Knowledge-base list endpoint:

```http
GET /api/v1/data/knowledge-bases?page=1&page_size=100
```

If listing fails, the UI falls back to manual `knowledge_base_id` entry.

## Validation

Commands run:

```bash
cd src
PYTHONPATH=. uv run pytest -q
```

Result:

```text
28 passed
```

Frontend type-check and build:

```bash
cd frontend
pnpm install
pnpm run lint
pnpm run build
```

Result:

```text
tsc --noEmit
Compiled successfully
```

## Manual end-to-end test flow

1. Start backend dependencies and FastAPI.
2. Ensure at least one knowledge base is created, processed, and indexed.
3. Start frontend:

```bash
cd frontend
pnpm run dev
```

4. Open `http://localhost:3000`.
5. Select a knowledge base or paste a `knowledge_base_id`.
6. Ask a question.
7. Confirm the UI displays:
   - assistant answer
   - citations
   - source chunks
   - confidence/retrieval strategy
   - trace ID

## Known limitations

- Responses are non-streaming. Streaming is Sprint 6.
- Chat history is local component state only and is not persisted server-side.
- No authentication/session handling yet.
- No upload or document-management screens yet.
- Feedback controls are deferred to Sprint 6.

## Sprint 6 handoff

Recommended next items:

- Add FastAPI streaming answer endpoint.
- Connect streaming responses in the Next.js UI.
- Preserve final citations after stream completion.
- Add thumbs up/down feedback tied to `trace_id`.
- Send feedback metadata to Langfuse.
