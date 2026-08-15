from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_schemes import DataChunk, RetrievedDocuments


type AsyncSessionContext = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class ContextChunk(Protocol):
    chunk_id: UUID
    chunk_asset_id: UUID
    chunk_order: int
    chunk_content: str
    chunk_metadata: dict[str, JsonValue] | None


async def expand_with_adjacent_chunks(
    db_client: AsyncSessionContext | None,
    knowledge_base_id: UUID,
    documents: list[RetrievedDocuments],
    *,
    neighbor_window: int = 1,
    max_documents: int = 10,
) -> list[RetrievedDocuments]:
    if db_client is None or not documents:
        return documents

    anchor_ids = [document.chunk_id for document in documents if document.chunk_id]
    if not anchor_ids:
        return documents

    async with db_client() as session:
        anchor_result = await session.execute(
            select(DataChunk).where(
                DataChunk.chunk_knowledge_base_id == knowledge_base_id,
                DataChunk.chunk_id.in_(anchor_ids),
            )
        )
        anchor_chunks = list(anchor_result.scalars().all())
        if not anchor_chunks:
            return documents

        context_result = await session.execute(
            select(DataChunk)
            .where(
                DataChunk.chunk_knowledge_base_id == knowledge_base_id,
                or_(*[
                    and_(
                        DataChunk.chunk_asset_id == chunk.chunk_asset_id,
                        DataChunk.chunk_order >= chunk.chunk_order - neighbor_window,
                        DataChunk.chunk_order <= chunk.chunk_order + neighbor_window,
                    )
                    for chunk in anchor_chunks
                ]),
            )
            .order_by(DataChunk.chunk_asset_id.asc(), DataChunk.chunk_order.asc())
        )
        context_chunks = list(context_result.scalars().all())

    return expand_ranked_documents_with_context(
        documents,
        anchor_chunks,
        context_chunks,
        neighbor_window=neighbor_window,
        max_documents=max_documents,
    )


def expand_ranked_documents_with_context(
    documents: list[RetrievedDocuments],
    anchor_chunks: list[ContextChunk],
    context_chunks: list[ContextChunk],
    *,
    neighbor_window: int,
    max_documents: int,
) -> list[RetrievedDocuments]:
    anchors_by_id = {str(chunk.chunk_id): chunk for chunk in anchor_chunks}
    context_by_asset = _group_context_chunks(context_chunks)
    expanded: list[RetrievedDocuments] = []
    seen: set[str] = set()

    for document in documents:
        anchor = anchors_by_id.get(str(document.chunk_id))
        if anchor is None:
            _append_document(expanded, seen, document, max_documents)
            continue

        group = [
            chunk
            for chunk in context_by_asset.get(str(anchor.chunk_asset_id), [])
            if anchor.chunk_order - neighbor_window <= chunk.chunk_order <= anchor.chunk_order + neighbor_window
        ]
        for chunk in sorted(group, key=lambda item: item.chunk_order):
            _append_document(
                expanded,
                seen,
                _document_from_chunk(chunk, anchor_document=document),
                max_documents,
            )

    return expanded


def format_documents_for_prompt(documents: list[RetrievedDocuments]) -> str:
    return "\n".join(
        f"## Source ID: source_{idx + 1}\n### Content: {document.text}"
        for idx, document in enumerate(documents)
    )


def _group_context_chunks(chunks: list[ContextChunk]) -> dict[str, list[ContextChunk]]:
    grouped: dict[str, list[ContextChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(str(chunk.chunk_asset_id), []).append(chunk)
    return grouped


def _append_document(
    documents: list[RetrievedDocuments],
    seen: set[str],
    document: RetrievedDocuments,
    max_documents: int,
) -> None:
    if len(documents) >= max_documents:
        return
    key = document.chunk_id or document.text
    if key in seen:
        return
    seen.add(key)
    documents.append(document)


def _document_from_chunk(chunk: ContextChunk, *, anchor_document: RetrievedDocuments) -> RetrievedDocuments:
    metadata = dict(chunk.chunk_metadata or {})
    metadata["chunk_id"] = str(chunk.chunk_id)
    page_number = _metadata_value(metadata, "page_number", "page")
    source = _metadata_value(metadata, "document_name", "file_name", "source")
    return RetrievedDocuments(
        text=chunk.chunk_content,
        score=anchor_document.score,
        chunk_id=str(chunk.chunk_id),
        source=str(source) if source is not None else None,
        page_number=page_number if isinstance(page_number, int) else None,
        metadata=metadata,
        retrieval_mode=anchor_document.retrieval_mode,
    )


def _metadata_value(metadata: dict[str, JsonValue], *keys: str) -> JsonValue | None:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None
