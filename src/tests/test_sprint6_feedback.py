from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from helpers.config import Settings
from models.AnswerFeedbackDataModel import (
    AnswerFeedbackDataModel,
    AnswerFeedbackSubmission,
)
from models.db_schemes.rag_app_db.schemes import AnswerFeedback
from routes import nlp as nlp_routes
from routes.schemes.nlp import FeedbackRequest
from services.langfuse_service import LangfuseService


def _feedback_submission(*, trace_id: str, rating: str, comment: str | None) -> AnswerFeedbackSubmission:
    return AnswerFeedbackSubmission(
        trace_id=trace_id,
        knowledge_base_id=uuid4(),
        rating=rating,
        comment=comment,
        question="What is retrieval-augmented generation?",
        answer="It combines retrieval with generation.",
        citations=[{"source_id": "source_1", "rank": 1}],
        source_chunks=[{"source_id": "source_1", "text": "source snapshot"}],
        langfuse_status="disabled",
    )


def test_feedback_upsert_inserts_first_submission() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    AnswerFeedback.__table__.create(engine)

    with Session(engine, expire_on_commit=False) as session:
        repository = AnswerFeedbackDataModel(session)

        feedback = repository.upsert(
            _feedback_submission(trace_id="trace-1", rating="thumbs_up", comment="Helpful")
        )

        session.commit()

        assert feedback.trace_id == "trace-1"
        assert feedback.rating == "thumbs_up"
        assert feedback.comment == "Helpful"
        assert session.scalar(select(func.count()).select_from(AnswerFeedback)) == 1

    engine.dispose()


def test_feedback_upsert_updates_existing_trace_without_creating_a_second_row() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    AnswerFeedback.__table__.create(engine)

    with Session(engine, expire_on_commit=False) as session:
        repository = AnswerFeedbackDataModel(session)
        repository.upsert(_feedback_submission(trace_id="trace-1", rating="thumbs_up", comment=None))
        session.commit()

        updated_feedback = repository.upsert(
            AnswerFeedbackSubmission(
                trace_id="trace-1",
                knowledge_base_id=uuid4(),
                rating="thumbs_down",
                comment="Missing detail",
                question="What changes when feedback is revised?",
                answer="The latest feedback snapshot replaces the earlier snapshot.",
                citations=[{"source_id": "source_2", "rank": 1}],
                source_chunks=[{"source_id": "source_2", "text": "updated source snapshot"}],
                langfuse_status="failed",
            )
        )
        session.commit()

        persisted_feedback = session.scalar(
            select(AnswerFeedback).where(AnswerFeedback.trace_id == "trace-1")
        )

        assert session.scalar(select(func.count()).select_from(AnswerFeedback)) == 1
        assert updated_feedback.rating == "thumbs_down"
        assert persisted_feedback is not None
        assert persisted_feedback.comment == "Missing detail"
        assert persisted_feedback.question == "What changes when feedback is revised?"
        assert persisted_feedback.answer == "The latest feedback snapshot replaces the earlier snapshot."
        assert persisted_feedback.citations == [{"source_id": "source_2", "rank": 1}]
        assert persisted_feedback.source_chunks == [{"source_id": "source_2", "text": "updated source snapshot"}]
        assert persisted_feedback.langfuse_status == "failed"

    engine.dispose()


def test_feedback_submission_rejects_invalid_rating() -> None:
    with pytest.raises(ValidationError):
        _feedback_submission(trace_id="trace-1", rating="neutral", comment=None)


def test_feedback_submission_rejects_overlong_comment() -> None:
    with pytest.raises(ValidationError):
        _feedback_submission(trace_id="trace-1", rating="thumbs_up", comment="x" * 2_001)


def test_feedback_submission_rejects_missing_trace_id_and_secret_fields() -> None:
    with pytest.raises(ValidationError):
        AnswerFeedbackSubmission(
            knowledge_base_id=uuid4(),
            rating="thumbs_up",
            question="question",
            answer="answer",
            citations=[],
            source_chunks=[],
        )

    with pytest.raises(ValidationError):
        AnswerFeedbackSubmission(
            trace_id="trace-1",
            rating="thumbs_up",
            question="question",
            answer="answer",
            citations=[],
            source_chunks=[],
        )

    with pytest.raises(ValidationError):
        AnswerFeedbackSubmission(
            trace_id="trace-1",
            knowledge_base_id=uuid4(),
            rating="thumbs_up",
            question="question",
            answer="answer",
            citations=[],
            source_chunks=[],
            api_key="must-not-persist",
        )

    with pytest.raises(ValidationError):
        AnswerFeedbackSubmission(
            trace_id="trace-1",
            knowledge_base_id=uuid4(),
            rating="thumbs_up",
            question="question",
            answer="answer",
            citations=[],
            source_chunks=[],
            full_prompt="must-not-persist",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("citations", [{"source_id": "source_1", "api_key": "must-not-persist"}]),
        ("source_chunks", [{"source_id": "source_1", "text": "snapshot", "full_prompt": "must-not-persist"}]),
    ],
)
def test_feedback_submission_rejects_nested_secret_fields(field: str, value: list[dict[str, str]]) -> None:
    payload = {
        "trace_id": "trace-1",
        "knowledge_base_id": uuid4(),
        "rating": "thumbs_up",
        "question": "question",
        "answer": "answer",
        "citations": [],
        "source_chunks": [],
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        AnswerFeedbackSubmission(**payload)


def test_answer_feedback_migration_downgrade_drops_the_created_table(monkeypatch: pytest.MonkeyPatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "models/db_schemes/rag_app_db/alembic/versions/f1a2b3c4d5e6_add_answer_feedback.py"
    )
    specification = spec_from_file_location("answer_feedback_migration", migration_path)
    assert specification is not None
    assert specification.loader is not None
    migration = module_from_spec(specification)
    specification.loader.exec_module(migration)

    operations: list[tuple[str, str]] = []
    table_comments: dict[str, str | None] = {}

    class FakeOperations:
        def create_table(self, table_name: str, *columns, **kwargs) -> None:
            operations.append(("create_table", table_name))
            table_comments[table_name] = kwargs.get("comment")

        def create_index(self, index_name: str, table_name: str, *columns, **kwargs) -> None:
            operations.append(("create_index", index_name))

        def drop_index(self, index_name: str, table_name: str | None = None) -> None:
            operations.append(("drop_index", index_name))

        def drop_table(self, table_name: str) -> None:
            operations.append(("drop_table", table_name))
            table_comments.pop(table_name, None)

    monkeypatch.setattr(migration, "op", FakeOperations())
    monkeypatch.setattr(migration, "_table_names", lambda: set())
    monkeypatch.setattr(migration, "_index_names", lambda table_name: set())
    monkeypatch.setattr(migration, "_table_comment", lambda table_name: table_comments.get(table_name))
    migration.upgrade()

    monkeypatch.setattr(migration, "_table_names", lambda: {"answer_feedback"})
    monkeypatch.setattr(
        migration,
        "_index_names",
        lambda table_name: {"answer_feedback_knowledge_base_id_index"},
    )
    migration.downgrade()

    assert ("create_table", "answer_feedback") in operations
    assert ("drop_table", "answer_feedback") in operations


def test_answer_feedback_migration_preserves_preexisting_table_when_only_index_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "models/db_schemes/rag_app_db/alembic/versions/f1a2b3c4d5e6_add_answer_feedback.py"
    )
    specification = spec_from_file_location("answer_feedback_migration_stale_state", migration_path)
    assert specification is not None
    assert specification.loader is not None
    migration = module_from_spec(specification)
    specification.loader.exec_module(migration)

    operations: list[tuple[str, str]] = []
    table_names = {"answer_feedback"}
    index_names: set[str] = set()

    class FakeOperations:
        def create_table(self, table_name: str, *columns, **kwargs) -> None:
            operations.append(("create_table", table_name))
            table_names.add(table_name)

        def create_index(self, index_name: str, table_name: str, *columns, **kwargs) -> None:
            operations.append(("create_index", index_name))
            index_names.add(index_name)

        def drop_index(self, index_name: str, table_name: str | None = None) -> None:
            operations.append(("drop_index", index_name))
            index_names.discard(index_name)

        def drop_table(self, table_name: str) -> None:
            operations.append(("drop_table", table_name))
            table_names.discard(table_name)

    monkeypatch.setattr(migration, "op", FakeOperations())
    monkeypatch.setattr(migration, "_table_names", lambda: table_names)
    monkeypatch.setattr(migration, "_index_names", lambda table_name: index_names)
    monkeypatch.setattr(migration, "_table_comment", lambda table_name: None)

    migration.upgrade()
    migration.downgrade()

    assert operations == [
        ("create_index", "answer_feedback_knowledge_base_id_index"),
        ("drop_index", "answer_feedback_knowledge_base_id_index"),
    ]


class _FeedbackSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def run_sync(self, callback):
        return callback(None)


class _RecordingFeedbackRepository:
    def __init__(self) -> None:
        self.submissions: dict[str, AnswerFeedbackSubmission] = {}

    def upsert(self, submission: AnswerFeedbackSubmission) -> AnswerFeedbackSubmission:
        self.submissions[submission.trace_id] = submission
        return submission


class _FailingScoreClient:
    def __init__(self, repository: _RecordingFeedbackRepository) -> None:
        self.repository = repository
        self.persisted_count_when_scored: int | None = None

    def create_score(self, **kwargs) -> None:
        self.persisted_count_when_scored = len(self.repository.submissions)
        raise RuntimeError("Langfuse unavailable")


class _FailingFeedbackRepository:
    def upsert(self, submission: AnswerFeedbackSubmission) -> AnswerFeedbackSubmission:
        raise RuntimeError("database unavailable")


def _feedback_request(knowledge_base_id: str) -> FeedbackRequest:
    return FeedbackRequest(
        trace_id="trace-feedback",
        knowledge_base_id=knowledge_base_id,
        rating="thumbs_up",
        comment="Helpful answer.",
        question="What is retrieval-augmented generation?",
        answer="It combines retrieval with generation.",
        citations=[{"source_id": "source_1", "rank": 1}],
        source_chunks=[{"source_id": "source_1", "rank": 1, "text": "source snapshot"}],
    )


def _feedback_app(langfuse_service: LangfuseService) -> FastAPI:
    app = FastAPI()
    app.db_client = _FeedbackSession
    app.langfuse_service = langfuse_service
    app.include_router(nlp_routes.nlp_router)
    app.dependency_overrides[nlp_routes.get_settings] = lambda: Settings(
        _env_file=None,
        LANGFUSE_ENABLED=False,
    )
    return app


def test_feedback_endpoint_persists_and_returns_disabled_langfuse_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    knowledge_base_id = uuid4()
    repository = _RecordingFeedbackRepository()
    monkeypatch.setattr(nlp_routes, "AnswerFeedbackDataModel", lambda sync_session: repository)
    app = _feedback_app(LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False)))

    # When
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/nlp/index/answer/{knowledge_base_id}/feedback",
            json=_feedback_request(str(knowledge_base_id)).model_dump(mode="json"),
        )

    # Then
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "trace_id": "trace-feedback",
        "rating": "thumbs_up",
        "comment": "Helpful answer.",
        "langfuse_status": "disabled",
        "message": "Feedback saved.",
    }
    assert repository.submissions["trace-feedback"].answer == "It combines retrieval with generation."


def test_feedback_endpoint_returns_success_after_langfuse_scoring_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    knowledge_base_id = uuid4()
    repository = _RecordingFeedbackRepository()
    client = _FailingScoreClient(repository)
    langfuse_service = LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False))
    langfuse_service.client = client
    monkeypatch.setattr(nlp_routes, "AnswerFeedbackDataModel", lambda sync_session: repository)
    app = _feedback_app(langfuse_service)

    # When
    with TestClient(app) as test_client:
        response = test_client.post(
            f"/api/v1/nlp/index/answer/{knowledge_base_id}/feedback",
            json=_feedback_request(str(knowledge_base_id)).model_dump(mode="json"),
        )

    # Then
    assert response.status_code == 200
    assert response.json()["status"] is True
    assert response.json()["langfuse_status"] == "failed"
    assert client.persisted_count_when_scored == 1


def test_feedback_endpoint_rejects_missing_final_answer_snapshot() -> None:
    # Given
    knowledge_base_id = uuid4()
    app = _feedback_app(LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False)))
    payload = _feedback_request(str(knowledge_base_id)).model_dump(mode="json")
    payload.pop("answer")

    # When
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/nlp/index/answer/{knowledge_base_id}/feedback",
            json=payload,
        )

    # Then
    assert response.status_code == 422


@pytest.mark.parametrize("omitted_field", ["citations", "source_chunks"])
def test_feedback_endpoint_rejects_missing_required_snapshot_arrays(omitted_field: str) -> None:
    # Given
    knowledge_base_id = uuid4()
    app = _feedback_app(LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False)))
    payload = _feedback_request(str(knowledge_base_id)).model_dump(mode="json")
    payload.pop(omitted_field)

    # When
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/nlp/index/answer/{knowledge_base_id}/feedback",
            json=payload,
        )

    # Then
    assert response.status_code == 422


def test_feedback_endpoint_does_not_hide_persistence_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    knowledge_base_id = uuid4()
    repository = _FailingFeedbackRepository()
    monkeypatch.setattr(nlp_routes, "AnswerFeedbackDataModel", lambda sync_session: repository)
    app = _feedback_app(LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False)))

    # When
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/v1/nlp/index/answer/{knowledge_base_id}/feedback",
            json=_feedback_request(str(knowledge_base_id)).model_dump(mode="json"),
        )

    # Then
    assert response.status_code == 500
