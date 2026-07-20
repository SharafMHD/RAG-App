# Local Development Execution Commands

This guide provides the exact terminal commands required to run the core dependencies, workers, background schedulers, API server, and database migrations for the RAG application.

### 1. External Infrastructure (Docker Dependencies)
Spin up the background broker environments, internal caching services, and the vector storage instance:
```bash
docker compose up rabbitmq redis pgvector
```

### 2. Async Workers (Celery)
Launch the primary background task processing daemon, monitoring all designated task processing queues:
```bash
python -m celery -A celery_app worker -Q default,file_processing_queue,data_indexing_queue,log_retention_queue -E
```

### 3. Background Task Scheduler (Celery Beat)
Execute the background heartbeat cron scheduler in a standalone terminal to handle recurring logs or maintenance cleanup plans:
```bash
python -m celery -A celery_app beat --loglevel=info
```

### 4. Cluster Monitoring Dashboard (Flower)
Boot up the tracking web dashboard panel to inspect task distribution performance profiles:
```bash
python -m celery -A celery_app flower --conf=FlowerConfig.py
```

### 5. Application Core API Gateway (FastAPI)
Run the asynchronous web server engine locally with live hot-reloads configured for testing adjustments:
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Relational Database Migrations (Alembic)
Generate delta schemas dynamically based on model changes, and instantly execute target synchronization scripts:
```bash
# Generate the migration script tracking changes
alembic revision --autogenerate -m "create celery task execution table"

# Apply all pending migrations to the local database
alembic upgrade heads
```
