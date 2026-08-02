from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Final, Literal, assert_never
from uuid import uuid4

from pydantic import JsonValue

from helpers.config import Settings

type FeedbackRating = Literal["thumbs_up", "thumbs_down"]
type LangfuseScoreStatus = Literal["disabled", "sent", "failed"]

FEEDBACK_SCORE_NAME: Final = "answer_feedback"


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
        except Exception:  # noqa: BLE001  # BROAD_EXCEPT_OK
            self.client = None
            self.enabled = False

    def create_trace_id(self) -> str:
        if self.client and hasattr(self.client, "create_trace_id"):
            try:
                return self.client.create_trace_id()
            except Exception:  # noqa: BLE001  # BROAD_EXCEPT_OK
                return str(uuid4())
        return str(uuid4())

    def score_feedback(
        self,
        trace_id: str,
        rating: FeedbackRating,
        *,
        comment: str | None = None,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> LangfuseScoreStatus:
        """Forward an answer rating to Langfuse without affecting persistence."""
        if self.client is None:
            return "disabled"

        match rating:
            case "thumbs_up":
                score = 1.0
            case "thumbs_down":
                score = 0.0
            case unreachable:
                assert_never(unreachable)

        try:
            score_result = self.client.create_score(
                name=FEEDBACK_SCORE_NAME,
                value=score,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=comment,
                metadata=metadata,
            )
            if score_result is not None:
                return "failed"
            flush = getattr(self.client, "flush", None)
            if callable(flush):
                flush()
        except Exception:  # noqa: BLE001  # BROAD_EXCEPT_OK
            return "failed"
        return "sent"

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
        except Exception:  # noqa: BLE001  # BROAD_EXCEPT_OK
            yield None

    def flush(self) -> None:
        if self.client and hasattr(self.client, "flush"):
            try:
                self.client.flush()
            except Exception:  # noqa: BLE001  # BROAD_EXCEPT_OK
                return
