# Run Commands

Commands for running the RAG application in **production** and **development** modes.

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

```bash
cd docker
docker compose up -d rabbitmq redis pgvector qdrant
```

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

### 11. Sprint 4 migration and re-index after document-processing changes

Sprint 4 adds chunk metadata columns and changes the default chunking strategy. Apply migrations, then reprocess/re-index existing knowledge bases so old chunks are regenerated with page-aware metadata.

```bash
cd src/models/db_schemes/rag_app_db
PYTHONPATH=../../../../ uv run alembic upgrade head
```

Then call the process/index API or Celery workflow for each existing knowledge base with `do_reset=true`.

### 12. Generate a new migration after model changes

```bash
cd src/models/db_schemes/rag_app_db
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```
