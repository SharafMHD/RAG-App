# Sprint 0 — Baseline and Contracts

## Current backend RAG flow

1. Create a knowledge base: `POST /api/v1/data/knowledge-bases/create`
2. Upload a document: `POST /api/v1/data/upload/{knowledge_base_id}`
3. Process chunks: `POST /api/v1/data/processfile/{knowledge_base_id}`
4. Index chunks: `POST /api/v1/nlp/index/push/{knowledge_base_id}`
   - Combined workflow also exists: `POST /api/v1/data/process_and_index/{knowledge_base_id}`
5. Search indexed chunks: `POST /api/v1/nlp/index/search/{knowledge_base_id}`
6. Generate a RAG answer: `POST /api/v1/nlp/index/answer/{knowledge_base_id}`

## Knowledge base selection contract

The frontend selects exactly one knowledge base for the current chat by calling backend endpoints with the selected `knowledge_base_id` path parameter.

```http
POST /api/v1/nlp/index/answer/{knowledge_base_id}
Content-Type: application/json

{
  "text": "What does this document say about refunds?",
  "limit": 5
}
```

`limit` is the current vector-search top-k for the request. It is bounded by the backend schema to `1..50`.

## Chat answer response contract

`POST /api/v1/nlp/index/answer/{knowledge_base_id}` returns the stable chat response shape for the future Next.js UI:

```json
{
  "status": true,
  "knowledge_base_id": "uuid",
  "answer": "Grounded answer text.",
  "citations": [
    {
      "source_id": "source_1",
      "rank": 1,
      "score": 0.83,
      "document_name": "policy.pdf",
      "page_number": 2,
      "chunk_id": "chunk uuid"
    }
  ],
  "source_chunks": [
    {
      "source_id": "source_1",
      "rank": 1,
      "text": "Retrieved source chunk text...",
      "score": 0.83,
      "metadata": {}
    }
  ],
  "confidence": 0.83,
  "retrieval_metadata": {
    "strategy": "vector",
    "requested_top_k": 5,
    "returned_count": 1,
    "vector_top_k": 5,
    "bm25_top_k": null,
    "rerank_top_n": null,
    "min_relevance_score": null
  },
  "trace_id": "uuid",
  "message": "RAG answer generated successfully"
}
```

Notes:

- The current implementation uses vector retrieval only; BM25 and reranking fields are reserved for later sprints.
- Citations are derived from retrieved source chunks. Rich document/page metadata will become more complete after document-processing upgrades.
- `trace_id` is generated now and can later be replaced or correlated with Langfuse trace IDs.
- The response intentionally does not expose the final prompt or chat history to the frontend.

## Production configuration values to confirm

Backend/RAG:

- `GENERATION_BACKEND`, `GENERATION_MODEL_ID`, provider API key
- `EMBEDDING_BACKEND`, `EMBEDDING_MODEL_ID`, `EMBEDDING_MODEL_SIZE`, provider API key
- `VECTOR_DB_BACKEND`, `VECTOR_DB_DISTANCE_METHOD`, `PGVECTOR_INDEX_THREADHOLD`
- `DEFAULT_INPUT_MAX_TOKENS`, `DEFAULT_OUTPUT_MAX_TOKENS`, `DEFAULT_GENERATION_TEMPERATURE`
- `FILE_ALLOWED_TYPES`, `FILE_ALLOWED_SIZE`, chunk defaults

Langfuse:

- `langfuse_secret_key`
- `langfuse_public_key`
- `langfuse_base_url`

Frontend/API:

- Backend API base URL
- API-key header value if `REQUIRE_API_KEY=true`
- Allowed CORS origins for frontend domain(s)
- Auth/session provider values once selected

## Smoke-test coverage added

- Request validation for chat/search inputs.
- Knowledge-base creation payload validation.
- Template fallback behavior.
- File-name sanitization.
- Chunking overlap behavior.
- Stable chat response schema shape for the frontend.
