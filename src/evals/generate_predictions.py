from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from controllers import NLPController
from evals.run_eval import DEFAULT_DATASET
from evals.schemas import load_golden_dataset
from helpers.config import get_settings
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from stores.llm import LLMProvideFactory
from stores.llm.Templates.template_parser import TemplateParser
from stores.vectordb import VectorDBProviderFactory


def _postgres_url(settings) -> str:
    return (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DB}"
    )


def _page_number(document) -> int | None:
    value = getattr(document, "page_number", None) or (getattr(document, "metadata", {}) or {}).get("page_number") or (getattr(document, "metadata", {}) or {}).get("page")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def generate_predictions(
    *,
    dataset_path: str | Path,
    output_path: str | Path,
    knowledge_base_id: UUID,
    mode: str,
    limit: int,
) -> None:
    settings = get_settings()
    engine = create_async_engine(_postgres_url(settings), echo=False)
    db_client = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    llm_factory = LLMProvideFactory(settings)
    generation_client = llm_factory.create(provider=settings.GENERATION_BACKEND)
    generation_client.set_genration_model(settings.GENERATION_MODEL_ID)
    embedding_client = llm_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, embedding_model_size=settings.EMBEDDING_MODEL_SIZE)

    vector_db_client = VectorDBProviderFactory(config=settings, db_client=db_client).create(provider=settings.VECTOR_DB_BACKEND)
    await vector_db_client.connect()

    try:
        knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=db_client)
        knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)
        controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=TemplateParser(language=settings.PRIMARY_LANGUAGE, default_language=settings.DEFAULT_LANGUAGE),
            db_client=db_client,
            settings=settings,
        )

        records = load_golden_dataset(dataset_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for record in records:
                documents = await controller.search_index(
                    knowledge_base=knowledge_base,
                    text=record.question,
                    limit=limit,
                    strategy=mode,
                )
                citations = []
                page_numbers = []
                for rank, document in enumerate(documents, start=1):
                    page_number = _page_number(document)
                    if page_number is not None:
                        page_numbers.append(page_number)
                    citations.append({
                        "rank": rank,
                        "chunk_id": getattr(document, "chunk_id", None),
                        "page_number": page_number,
                        "score": getattr(document, "score", None),
                        "source": getattr(document, "source", None),
                    })

                prediction = {
                    "id": record.id,
                    "answer": None,
                    "retrieved_chunk_ids": [str(doc.chunk_id) for doc in documents if getattr(doc, "chunk_id", None)],
                    "retrieved_page_numbers": page_numbers,
                    "retrieved_texts": [doc.text for doc in documents],
                    "citations": citations,
                }
                handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    finally:
        await vector_db_client.disconnect()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate retrieval predictions for the offline eval dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--output", required=True)
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--mode", choices=["vector", "bm25", "hybrid"], default="vector")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    asyncio.run(generate_predictions(
        dataset_path=args.dataset,
        output_path=args.output,
        knowledge_base_id=UUID(args.knowledge_base_id),
        mode=args.mode,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
