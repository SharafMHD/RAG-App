# Run Commands

Commands for running the RAG application in **production** and **development** modes.

## One-command development startup

From the repository root, start the full development stack with:

```bash
./dev
```

The script starts Docker infrastructure, including Langfuse, runs Alembic migrations, then starts Celery worker, Celery beat, Flower, FastAPI, and the Next.js frontend. Logs are written to `.dev-logs/`. Press `Ctrl+C` to stop app processes; Docker services are left running. To skip Flower, run `START_FLOWER=0 ./dev`. To skip Langfuse, run `START_LANGFUSE=0 ./dev`.

## Production

Production should run through Docker Compose so FastAPI, Celery, Redis, RabbitMQ, PostgreSQL/PGVector, Qdrant, Prometheus, Grafana, Flower, and Nginx use the same network and environment.

### 1. Prepare environment files

```bash
cd docker/env
cp .env.example.app .env.app
cp .env.example.postgres .env.postgres
cp .env.example.rabbitmq .env.rabbitmq
cp .env.example.redis .env.redis
cp .env.example.garfana .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter
cp .env.example.langfuse .env.langfuse
```

Edit the copied files and set real secrets/credentials before starting services.

### 2. Validate Compose configuration

```bash
cd docker
docker compose config --quiet
```

### 3. Build and start the production stack

```bash
docker compose up --build -d
```

The application entrypoint runs Alembic migrations with a PostgreSQL advisory lock before each service starts.

### 4. Check service health

```bash
docker ps
curl -fsS http://localhost/api/v1/health
curl -fsS http://localhost/api/v1/welcome
```

Expected core services should be `Up` or `healthy`:

```text
fastapi
nginx
celery-worker
celery-beat
flower
rabbitmq
redis
pgvector
qdrant
prometheus
grafana
```

### 5. View logs

```bash
docker compose logs -f fastapi celery-worker celery-beat flower nginx
```

### 6. Stop the stack

```bash
docker compose down
```

To remove volumes too, only when you intentionally want to delete persisted data:

```bash
docker compose down -v --remove-orphans
```

### 7. Langfuse observability

Langfuse is included in the main Docker Compose stack. It reuses the existing `pgvector` PostgreSQL server through a dedicated `langfuse` database and reuses the existing `redis` service. Langfuse still needs its own ClickHouse and MinIO services.

```bash
cd docker
docker compose up -d langfuse-web langfuse-worker
curl -fsS http://localhost:3001/api/public/health
```

## Development

Development runs app services locally from `src/` while infrastructure dependencies run in Docker.

### 1. Prepare Python environment

```bash
cd src
uv sync
cp .env.example .env
```

Edit `src/.env` with local settings and API keys if you need real LLM calls.

### 2. Start infrastructure dependencies

Docker Desktop/daemon must be running before starting these services.

```bash
cd docker
docker compose up -d rabbitmq redis pgvector qdrant
```

If FastAPI starts but `/api/v1/health` returns `503` with `database: error`, PostgreSQL is not reachable. Start Docker Desktop and rerun the Compose command above.

### 3. Run database migrations

```bash
cd src/models/db_schemes/rag_app_db
alembic upgrade head
```

### 4. Start FastAPI with reload

```bash
cd src
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start Celery worker

Run in a separate terminal:

```bash
cd src
uv run python -m celery -A celery_app worker \
  --queues=default,file_processing_queue,data_indexing_queue,log_retention_queue \
  --loglevel=info \
  -E
```

### 6. Start Celery Beat

Run in a separate terminal:

```bash
cd src
uv run python -m celery -A celery_app beat --loglevel=info
```

### 7. Start Flower

Run in a separate terminal:

```bash
cd src
uv run python -m celery -A celery_app flower --conf=FlowerConfig.py
```

### 8. Verify local app

```bash
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:8000/api/v1/welcome
curl -fsS http://localhost:8000/metrics | head
```

### 9. Create a knowledge base

```bash
curl -X POST http://localhost:8000/api/v1/data/knowledge-bases/create \
  -H 'Content-Type: application/json' \
  -d '{"knowledge_base_name":"local-demo","description":"Local test knowledge base"}'
```

### 10. Run tests

```bash
cd src
uv run python -m pytest -q
```

### 11. Admin knowledge-base routes and UI

Admin UI routes:

```text
http://localhost:3000/admin/knowledge-bases
http://localhost:3000/admin/settings
```

These temporary admin API endpoints do not require API-key auth or permission checks, even when `REQUIRE_API_KEY=true`:

```bash
# Create knowledge base
curl -X POST http://localhost:8000/api/v1/admin/knowledge-bases/create \
  -H 'Content-Type: application/json' \
  -d '{"knowledge_base_name":"admin-demo","description":"Admin-created KB","owner":"admin"}'

# Process and index existing knowledge base
curl -X POST http://localhost:8000/api/v1/admin/knowledge-bases/{knowledge_base_id}/process \
  -H 'Content-Type: application/json' \
  -d '{"file_id":null,"chunk_size":900,"overlap_size":150,"do_reset":true}'

# Create KB, upload one file, then process and index
curl -X POST http://localhost:8000/api/v1/admin/knowledge-bases/create-and-process \
  -F 'knowledge_base_name=admin-upload-demo' \
  -F 'description=Created and processed from admin route' \
  -F 'owner=admin' \
  -F 'do_reset=true' \
  -F 'file=@/path/to/document.pdf'

# Poll Celery task status
curl http://localhost:8000/api/v1/admin/tasks/{workflow_task_id}
```

### 12. Sprint 4 migration and re-index after document-processing changes

Sprint 4 adds chunk metadata columns and changes the default chunking strategy. Apply migrations, then reprocess/re-index existing knowledge bases so old chunks are regenerated with page-aware metadata.

```bash
cd src/models/db_schemes/rag_app_db
PYTHONPATH=../../../../ uv run alembic upgrade head
```

Then call the process/index API or Celery workflow for each existing knowledge base with `do_reset=true`.

### 13. Run the Next.js chat frontend

Run in a separate terminal while FastAPI is available:

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm run dev
```

`pnpm run dev` cleans `.next` before starting to avoid stale Next.js chunk errors such as `Cannot find module './617.js'` after route/file changes.

Open:

```text
http://localhost:3000
```

If backend API-key protection is enabled, set `NEXT_PUBLIC_API_KEY` in `frontend/.env.local`.

### 14. Generate a new migration after model changes

```bash
cd src/models/db_schemes/rag_app_db
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```
