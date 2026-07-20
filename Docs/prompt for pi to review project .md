# Prompt for PI — RAG Codebase Review & Context Setup

## Phase 1: Explore & Understand
Explore my entire codebase (all directories, not just the top level). Before making any judgments, build a clear picture of:

1. **Project structure** — how files/modules are organized (ingestion, chunking, embedding, vector store, retrieval, generation/LLM calls, API layer, utils, config).
2. **Coding patterns & conventions I already use**, including:
   - Naming conventions (functions, variables, files, classes)
   - Error handling style (try/except patterns, custom exceptions, logging approach)
   - How I structure prompts sent to the LLM (are they inline strings, templates, separate files?)
   - How config/env variables are handled
   - How I structure classes vs functions
   - Testing patterns (if any tests exist)
   - Dependency/library choices (e.g., LangChain, LlamaIndex, raw OpenAI/Anthropic SDK, FAISS/Chroma/Pinecone, etc.)
3. **RAG-specific architecture**:
   - Chunking strategy (size, overlap, splitter type)
   - Embedding model(s) used and where
   - Vector store setup and indexing logic
   - Retrieval logic (top-k, filters, re-ranking if any)
   - How retrieved context gets merged into the final prompt
   - Any caching, batching, or async patterns

## Phase 2: Save Context for Future Sessions
Once you understand the codebase, write a `/.pi/PI_Instructions.md` file at the project root summarizing:
- Project purpose and architecture overview
- The coding conventions/patterns identified above (so future sessions follow the same style instead of introducing inconsistent patterns)
- Key file locations and what each does
- Known constraints (e.g., specific model versions, token limits, vector DB used)

This file should be something a future PI Code session can read first to instantly understand how this codebase works and how I like code written.

## Phase 3: Code Review
Now review the codebase specifically for:
1. **Bugs / logic errors** — including RAG-specific issues like off-by-one chunking errors, incorrect top-k handling, silent failures on empty retrieval, mismatched embedding dimensions, etc.
2. **Spelling/grammar issues** — in variable names, docstrings, comments, log messages, and especially in any user-facing strings or prompt templates (spelling mistakes in prompts sent to the LLM can silently degrade output quality).
3. **Edge cases not handled**, such as:
   - Empty or malformed user query
   - No documents retrieved / empty vector store
   - Duplicate or near-duplicate chunks
   - Extremely long input exceeding token limits
   - API failures, timeouts, or rate limits from the LLM or embedding provider
   - Non-UTF8 or corrupted source documents during ingestion
   - Concurrent requests / race conditions if applicable
4. **Hardcoded strings & magic numbers** — especially prompt templates, model names, chunk sizes, and thresholds that should probably be config-driven.
5. **Security/robustness concerns** — e.g., unsanitized input passed into prompts (prompt injection risk), missing input validation, exposed API keys.

## Phase 4: Deliverable
Give me a clean, prioritized report structured as:

1. **Summary** of overall code health and architecture (2-3 sentences)
2. **Critical issues** (bugs/edge cases that could break in production) — with file/line references
3. **Moderate issues** (spelling, unclear naming, inconsistent patterns)
4. **Minor/nice-to-have improvements**
5. **A step-by-step cleanup plan**, ordered by priority, that I can execute incrementally without breaking existing functionality

Do not rewrite the entire codebase yet — just report findings and the plan first, so I can review and confirm before you make changes.