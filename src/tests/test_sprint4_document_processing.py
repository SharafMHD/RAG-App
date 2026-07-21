from dataclasses import dataclass

from services.document_processing import ChunkingConfig, PageAwareRecursiveChunker, clean_extracted_text


@dataclass
class DummyPage:
    page_content: str
    metadata: dict


def test_clean_extracted_text_preserves_arabic_and_normalizes_spacing():
    text = "  المؤمن\tعليه\r\n\r\n\r\nصاحب   العمل  "

    assert clean_extracted_text(text) == "المؤمن عليه\n\nصاحب العمل"


def test_page_aware_chunker_preserves_page_and_version_metadata():
    chunker = PageAwareRecursiveChunker(
        ChunkingConfig(
            chunk_size=40,
            chunk_overlap=5,
            min_chunk_chars=1,
            chunking_strategy="page_recursive_v1",
            embedding_model="text-embedding-test",
        )
    )
    chunks = chunker.split(
        [
            DummyPage(
                page_content="المؤمن عليه هو كل شخص تسري عليه أحكام هذا القانون. صاحب العمل جهة العمل.",
                metadata={"page_number": 11, "document_name": "law.pdf"},
            )
        ]
    )

    assert len(chunks) >= 2
    assert chunks[0].metadata["page_number"] == 11
    assert chunks[0].metadata["document_name"] == "law.pdf"
    assert chunks[0].metadata["chunk_index"] == 1
    assert chunks[0].metadata["chunking_strategy"] == "page_recursive_v1"
    assert chunks[0].metadata["embedding_model"] == "text-embedding-test"
    assert len(chunks[0].metadata["content_hash"]) == 64
    assert chunks[0].metadata["parent_chunk_id"] is None


def test_page_aware_chunker_skips_empty_pages_and_retains_page_numbers():
    chunker = PageAwareRecursiveChunker(ChunkingConfig(chunk_size=100, chunk_overlap=0, min_chunk_chars=1))

    chunks = chunker.split(
        [
            DummyPage(page_content="", metadata={"page_number": 1}),
            DummyPage(page_content="نص الصفحة الثانية", metadata={"page_number": 2, "source": "doc.txt"}),
        ]
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["page_number"] == 2
    assert chunks[0].metadata["source"] == "doc.txt"
