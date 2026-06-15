FROM ghcr.io/astral-sh/uv:0.11.21-python3.12-trixie

WORKDIR /app



# Install additional system dependencies for lxml and other packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libavif-dev pkg-config \
    libjpeg-dev \
    gcc unzip zip \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt .

RUN uv pip install -r requirements.txt --system

COPY src/ .
# Create the directory for the database schemes
RUN mkdir -p models/db_schemes/rag_app_db/
# Copy the alembic.ini file to the appropriate location in the container
COPY docker/rag-app/alembic.ini /app/models/db_schemes/rag_app_db/

COPY docker/rag-app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
