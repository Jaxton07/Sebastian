from __future__ import annotations

import pytest

from sebastian.memory.contracts.retrieval import (
    ExplicitMemorySearchRequest,
    ExplicitMemorySearchResult,
    PromptMemoryRequest,
    PromptMemoryResult,
)
from sebastian.memory.contracts.writing import MemoryWriteRequest, MemoryWriteResult
from sebastian.memory.services.retrieval import MemoryRetrievalService


def test_prompt_memory_request_defaults_dedupe_sets() -> None:
    request = PromptMemoryRequest(
        session_id="sess-1",
        agent_type="sebastian",
        user_message="我喜欢什么",
        subject_id="user:owner",
    )
    assert request.resident_record_ids == set()
    assert request.resident_dedupe_keys == set()
    assert request.resident_canonical_bullets == set()


def test_prompt_memory_result_instantiation() -> None:
    result = PromptMemoryResult(section="## 记忆\n- 喜欢咖啡")
    assert result.section == "## 记忆\n- 喜欢咖啡"


def test_explicit_memory_search_request_default_limit() -> None:
    request = ExplicitMemorySearchRequest(
        query="咖啡",
        session_id="sess-1",
        agent_type="sebastian",
        subject_id="user:owner",
    )
    assert request.limit == 5


def test_explicit_memory_search_result_instantiation() -> None:
    result = ExplicitMemorySearchResult(items=[{"id": "m1", "content": "喜欢咖啡"}])
    assert len(result.items) == 1


def test_memory_write_result_defaults() -> None:
    result = MemoryWriteResult()
    assert result.decisions == []
    assert result.proposed_slots_registered == []
    assert result.proposed_slots_rejected == []
    assert result.saved_count == 0
    assert result.discarded_count == 0


@pytest.mark.asyncio
async def test_retrieval_service_delegates_prompt_retrieval(db_session, monkeypatch) -> None:
    captured = {}

    async def fake_retrieve(context, *, db_session):
        captured["context"] = context
        return "## Memory\n- [fact] hello"

    monkeypatch.setattr("sebastian.memory.services.retrieval.retrieve_memory_section", fake_retrieve)

    service = MemoryRetrievalService()
    result = await service.retrieve_for_prompt(
        PromptMemoryRequest(
            session_id="sess-1",
            agent_type="sebastian",
            user_message="hello",
            subject_id="user:owner",
        ),
        db_session=db_session,
    )

    assert result.section == "## Memory\n- [fact] hello"
    assert captured["context"].access_purpose == "context_injection"


@pytest.mark.asyncio
async def test_retrieval_service_search_returns_empty_on_no_data(db_session, monkeypatch) -> None:
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "sebastian.memory.profile_store.ProfileMemoryStore.search_active",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "sebastian.memory.profile_store.ProfileMemoryStore.search_recent_context",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "sebastian.memory.episode_store.EpisodeMemoryStore.search_summaries_by_query",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "sebastian.memory.episode_store.EpisodeMemoryStore.search_episodes_only",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "sebastian.memory.entity_registry.EntityRegistry.list_relations",
        AsyncMock(return_value=[]),
    )

    service = MemoryRetrievalService()
    result = await service.search(
        ExplicitMemorySearchRequest(
            query="咖啡",
            session_id="sess-1",
            agent_type="sebastian",
            subject_id="user:owner",
        ),
        db_session=db_session,
    )

    assert isinstance(result, ExplicitMemorySearchResult)
    assert result.items == []
