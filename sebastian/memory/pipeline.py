from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sebastian.memory.errors import InvalidCandidateError
from sebastian.memory.resolver import resolve_candidate
from sebastian.memory.subject import resolve_subject
from sebastian.memory.types import MemoryDecisionType, ResolveDecision
from sebastian.memory.write_router import persist_decision

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from sebastian.memory.decision_log import MemoryDecisionLogger
    from sebastian.memory.entity_registry import EntityRegistry
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.memory.slots import SlotRegistry
    from sebastian.memory.types import CandidateArtifact


async def process_candidates(
    candidates: list[CandidateArtifact],
    *,
    session_id: str,
    agent_type: str,
    db_session: AsyncSession,
    profile_store: ProfileMemoryStore,
    episode_store: EpisodeMemoryStore,
    entity_registry: EntityRegistry,
    decision_logger: MemoryDecisionLogger,
    slot_registry: SlotRegistry,
    worker_id: str,
    model_name: str | None,
    rule_version: str,
    input_source: dict[str, Any],
) -> list[ResolveDecision]:
    """Process candidate artifacts through the full write pipeline.

    For each candidate:
    1. Resolve subject_id from candidate.scope + session context
    2. Validate against slot registry (DISCARD + log on failure)
    3. Resolve against existing memories (ADD/SUPERSEDE/MERGE/DISCARD)
    4. Persist non-DISCARD decisions
    5. Append to decision log

    Returns all ResolveDecision objects including DISCARDs.
    Does NOT handle EXPIRE actions — those stay inline in the caller.
    Does NOT commit db_session — caller is responsible.
    """
    decisions: list[ResolveDecision] = []

    for candidate in candidates:
        subject_id = await resolve_subject(
            candidate.scope,
            session_id=session_id,
            agent_type=agent_type,
        )
        try:
            slot_registry.validate_candidate(candidate)
        except InvalidCandidateError as e:
            decision = ResolveDecision(
                decision=MemoryDecisionType.DISCARD,
                reason=f"validate: {e}",
                old_memory_ids=[],
                new_memory=None,
                candidate=candidate,
                subject_id=subject_id,
                scope=candidate.scope,
                slot_id=candidate.slot_id,
            )
            await decision_logger.append(
                decision,
                worker=worker_id,
                model=model_name,
                rule_version=rule_version,
                input_source=input_source,
            )
            decisions.append(decision)
            continue

        decision = await resolve_candidate(
            candidate,
            subject_id=subject_id,
            profile_store=profile_store,
            slot_registry=slot_registry,
            episode_store=episode_store,
        )

        if decision.decision != MemoryDecisionType.DISCARD and decision.new_memory is not None:
            await persist_decision(
                decision,
                session=db_session,
                profile_store=profile_store,
                episode_store=episode_store,
                entity_registry=entity_registry,
            )

        await decision_logger.append(
            decision,
            worker=worker_id,
            model=model_name,
            rule_version=rule_version,
            input_source=input_source,
        )
        decisions.append(decision)

    return decisions
