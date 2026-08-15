from types import SimpleNamespace

from models.db_schemes import RetrievedDocuments
from services.retrieval_context import expand_ranked_documents_with_context


def _chunk(chunk_id: str, order: int, text: str):
    return SimpleNamespace(
        chunk_id=chunk_id,
        chunk_asset_id="asset-1",
        chunk_order=order,
        chunk_content=text,
        chunk_metadata={"page_number": order, "document_name": "guide.pdf"},
    )


def test_expand_ranked_documents_with_context_adds_adjacent_chunks_once():
    anchor_document = RetrievedDocuments(
        text="anchor text",
        score=0.9,
        chunk_id="chunk-2",
        retrieval_mode="hybrid",
    )
    context_chunks = [
        _chunk("chunk-1", 1, "previous context"),
        _chunk("chunk-2", 2, "anchor context"),
        _chunk("chunk-3", 3, "next context"),
    ]

    expanded = expand_ranked_documents_with_context(
        [anchor_document],
        [context_chunks[1]],
        context_chunks,
        neighbor_window=1,
        max_documents=10,
    )

    assert [document.chunk_id for document in expanded] == ["chunk-1", "chunk-2", "chunk-3"]
    assert [document.text for document in expanded] == ["previous context", "anchor context", "next context"]
    assert all(document.score == 0.9 for document in expanded)


def test_expand_ranked_documents_with_context_respects_max_documents():
    anchor_document = RetrievedDocuments(
        text="anchor text",
        score=0.9,
        chunk_id="chunk-2",
        retrieval_mode="hybrid",
    )
    context_chunks = [
        _chunk("chunk-1", 1, "previous context"),
        _chunk("chunk-2", 2, "anchor context"),
        _chunk("chunk-3", 3, "next context"),
    ]

    expanded = expand_ranked_documents_with_context(
        [anchor_document],
        [context_chunks[1]],
        context_chunks,
        neighbor_window=1,
        max_documents=2,
    )

    assert [document.chunk_id for document in expanded] == ["chunk-1", "chunk-2"]
