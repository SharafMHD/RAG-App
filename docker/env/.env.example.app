APP_NAME="RAG-APP v1"
APP_VERSION="0.2.1"
ENVIRONMENT="development"

FILE_ALLWOED_TYPES=["text/plain", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
FILE_ALLOWED_SZIE=10 # in MB
UPLOAD_DIR= "assets/files"
FILE_DEFAULT_CHUNK_SIZE=512000 # in kb
FILE_OVERLAP_SIZE=5120 # in kb

#MONGODB_URL="mongodb://admin:admin@localhost:27017"
#MONGODB_DB_NAME="rag_app_db"
#========================= Postgres Config =========================
POSTGRES_HOST="localhost"
POSTGRES_PORT=5400
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="admin"
POSTGRES_MAIN_DB="rag_app_db"
# ========================= LLM Config =========================
GENERATION_BACKEND = "OPENAI"
EMBEDDING_BACKEND = "OPENAI"

OPENAI_BASE_URL=https://api.openai.com/v1/
OPENAI_API_KEY="sk-proj-"
COHERE_API_KEY="m8-"
# GENERATION_MODEL_ID_LITERAL = ["gpt-4o-mini", "gpt-3.5-turbo", "cohere-command-xlarge"]
GENERATION_MODEL_ID="gpt-4o-mini"
# EMBEDDING_MODEL_ID_LITERAL = ["text-embedding-3-small", "text-embedding-2-small", "text-embedding-ada-002"]
EMBEDDING_MODEL_ID="text-embedding-3-small"
EMBEDDING_MODEL_SIZE=1536

DEFAULT_INPUT_MAX_TOKENS=5000
DEFAULT_OUTPUT_MAX_TOKENS=200
DEFAULT_GENERATION_TEMPERATURE=0.1

# ========================= Vector DB Config =========================
# VECTOR_DB_BACKEND_LITERAL = ["PGVECTOR" , "QDRANT"]
VECTOR_DB_BACKEND = "PGVECTOR"
VECTOR_DB_PATH = "qdrant_db"
VECTOR_DB_DISTANCE_METHOD = "cosine"
PGVECTOR_INDEX_THREADHOLD = 100

#======================== Langfuse Config =========================
LANGFUSE_SECRET_KEY="sk-lf-"
LANGFUSE_PUBLIC_KEY="pk-lf-"
LANGFUSE_BASE_URL="http://host.docker.internal:3001"

#======================== Celery Config =========================
CELERY_BROKER_URL="amqp://rag_app_user:RAG_APP_PWD@rabbitmq:5672/Rag_App_VHost"    
CELERY_RESULT_BACKEND="redis://:RAG_APP_PWD@redis:6379/0"
CELERY_TASK_SERIALIZER="json"
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_ACKS_LATE=true
CELERY_WORKER_CONCURRENCY=2
CELERY_FLOWER_PASSWORD="RAG_APP_PWD"