## Docker:  
docker compose up rabbitmq redis pgvector
## Celery : 
python -m celery -A celery_app worker -Q default,file_processing_queue,data_indexing_queue -E

## Flower: 
python -m celery -A celery_app flower --conf=FlowerConfig.py

## FastAPI App
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000