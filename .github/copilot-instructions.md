## Purpose
This file gives short, actionable guidance to AI coding agents working on this repository so they can be productive immediately.

## Repo snapshot (discovered)
- `README.md` — high-level project description (one-line, contains typos).
- `.LICENSE` — license file present.
- `.gitignore` — git ignore rules.

Current README excerpt (line 2):
```
This is a copmerhensive rag app with pwoer of llm
```

Suggested quick fix (one-line):
"This is a comprehensive RAG app powered by an LLM."

## High-priority tasks for an AI agent
1. Fix obvious documentation issues first. Update `README.md` to correct typos and expand the one-line description so humans know expected language/runtime.
   - Example edit: replace the exact line above with the suggested sentence.
2. Detect the project language and tooling. There are currently no manifest files (e.g., `package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, or `go.mod`) in the repo root — confirm by searching (commands below).
3. If the user expects a RAG implementation, propose a minimal scaffold and create it only after confirmation: `src/`, `ingest/`, `vectorstore/`, `api/`, `tests/`, and a minimal `README` usage section.

## How to discover build / test / run commands (do this before making assumptions)
Run these in the repo root to locate common manifests and CI configs:
```zsh
ls -la
grep -R "package.json\|pyproject.toml\|requirements.txt\|Pipfile\|go.mod\|Dockerfile\|Makefile" -n || true
ls .github || true
```

If CI exists under `.github/workflows`, read workflow files for build/test steps and tool versions.

## Project-specific notes (what an agent should assume from current contents)
- No source code found in the repository root — treat this as a documentation-first repo until more files are added.
- Because the repository title is "RAG APP", prefer suggesting RAG-relevant scaffolding (ingestion -> vector store -> LLM client -> API/UI) but do not implement it without user confirmation.

## Conventions and patterns to follow when adding code
- Use a single top-level language/environment. Ask the owner which language they want (Python or Node.js are common for RAG apps).
- If scaffolding Python: create `pyproject.toml` or `requirements.txt`, a `src/` package, a `scripts/` entrypoint, and a `tests/` folder using `pytest`.
- If scaffolding Node.js: create `package.json`, `src/`, and `tests/` with `vitest` or `jest` depending on user preference.

## Pull request and commit guidance
- Make small, focused commits. When fixing docs, one commit that updates `README.md` is sufficient.
- Include a short changelog entry in `README.md` or `CHANGELOG.md` when adding project scaffolding.

## When you need clarification
- If manifests or source code are missing, ask the user: "Which language/runtime do you want for this RAG app?" and "Do you want me to scaffold a minimal project now?"

## Why these instructions matter
They keep the agent from guessing at the build system or inserting an opinionated scaffold without confirmation. The repo currently only contains documentation and metadata, so the highest value is small, verifiable changes (docs fixes) and discovery steps.

---
If any of these points are unclear or you want a different starting task (scaffold Python/Node, add CI, or implement an ingestion example), tell me which and I will proceed.
