from .BaseController import BaseController
from dataclasses import dataclass
from models.db_schemes import KnowledgeBase , DataChunk, RetrievedDocuments
from stores.llm.LLMEnums import DocumentTypeEums
from stores.retrieval import reciprocal_rank_fusion
from helpers.config import get_settings, Settings
from services.langfuse_service import LangfuseService
from services.prompt_service import PromptBundle, PromptService
from services.query_preprocessing import (
    GenerationClientQueryGenerator,
    QueryPreprocessingMetadata,
    QueryPreprocessingOptions,
    QueryPreprocessingSelection,
    QueryPreprocessingService,
)
from sqlalchemy import select
from typing import List
from uuid import UUID
import json
import math
import re


@dataclass(frozen=True, slots=True)
class SearchIndexResult:
    documents: list[RetrievedDocuments]
    preprocessing: QueryPreprocessingMetadata


@dataclass(frozen=True, slots=True)
class RAGAnswerPreparation:
    full_prompt: str | None
    chat_history: list[dict[str, str]] | None
    retrieved_documents: list[RetrievedDocuments]
    prompt_bundle: PromptBundle | None
    preprocessing: QueryPreprocessingMetadata


class NLPController(BaseController):
    def __init__(self,vector_db_client, generation_client,embedding_client, template_parser, db_client=None, settings: Settings | None = None, prompt_service: PromptService | None = None, langfuse_service: LangfuseService | None = None, query_preprocessor: QueryPreprocessingService | None = None):
        super().__init__()

        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.db_client = db_client
        self.settings = settings or get_settings()
        self.langfuse_service = langfuse_service or LangfuseService(self.settings)
        self.prompt_service = prompt_service or PromptService(self.settings, self.langfuse_service)
        self.query_preprocessor = query_preprocessor or QueryPreprocessingService(GenerationClientQueryGenerator(self.generation_client))

    async def create_collection_name(self, knowledge_base_id:UUID):
        collection_name = f"collection_{self.vector_db_client.default_vector_size}_{knowledge_base_id}".strip().replace(" ","_").lower()
        return collection_name
    
    async def reset_vector_db_collection(self, knowledge_base: KnowledgeBase):
        # 1. Correctly awaited
        collection_name = await self.create_collection_name(str(knowledge_base.knowledge_base_id))
        
        # 2. Match the names in your PGVectorDBProvider.py
        if await self.vector_db_client.is_collection_exists(collection_name):
            await self.vector_db_client.drop_collection(collection_name)
        
        return collection_name

    async def get_vector_db_collection_info(self, knowledge_base:KnowledgeBase):
        collection_name = await self.create_collection_name(str(knowledge_base.knowledge_base_id))
        collection_info = await self.vector_db_client.get_collection_info(collection_name)
        
        return json.loads(
                json.dumps(collection_info , default=lambda o: o.__dict__)
            )
    
    async def index_into_vector_db(self, knowledge_base: KnowledgeBase, data_chunks: List[DataChunk], do_reset: bool = False, chunk_ids: List[int] | None = None):
        if not data_chunks:
            return False

        collection_name = await self.create_collection_name(str(knowledge_base.knowledge_base_id))
        texts = [chunk.chunk_content for chunk in data_chunks]
        metadata = [chunk.chunk_metadata for chunk in data_chunks]
        chunk_ids = chunk_ids or [chunk.chunk_id for chunk in data_chunks]

        vectors = self.embedding_client.embedd_text(
            text=texts,
            document_type=DocumentTypeEums.DOCUMENT.value,
        )
        if not vectors or len(vectors) != len(texts):
            return False

        await self.vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedd_size,
            do_reset=do_reset,
        )

        return await self.vector_db_client.insert_many_vectors(
            collection_name=collection_name,
            texts=texts,
            vectors=vectors,
            metadata=metadata,
            record_ids=chunk_ids,
        )
    
    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[\w\u0600-\u06FF]+", (text or "").lower())

    def _metadata_value(self, metadata: dict, *keys: str):
        for key in keys:
            if key in metadata and metadata[key] is not None:
                return metadata[key]
        return None

    async def search_vector(self, knowledge_base: KnowledgeBase, text: str, limit: int = 5):
         #Step 1: Get or create collection
        query_vector= None
        collection_name = await self.create_collection_name(str(knowledge_base.knowledge_base_id))

        #Step 2: Prepare embedding for search text
        vectors = self.embedding_client.embedd_text(
            text=text, 
            document_type = DocumentTypeEums.QUERY.value
        )

        if not vectors or len(vectors) ==0:
            return []
        
        if isinstance(vectors, list):
            query_vector = vectors[0]
        
        if not query_vector or len(query_vector) == 0:
            return []

        limit = max(1, int(limit or 5))
        

        #Step 3: Search in vector db
        search_results = await self.vector_db_client.search_by_vector(
            collection_name= collection_name,
            query_vector= query_vector,
            limit= limit
        )

        return search_results or []

    async def search_keyword(self, knowledge_base: KnowledgeBase, text: str, limit: int = 5) -> list[RetrievedDocuments]:
        """Simple BM25-like lexical retrieval over stored chunks.

        Uses token overlap with IDF smoothing so it works without extra PostgreSQL
        extensions and remains useful for Arabic legal exact-term queries.
        """
        if self.db_client is None:
            return []

        query_tokens = self._tokenize(text)
        if not query_tokens:
            return []
        query_terms = set(query_tokens)

        async with self.db_client() as session:
            result = await session.execute(
                select(DataChunk).where(DataChunk.chunk_knowledge_base_id == knowledge_base.knowledge_base_id)
            )
            chunks = list(result.scalars().all())

        if not chunks:
            return []

        tokenized_chunks = [self._tokenize(chunk.chunk_content) for chunk in chunks]
        doc_count = len(chunks)
        document_frequency = {
            term: sum(1 for tokens in tokenized_chunks if term in set(tokens))
            for term in query_terms
        }
        avgdl = sum(len(tokens) for tokens in tokenized_chunks) / max(doc_count, 1)
        k1 = 1.5
        b = 0.75

        scored: list[RetrievedDocuments] = []
        for chunk, tokens in zip(chunks, tokenized_chunks):
            if not tokens:
                continue
            score = 0.0
            dl = len(tokens)
            for term in query_terms:
                tf = tokens.count(term)
                if tf == 0:
                    continue
                df = document_frequency.get(term, 0)
                idf = math.log(1 + ((doc_count - df + 0.5) / (df + 0.5)))
                score += idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avgdl))))
            if score <= 0:
                continue
            metadata = chunk.chunk_metadata or {}
            scored.append(RetrievedDocuments(
                text=chunk.chunk_content,
                score=score,
                chunk_id=str(chunk.chunk_id),
                source=self._metadata_value(metadata, "document_name", "file_name", "source"),
                page_number=self._metadata_value(metadata, "page_number", "page"),
                metadata={**metadata, "chunk_id": str(chunk.chunk_id)},
                retrieval_mode="bm25",
            ))

        scored.sort(key=lambda document: document.score, reverse=True)
        return scored[:max(1, int(limit or 5))]

    async def search_index(self, knowledge_base:KnowledgeBase, text: str, limit:int=5, strategy: str | None = None, preprocessing: QueryPreprocessingSelection | None = None):
        result = await self.search_index_with_metadata(knowledge_base, text, limit, strategy, preprocessing)
        return result.documents

    async def search_index_with_metadata(self, knowledge_base:KnowledgeBase, text: str, limit:int=5, strategy: str | None = None, preprocessing: QueryPreprocessingSelection | None = None) -> SearchIndexResult:
        limit = max(1, int(limit or 5))
        strategy = (strategy or ("hybrid" if self.settings.HYBRID_SEARCH_ENABLED else "vector")).lower()
        options = QueryPreprocessingOptions.from_settings(self.settings, preprocessing)
        prepared = await self.query_preprocessor.prepare(text, options)
        ranked_lists = [await self._search_single_query(knowledge_base, query, limit, strategy) for query in prepared.queries]
        documents = ranked_lists[0] if len(ranked_lists) == 1 else reciprocal_rank_fusion(
            ranked_lists,
            k=self.settings.RRF_K,
            top_n=limit,
        )
        return SearchIndexResult(documents, prepared.metadata)

    async def _search_single_query(self, knowledge_base:KnowledgeBase, text: str, limit: int, strategy: str) -> list[RetrievedDocuments]:
        if strategy == "bm25":
            return await self.search_keyword(knowledge_base=knowledge_base, text=text, limit=limit)
        if strategy == "hybrid":
            vector_results = await self.search_vector(knowledge_base=knowledge_base, text=text, limit=self.settings.VECTOR_TOP_K)
            bm25_results = await self.search_keyword(knowledge_base=knowledge_base, text=text, limit=self.settings.BM25_TOP_K)
            return reciprocal_rank_fusion(
                [vector_results, bm25_results],
                k=self.settings.RRF_K,
                top_n=limit or self.settings.HYBRID_TOP_N,
            )
        return await self.search_vector(knowledge_base=knowledge_base, text=text, limit=limit)
    
    async def answer_rag_query(self, knowledge_base:KnowledgeBase, query_text:str, limit:int=10, strategy: str | None = None, preprocessing: QueryPreprocessingSelection | None = None):
        answer, full_prompt, chat_history, retrieved_documents, prompt_bundle, _ = await self.answer_rag_query_with_metadata(
            knowledge_base,
            query_text,
            limit,
            strategy,
            preprocessing,
        )
        return answer, full_prompt, chat_history, retrieved_documents, prompt_bundle

    async def answer_rag_query_with_metadata(self, knowledge_base:KnowledgeBase, query_text:str, limit:int=10, strategy: str | None = None, preprocessing: QueryPreprocessingSelection | None = None):
        preparation = await self.prepare_rag_answer(
            knowledge_base,
            query_text,
            limit,
            strategy,
            preprocessing,
        )
        answer = None
        if preparation.full_prompt and preparation.chat_history:
            answer = self.generation_client.generate_text(
                prompt=preparation.full_prompt,
                chat_history=preparation.chat_history,
            )
        return answer, preparation.full_prompt, preparation.chat_history, preparation.retrieved_documents, preparation.prompt_bundle, preparation.preprocessing

    async def prepare_rag_answer(self, knowledge_base:KnowledgeBase, query_text:str, limit:int=10, strategy: str | None = None, preprocessing: QueryPreprocessingSelection | None = None) -> RAGAnswerPreparation:
        retrieval_result = await self.search_index_with_metadata(
            knowledge_base= knowledge_base,
            text= query_text,
            limit= limit,
            strategy=strategy,
            preprocessing=preprocessing,
        )
        retrieved_documents = retrieval_result.documents
        if not retrieved_documents or len(retrieved_documents) == 0:
            return RAGAnswerPreparation(None, None, retrieved_documents, None, retrieval_result.preprocessing)
        prompt_bundle = self.prompt_service.get_rag_prompt(query_text=query_text)
        system_prompt = prompt_bundle.system_prompt
        documents_prompts = "\n".join([
            "\n".join([
                f"## Source ID: source_{idx + 1}",
                f"### Content: {self.generation_client.process_text(doc.text)}",
            ])
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = prompt_bundle.footer_prompt
        if not system_prompt or not footer_prompt:
            return RAGAnswerPreparation(None, None, retrieved_documents, prompt_bundle, retrieval_result.preprocessing)
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([documents_prompts, footer_prompt])
        return RAGAnswerPreparation(full_prompt, chat_history, retrieved_documents, prompt_bundle, retrieval_result.preprocessing)
