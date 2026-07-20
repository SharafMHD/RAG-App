from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any, Iterator
from uuid import uuid4

from helpers.config import Settings


class LangfuseService:
    """Small optional Langfuse wrapper.

    The rest of the app can request trace IDs and tracing contexts without
    caring whether Langfuse is configured. When disabled or misconfigured this
    service behaves as a no-op and still returns local UUID trace IDs.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self.enabled = bool(
            settings.LANGFUSE_ENABLED
            and settings.langfuse_public_key
            and settings.langfuse_secret_key
        )
        if not self.enabled:
            return

        try:
            from langfuse import Langfuse

            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_base_url,
                environment=settings.LANGFUSE_ENVIRONMENT,
                release=settings.LANGFUSE_RELEASE,
                sample_rate=settings.LANGFUSE_TRACE_SAMPLE_RATE,
            )
        except Exception:
            self.client = None
            self.enabled = False

    def create_trace_id(self) -> str:
        if self.client and hasattr(self.client, "create_trace_id"):
            try:
                return self.client.create_trace_id()
            except Exception:
                pass
        return str(uuid4())

    @contextmanager
    def trace_answer(self, trace_id: str, *, input: Any = None, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
        if not self.client:
            yield None
            return

        try:
            from langfuse.types import TraceContext

            with self.client.start_as_current_observation(
                name="rag-answer",
                as_type="generation",
                trace_context=TraceContext(trace_id=trace_id),
                input=input,
                metadata=metadata or {},
                model=self.settings.GENERATION_MODEL_ID,
                model_parameters={
                    "temperature": self.settings.DEFAULT_GENERATION_TEMPERATURE,
                    "max_output_tokens": self.settings.DEFAULT_OUTPUT_MAX_TOKENS,
                },
            ) as observation:
                yield observation
        except Exception:
            yield None

    def flush(self) -> None:
        if self.client and hasattr(self.client, "flush"):
            try:
                self.client.flush()
            except Exception:
                pass
