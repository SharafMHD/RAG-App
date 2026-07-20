# PI Instructions — RAG App Codebase Context

## Project purpose
This repository is a Python/FastAPI RAG application for uploading documents into projects, processing files into chunks, embedding/indexing chunks into a vector database, and answering user questions using retrieved context plus an LLM.

## Architecture overview
- **API layer:** `src/main.py` creates the FastAPI app, PostgreSQL async SQLAlchemy engine/sessionmaker, LLM providers, vector DB provider, template parser, metrics endpoint, and routers.
- **Routes:** `src/routes/data.py` handles project creation, file upload, file processing, and process+index workflow starts. `src/routes/nlp.py` handles indexing, index info, vector search, and RAG answers. `src/routes/base.py` exposes a welcome endpoint.
- **Controllers:** `src/controllers/` contains file/path validation (`DataController`, `ProjectController`, `BaseController`), file loading/chunking (`ProcessFileController`), and RAG/index orchestration (`NLPController`).
- **Persistence models:** `src/models/*DataModel.py` wrap async SQLAlchemy operations. SQLAlchemy schemas live in `src/models/db_schemes/rag_app_db/schemes/`.
- **Background jobs:** Celery setup is in `src/celery_app.py`; jobs live in `src/tasks/` for file processing, indexing, process/index workflow, and log retention.
- **LLM providers:** Provider interfaces/factory live in `src/stores/llm/`; concrete providers are `Providers/OpenAIProvider.py` and `Providers/CoHereProvider.py`.
- **Prompt templates:** RAG templates are Python `string.Template` modules under `src/stores/llm/Templates/locales/{en,ar}/rag.py`, loaded by `template_parser.py`.
- **Vector stores:** `src/stores/vectordb/` abstracts Qdrant local storage and PGVector/PostgreSQL implementations.
- **Config:** `src/helpers/config.py` uses Pydantic `BaseSettings` and `.env` with defaults for app, Postgres, LLM, vector DB, templates, Celery, and Langfuse.
- **Docker/ops:** `docker/` contains compose files, service env examples, nginx, Prometheus, RabbitMQ, and app Dockerfile.

## RAG-specific flow
1. Upload file to `assets/files/{project_id}/...` and store asset metadata in PostgreSQL.
2. Process file through LangChain loaders (`TextLoader`, `PyMuPDFLoader`) in `ProcessFileController`.
3. Chunking currently uses a custom character splitter (`process_doc_simple_splitter`) with configurable `chunk_size` and `overlap_size`; LangChain `RecursiveCharacterTextSplitter` is present but commented out.
4. Store chunks in PostgreSQL `data_chunks` with source metadata and chunk order.
5. Embed chunk text via the configured LLM provider (`OPENAI` by default, `text-embedding-3-small`, size `1536`).
6. Create/use a collection named `collection_{vector_size}_{project_id}` and insert chunk vectors into Qdrant or PGVector.
7. Search embeds the query, retrieves top-k documents, formats document prompts, appends the query/footer, and generates an answer.

## Coding conventions and patterns
- File and class names are mostly PascalCase for controllers/models (`DataController.py`, `ProjectDataModel.py`) and provider classes; routes/tasks use snake_case modules.
- Most code is async for DB/API boundaries; synchronous loaders and LLM SDK calls are used inside async flows and sometimes wrapped with `asyncio.to_thread`.
- Responses commonly use `JSONResponse` with a boolean `status`, IDs as strings, and message values from `ResponseStatus` enums.
- Logging uses `logging.getLogger("uvicorn.error")`, `logging.getLogger("uvicorn")`, or `logging.getLogger("celery.task")`; avoid `print` in new code.
- Prefer adding configuration to `Settings` rather than scattering model names, limits, paths, or thresholds.
- Prompt text should remain in locale template modules, not inline in controllers/routes.
- There are currently no real tests; `python -m pytest -q` reports no tests.

## Key constraints/defaults
- Python requirement: `>=3.13` in `src/pyproject.toml`.
- Default generation model: `gpt-4o-mini`; default embedding model: `text-embedding-3-small`; default embedding size: `1536`.
- Default vector DB: local Qdrant (`VECTOR_DB_BACKEND=QDRANT`, `VECTOR_DB_PATH=qdrant_data`, `VECTOR_DBS_DIR=assets/vector_dbs`). PGVector provider also exists.
- Default chunk settings: `FILE_DEFAULT_CHUNK_SIZE=512000`, `FILE_OVERLAP_SIZE=5120` (comments say KB/bytes inconsistently; implementation treats values as character counts for splitting and bytes for upload read size).
- Supported upload MIME types include `text/plain`, `application/pdf`, and DOCX MIME type, but processing only supports `.txt` and `.pdf` at present.
- Celery requires broker/result backend config; tasks use queues `default`, `file_processing_queue`, `data_indexing_queue`, and `log_retention_queue`.

## Development commands
- Install/sync: `cd src && uv sync` or `pip install -r requirements.txt`.
- Run API: `cd src && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
- Run migrations: `cd src && alembic upgrade heads`.
- Run worker: `cd src && python -m celery -A celery_app worker -Q default,file_processing_queue,data_indexing_queue,log_retention_queue --loglevel=info`.
- Run beat: `cd src && python -m celery -A celery_app beat --loglevel=info`.
- Run tests/compile check: `cd src && python -m pytest -q`; `cd src && python -m compileall -q .`.

## Guidance for future PI sessions
- Read this file first, then inspect touched modules before editing.
- Do not rewrite the whole app unless asked; make small targeted changes.
- Preserve the existing controller/model/provider separation.
- When fixing bugs, add or update tests where practical because test coverage is currently absent.
- Be careful with existing uncommitted changes and generated/user-uploaded assets under `src/assets/`.
