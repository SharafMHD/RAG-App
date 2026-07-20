## Purpose
This file gives short, actionable guidance to AI coding agents working on this FastAPI/Celery RAG application.

## Repo snapshot
- Root docs/config: `README.md`, `Docs/RunCommands.md`, `.gitignore`, Docker files under `docker/`.
- Application source: `src/` contains FastAPI routes/controllers, Celery tasks, SQLAlchemy models/Alembic files, LLM providers, and vector DB providers.
- Python tooling lives in `src/pyproject.toml`, `src/requirements.txt`, and `src/uv.lock`.
- Agent context lives in `.pi/prompts/PI_Instructions.md`; read it before making broad changes.

## High-priority tasks
1. Keep local/generated data out of git: `.env`, uploaded files, local vector DB files, sqlite/db artifacts, Celery beat schedules, and `__pycache__`.
2. Prefer small fixes with regression tests for processing/indexing, Qdrant/PGVector providers, LLM providers, and route validation.
3. Reconcile docs when changing runtime behavior; current local run commands are centered on `src/` and port `8000`.

## Discovery and validation commands
```zsh
find . -maxdepth 3 -type f | sort
cd src && uv run pytest
cd src && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
cd src && python -m celery -A celery_app worker -Q default,file_processing_queue,data_indexing_queue,log_retention_queue --loglevel=info
```

## Conventions
- Use async/await consistently for FastAPI, SQLAlchemy, and provider interfaces.
- Preserve typo-based public/config names with aliases when renaming incrementally (`FILE_ALLWOED_TYPES`, `FILE_ALLOWED_SZIE`, etc.).
- Keep prompt text in `src/stores/llm/Templates/locales/`.
- Pull settings from `src/helpers/config.py` and `.env` examples rather than hardcoding provider/model/vector values.
