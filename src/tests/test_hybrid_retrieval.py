from models.db_schemes import RetrievedDocuments
from stores.retrieval import dedupe_retrieved_documents, reciprocal_rank_fusion


def test_reciprocal_rank_fusion_promotes_documents_seen_in_multiple_lists():
    vector = [
        RetrievedDocuments(text="a", score=0.9, chunk_id="a", retrieval_mode="vector"),
        RetrievedDocuments(text="b", score=0.8, chunk_id="b", retrieval_mode="vector"),
    ]
    bm25 = [
        RetrievedDocuments(text="b", score=3.0, chunk_id="b", retrieval_mode="bm25"),
        RetrievedDocuments(text="c", score=2.0, chunk_id="c", retrieval_mode="bm25"),
    ]

    fused = reciprocal_rank_fusion([vector, bm25], k=1)

    assert fused[0].chunk_id == "b"
    assert fused[0].retrieval_mode == "hybrid"


def test_dedupe_retrieved_documents_uses_chunk_id_first():
    documents = [
        RetrievedDocuments(text="first", score=1.0, chunk_id="same"),
        RetrievedDocuments(text="second", score=2.0, chunk_id="same"),
        RetrievedDocuments(text="third", score=1.0, chunk_id="other"),
    ]

    deduped = dedupe_retrieved_documents(documents)

    assert [document.text for document in deduped] == ["first", "third"]
