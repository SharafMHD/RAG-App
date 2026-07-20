# Production RAG Advanced TODO

This document captures the advanced RAG production-readiness plan for this app, based on the MiniRAG advanced topics notes and adapted for a single VPS + Docker Compose production deployment.


---

## Target Retrieval Pipeline

```text
User Query
   ↓
Query classification
   ↓
Optional query rewrite/decomposition
   ↓
Vector search top K
   +
BM25 search top K
   ↓
Result fusion
   ↓
Re-ranker
   ↓
Metadata/permission filtering
   ↓
Final context selection
   ↓
LLM answer with citations
   ↓
Structured response + tracing + feedback
```

Recommended config:

```env
HYBRID_SEARCH_ENABLED=true
BM25_ENABLED=true
RERANK_ENABLED=true
VECTOR_TOP_K=30
BM25_TOP_K=30
RERANK_TOP_N=8
MIN_RELEVANCE_SCORE=0.0
```

---

## UI / Frontend Chat App

Plan: build the user-facing chat UI with **Next.js** using Vercel's chatbot template:

<https://vercel.com/templates/next.js/chatbot>

- [ ] Create a separate Next.js frontend app for chat UI.
- [ ] Start from the Vercel Next.js chatbot template.
- [ ] Connect the chat UI to this FastAPI RAG backend.
- [ ] Support knowledge base selection in the UI.
- [ ] Display assistant answers with citations/sources.
- [ ] Display retrieved source metadata:
  - document name
  - page number
  - chunk/source reference
  - relevance/rerank score if useful
- [ ] Add streaming response support once backend streaming endpoint is ready.
- [ ] Add upload/document management screens if needed.
- [ ] Add feedback controls:
  - thumbs up
  - thumbs down
  - optional comment
- [ ] Send user feedback to backend and Langfuse where appropriate.
- [ ] Add authentication/session handling before production.
- [ ] Configure production frontend environment variables:
  - backend API URL
  - auth config
  - analytics/tracing config if needed
- [ ] Deploy frontend either:
  - on same VPS behind Caddy, or
  - on Vercel connected to the VPS API.

Priority: **High**

---

## 1. Advanced Retrieval Techniques

- [ ] Add BM25 keyword search.
- [ ] Add hybrid retrieval: vector search + BM25.
- [ ] Add result fusion between vector and BM25 results.
- [ ] Add re-ranking after initial retrieval.
- [ ] Add query expansion.
- [ ] Add optional HyDE mode.
- [ ] Add optional multi-vector retrieval.

Priority: **High**

---

## 2. Query Understanding and Routing

- [ ] Classify query type:
  - factual
  - summarization
  - comparison
  - analytical
  - conversational
  - out-of-scope
- [ ] Route each query type to different retrieval settings.
- [ ] Add query decomposition for complex questions.
- [ ] Add intent-aware prompts.

Priority: **High**

---

## 3. Advanced Document Processing

- [ ] Improve PDF extraction.
- [ ] Add table extraction.
- [ ] Preserve document structure:
  - headings
  - sections
  - page numbers
  - tables
  - captions
- [ ] Add parent-child chunking.
- [ ] Add contextual chunking.
- [ ] Store rich metadata per chunk.

Priority: **High**

---

## 4. Agentic RAG

- [ ] Keep normal RAG as default.
- [ ] Add agentic mode later for complex queries.
- [ ] Let agent choose retrieval tools:
  - vector search
  - BM25 search
  - metadata search
  - database lookup
- [ ] Add max tool calls and timeout protection.

Priority: **Medium**

---

## 5. Evaluation and Quality Measurement

- [ ] Create golden test dataset:
  - question
  - expected answer
  - expected source chunks
- [ ] Measure retrieval quality:
  - recall@k
  - precision@k
  - MRR
- [ ] Measure answer quality:
  - faithfulness
  - relevance
  - citation correctness
- [ ] Add RAGAS or similar evaluation.
- [ ] Run evals before every release.

Priority: **Very High**

---

## 6. Production Safety and Reliability

- [ ] Add hallucination guardrails.
- [ ] Require citations.
- [ ] Add “I don’t know” behavior when context is insufficient.
- [ ] Add timeout limits for LLM calls.
- [ ] Add retry handling.
- [ ] Add fallback behavior if retrieval, reranking, or LLM fails.
- [ ] Log failures safely.

Priority: **Very High**

---

## 7. Conversation and Memory

- [ ] Add chat history support.
- [ ] Summarize long conversation history.
- [ ] Use conversation-aware query rewriting.
- [ ] Keep user memory separate from document knowledge.
- [ ] Add privacy controls for stored conversations.

Priority: **Medium**

---

## 8. Performance and Scaling

- [ ] Cache embeddings.
- [ ] Cache retrieval results where safe.
- [ ] Add async processing for ingestion.
- [ ] Tune Celery concurrency.
- [ ] Add batch embedding.
- [ ] Monitor token usage and latency.
- [ ] Load test retrieval and ingestion.

Priority: **High**

---

## 9. Multi-modal RAG

- [ ] Future support for images inside PDFs.
- [ ] Extract image captions/descriptions.
- [ ] Store image metadata.
- [ ] Add vision model processing only when needed.

Priority: **Low/Medium**

---

## 10. Embedding Models Deep Dive

- [ ] Choose production embedding model.
- [ ] Benchmark embedding models against the eval set.
- [ ] Track embedding dimensions and vector DB compatibility.
- [ ] Add migration plan when changing embedding model.
- [ ] Store embedding model version per chunk.

Priority: **High**

---

## 11. Chunking Strategies Deep Dive

- [ ] Compare chunking strategies:
  - fixed-size
  - semantic
  - recursive
  - parent-child
  - contextual
- [ ] Tune chunk size and overlap.
- [ ] Store chunk index and parent document ID.
- [ ] Evaluate chunking using retrieval metrics.

Priority: **Very High**

---

## 12. GraphRAG and Knowledge Graphs

- [ ] Future option for entity extraction.
- [ ] Build relationships between:
  - documents
  - topics
  - entities
  - concepts
- [ ] Use graph retrieval for complex relationship questions.

Priority: **Low**

---

## 13. Prompt Engineering for RAG

Plan: use **Langfuse** for prompt management, prompt versioning, tracing, and evaluation feedback.

- [ ] Connect the app to Langfuse in production.
- [ ] Store RAG prompts in Langfuse instead of hardcoding production prompts.
- [ ] Version prompts in Langfuse.
- [ ] Track which prompt version was used for each answer.
- [ ] Add system prompt for grounded answers.
- [ ] Add citation format.
- [ ] Add no-answer instruction.
- [ ] Add different prompts by query type.
- [ ] Use Langfuse traces to inspect:
  - query
  - retrieved chunks
  - reranked chunks
  - final prompt
  - model response
  - latency/cost
- [ ] Test prompt changes against eval set before promotion.
- [ ] Define prompt promotion flow: draft → staging → production.

Priority: **High**

---

## 14. Arabic and RTL RAG

Important if users or documents include Arabic.

- [ ] Test Arabic document ingestion.
- [ ] Test Arabic queries.
- [ ] Use multilingual embeddings if needed.
- [ ] Support RTL output.
- [ ] Evaluate Arabic retrieval quality separately.

Priority: **Depends on audience**

---

## 15. Prompt Injection and RAG Security

- [ ] Detect malicious instructions inside documents.
- [ ] Add prompt-injection guardrails.
- [ ] Never allow retrieved documents to override system instructions.
- [ ] Add document sanitization.
- [ ] Add tests for prompt injection examples.

Priority: **Very High**

---

## 16. Metadata Filtering

- [ ] Filter by:
  - knowledge base
  - document
  - file type
  - date
  - owner/user
  - tags
- [ ] Add metadata-aware retrieval.
- [ ] Add permission-aware retrieval.

Priority: **Very High**

---

## 17. Cost Optimization and Token Management

- [ ] Limit retrieved context size.
- [ ] Compress context if too long.
- [ ] Track cost per request.
- [ ] Use cheaper models for:
  - query classification
  - query rewriting
  - reranking if local
- [ ] Add token budget config.

Priority: **High**

---

## 18. Testing RAG Systems

- [ ] Unit tests for chunking.
- [ ] Unit tests for metadata filtering.
- [ ] Unit tests for reranking.
- [ ] Integration tests for ingestion → retrieval → answer.
- [ ] Regression tests using golden dataset.
- [ ] Security tests for prompt injection.

Priority: **Very High**

---

## 19. LangChain and LlamaIndex Integration

- [ ] Do not add immediately unless needed.
- [ ] Keep current architecture clean.
- [ ] Consider LangChain/LlamaIndex only for:
  - query decomposition
  - agentic RAG
  - evaluation helpers
  - advanced retrievers

Priority: **Low/Medium**

---

## 21. Structured Output with Pydantic

- [ ] Add structured answer schema.
- [ ] Return:
  - answer
  - citations
  - confidence
  - source chunks
  - retrieval metadata
- [ ] Validate LLM output with Pydantic.

Priority: **High**

---

## 22. Streaming Responses in FastAPI

- [ ] Add optional streaming answer endpoint.
- [ ] Keep non-streaming endpoint for API clients.
- [ ] Stream tokens while preserving final citations.
- [ ] Handle disconnects safely.

Priority: **Medium**

---

## 23. Feedback Loops

- [ ] Add thumbs up/down feedback.
- [ ] Store user feedback.
- [ ] Track bad answers.
- [ ] Use feedback to improve:
  - chunking
  - prompts
  - retrieval settings
  - eval dataset
- [ ] Add admin review workflow.

Priority: **High**

---

# Suggested Implementation Sprints

## Sprint 0 — Baseline and Contracts

Goal: define stable backend/frontend contracts before adding advanced features.

- [x] Review current ingestion, retrieval, and answer endpoints.
- [x] Define final chat API response schema:
  - answer
  - citations
  - source chunks
  - confidence
  - retrieval metadata
  - trace ID
- [x] Define frontend/backend contract for knowledge base selection.
- [x] Add basic smoke tests for current RAG flow.
- [x] Confirm production env/config values needed for RAG, Langfuse, and frontend.

Exit criteria: current backend flow is documented and the future Next.js UI knows what API shape to consume.

---

## Sprint 1 — Evaluation Foundation

Goal: create measurement before changing retrieval quality.

- [ ] Create golden dataset:
  - question
  - expected answer
  - expected source chunks
- [ ] Add retrieval metrics:
  - recall@k
  - precision@k
  - MRR
- [ ] Add answer quality checks:
  - faithfulness
  - relevance
  - citation correctness
- [ ] Add regression test command.
- [ ] Add RAGAS or LLM-as-judge evaluation later if needed.

Exit criteria: every retrieval/prompt change can be compared against baseline.

---

## Sprint 2 — Core Retrieval Upgrade

Goal: improve answer relevance with hybrid search and reranking.

- [ ] Add BM25 keyword search.
- [ ] Add hybrid vector + BM25 retrieval.
- [ ] Add result fusion.
- [ ] Add re-ranking.
- [ ] Add metadata filtering by knowledge base/document/user where applicable.
- [ ] Add retrieval config:
  - `VECTOR_TOP_K`
  - `BM25_TOP_K`
  - `RERANK_TOP_N`
  - `MIN_RELEVANCE_SCORE`

Exit criteria: hybrid + rerank improves eval metrics compared with baseline.

---

## Sprint 3 — Prompting, Langfuse, and Structured Answers

Goal: make answers grounded, traceable, versioned, and frontend-friendly.

- [ ] Connect backend to Langfuse.
- [ ] Move production prompts into Langfuse prompt management.
- [ ] Add prompt version tracking per answer.
- [ ] Add citation-required system prompt.
- [ ] Add no-answer behavior when context is insufficient.
- [ ] Add structured Pydantic response schema.
- [ ] Trace query, retrieval, reranking, final prompt, answer, latency, and cost in Langfuse.

Exit criteria: each answer has citations, structured output, and a Langfuse trace ID.

---

## Sprint 4 — Document Processing Quality

Goal: improve the indexed data quality.

- [ ] Improve PDF parsing.
- [ ] Add table extraction plan/implementation.
- [ ] Preserve headings, sections, page numbers, captions, and metadata.
- [ ] Add parent-child chunking.
- [ ] Add contextual chunking where useful.
- [ ] Store embedding model version per chunk.
- [ ] Evaluate chunking strategies against the golden dataset.

Exit criteria: better chunk quality improves retrieval and citation quality.

---

## Sprint 5 — Next.js Chat UI MVP

Goal: ship a usable chat frontend using the Vercel Next.js chatbot template.

- [ ] Create Next.js app from Vercel chatbot template.
- [ ] Connect chat UI to FastAPI RAG backend.
- [ ] Add knowledge base selection.
- [ ] Render structured answers.
- [ ] Render citations and source metadata.
- [ ] Show loading/error states.
- [ ] Add basic auth/session plan.
- [ ] Configure frontend env vars for backend API URL.

Exit criteria: user can ask questions from the UI and see cited answers.

---

## Sprint 6 — Streaming and Feedback Loop

Goal: improve UX and start learning from users.

- [ ] Add FastAPI streaming response endpoint.
- [ ] Connect streaming to Next.js chat UI.
- [ ] Preserve final citations after stream completion.
- [ ] Add thumbs up/down feedback UI.
- [ ] Store feedback in backend.
- [ ] Send feedback metadata to Langfuse.
- [ ] Add admin/review workflow later.

Exit criteria: UI streams answers and captures feedback tied to trace IDs.

---

## Sprint 7 — RAG Security and Production Hardening

Goal: protect the system before real production usage.

- [ ] Add prompt injection protections.
- [ ] Add document sanitization rules.
- [ ] Add tests for malicious document instructions.
- [ ] Add permission-aware retrieval.
- [ ] Add LLM/retrieval timeouts and fallbacks.
- [ ] Add token budget limits.
- [ ] Add safe logging rules.
- [ ] Run security and regression tests.

Exit criteria: unsafe retrieved instructions cannot override system behavior and access control is enforced.

---

## Sprint 8 — Performance, Cost, and VPS Deployment

Goal: make the full backend + frontend production-ready on a single VPS.

- [ ] Cache embeddings where safe.
- [ ] Add batch embedding for ingestion.
- [ ] Tune Celery concurrency.
- [ ] Load test retrieval, ingestion, and chat endpoints.
- [ ] Track latency and cost per request.
- [ ] Deploy backend on VPS with Docker Compose.
- [ ] Deploy frontend on same VPS behind Caddy or on Vercel.
- [ ] Add monitoring dashboards and alerts.
- [ ] Add backup/restore procedure.

Exit criteria: app can run reliably on the target VPS with monitoring, backups, and documented deploy steps.

---

## Later / Advanced Sprints

- [ ] Query expansion.
- [ ] Query decomposition.
- [ ] HyDE.
- [ ] Agentic RAG.
- [ ] Multi-modal RAG.
- [ ] GraphRAG / knowledge graph retrieval.
- [ ] LangChain/LlamaIndex integrations only if they clearly reduce complexity.
