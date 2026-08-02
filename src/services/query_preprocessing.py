from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Literal, Protocol, assert_never

import anyio

from helpers.config import Settings


class QueryGenerationMode(StrEnum):
    DECOMPOSE = "decompose"
    EXPAND = "expand"


type QueryPreprocessingStatus = Literal["disabled", "applied", "fallback"]


class QueryGenerator(Protocol):
    async def generate(self, request: QueryGenerationRequest) -> tuple[str, ...]: ...


class GenerationTextClient(Protocol):
    def generate_text(
        self,
        prompt: str,
        chat_history: list | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str | None: ...


@dataclass(frozen=True, slots=True)
class QueryPreprocessingSelection:
    expand: bool
    decompose: bool
    max_generated_queries: int | None = None


@dataclass(frozen=True, slots=True)
class QueryPreprocessingOptions:
    expand: bool = False
    decompose: bool = False
    max_generated_queries: int = 3
    timeout_seconds: float = 5.0
    max_output_tokens: int = 128

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        selection: QueryPreprocessingSelection | None = None,
    ) -> QueryPreprocessingOptions:
        if selection is None:
            return cls(
                expand=settings.QUERY_EXPANSION_ENABLED,
                decompose=settings.QUERY_DECOMPOSITION_ENABLED,
                max_generated_queries=settings.QUERY_PREPROCESSING_MAX_GENERATED_QUERIES,
                timeout_seconds=settings.QUERY_PREPROCESSING_TIMEOUT_SECONDS,
                max_output_tokens=settings.QUERY_PREPROCESSING_MAX_OUTPUT_TOKENS,
            )
        return cls(
            expand=selection.expand,
            decompose=selection.decompose,
            max_generated_queries=selection.max_generated_queries or settings.QUERY_PREPROCESSING_MAX_GENERATED_QUERIES,
            timeout_seconds=settings.QUERY_PREPROCESSING_TIMEOUT_SECONDS,
            max_output_tokens=settings.QUERY_PREPROCESSING_MAX_OUTPUT_TOKENS,
        )


@dataclass(frozen=True, slots=True)
class QueryGenerationRequest:
    source_query: str
    mode: QueryGenerationMode
    max_generated_queries: int
    timeout_seconds: float
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class QueryPreprocessingMetadata:
    status: QueryPreprocessingStatus
    original_query: str
    generated_queries: tuple[str, ...]

    @property
    def generated_query_count(self) -> int:
        return len(self.generated_queries)


@dataclass(frozen=True, slots=True)
class PreparedQueries:
    queries: tuple[str, ...]
    metadata: QueryPreprocessingMetadata


class GenerationClientQueryGenerator:
    def __init__(self, client: GenerationTextClient):
        self.client = client

    async def generate(self, request: QueryGenerationRequest) -> tuple[str, ...]:
        prompt = _generation_prompt(request)
        generate_text = partial(
            self.client.generate_text,
            prompt=prompt,
            chat_history=[],
            max_output_tokens=request.max_output_tokens,
            temperature=0.0,
        )
        with anyio.fail_after(request.timeout_seconds):
            response = await anyio.to_thread.run_sync(generate_text, abandon_on_cancel=True)
        if response is None:
            raise QueryGenerationFailure()
        return tuple(response.splitlines())


class QueryGenerationFailure(Exception):
    pass


class QueryPreprocessingService:
    def __init__(self, generator: QueryGenerator):
        self.generator = generator

    async def prepare(self, original_query: str, options: QueryPreprocessingOptions) -> PreparedQueries:
        if not options.expand and not options.decompose:
            return _prepared(original_query, (), "disabled")

        generated: list[str] = []
        seen = {" ".join(original_query.split()).casefold()}
        try:
            if options.decompose:
                decomposed = await self._generate(_generation_request(original_query, QueryGenerationMode.DECOMPOSE, options, 0))
                _add_normalized(generated, seen, decomposed, options.max_generated_queries)

            expansion_sources = tuple(generated) if options.decompose else (original_query,)
            if options.expand:
                for source_query in expansion_sources:
                    if len(generated) >= options.max_generated_queries:
                        break
                    expanded = await self._generate(
                        _generation_request(source_query, QueryGenerationMode.EXPAND, options, len(generated))
                    )
                    _add_normalized(generated, seen, expanded, options.max_generated_queries)
        except QueryGenerationFailure:
            return _prepared(original_query, (), "fallback")
        return _prepared(original_query, tuple(generated), "applied")

    async def _generate(self, request: QueryGenerationRequest) -> tuple[str, ...]:
        try:
            return await self.generator.generate(request)
        except Exception as exc:
            raise QueryGenerationFailure() from exc


def _generation_request(
    source_query: str,
    mode: QueryGenerationMode,
    options: QueryPreprocessingOptions,
    generated_count: int,
) -> QueryGenerationRequest:
    return QueryGenerationRequest(
        source_query=source_query,
        mode=mode,
        max_generated_queries=options.max_generated_queries - generated_count,
        timeout_seconds=options.timeout_seconds,
        max_output_tokens=options.max_output_tokens,
    )


def _add_normalized(generated: list[str], seen: set[str], candidates: tuple[str, ...], maximum: int) -> None:
    for candidate in candidates:
        if len(generated) >= maximum:
            return
        normalized = " ".join(candidate.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            generated.append(normalized)


def _prepared(
    original_query: str,
    generated_queries: tuple[str, ...],
    status: QueryPreprocessingStatus,
) -> PreparedQueries:
    return PreparedQueries(
        queries=(original_query, *generated_queries),
        metadata=QueryPreprocessingMetadata(
            status=status,
            original_query=original_query,
            generated_queries=generated_queries,
        ),
    )


def _generation_prompt(request: QueryGenerationRequest) -> str:
    match request.mode:
        case QueryGenerationMode.DECOMPOSE:
            instruction = "Break the query into independent retrieval subqueries."
        case QueryGenerationMode.EXPAND:
            instruction = "Generate alternative retrieval phrasings for the query."
        case unreachable:
            assert_never(unreachable)
    return f"{instruction}\nReturn at most {request.max_generated_queries} plain lines.\nQuery: {request.source_query}"
