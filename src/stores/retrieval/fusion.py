from __future__ import annotations

from typing import Iterable

from models.db_schemes import RetrievedDocuments


def _document_key(document: RetrievedDocuments) -> str:
    if document.chunk_id:
        return str(document.chunk_id)
    return document.text


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[RetrievedDocuments]],
    *,
    k: int = 60,
    top_n: int | None = None,
) -> list[RetrievedDocuments]:
    """Fuse multiple ranked retrieval lists using Reciprocal Rank Fusion."""
    fused_scores: dict[str, float] = {}
    best_documents: dict[str, RetrievedDocuments] = {}

    for ranked_list in ranked_lists:
        for rank, document in enumerate(ranked_list, start=1):
            key = _document_key(document)
            fused_scores[key] = fused_scores.get(key, 0.0) + (1.0 / (k + rank))
            current_best = best_documents.get(key)
            if current_best is None or (document.score or 0.0) > (current_best.score or 0.0):
                best_documents[key] = document

    fused_documents = []
    for key, document in best_documents.items():
        data = document.model_dump()
        data["score"] = fused_scores[key]
        data["retrieval_mode"] = "hybrid"
        fused_documents.append(RetrievedDocuments(**data))

    fused_documents.sort(key=lambda item: item.score, reverse=True)
    if top_n is not None:
        return fused_documents[:top_n]
    return fused_documents


def dedupe_retrieved_documents(documents: list[RetrievedDocuments]) -> list[RetrievedDocuments]:
    seen: set[str] = set()
    deduped: list[RetrievedDocuments] = []
    for document in documents:
        key = _document_key(document)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(document)
    return deduped
