from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sebastian.memory.types import MemoryDecisionType, MemoryKind, ResolveDecision

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from sebastian.memory.entity_registry import EntityRegistry
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore


async def persist_decision(
    decision: ResolveDecision,
    *,
    session: AsyncSession,
    profile_store: ProfileMemoryStore,
    episode_store: EpisodeMemoryStore,
    entity_registry: EntityRegistry,
) -> None:
    """Route a ResolveDecision to the correct store based on memory kind.

    - DISCARD / EXPIRE → no write (caller still logs).
    - EPISODE / SUMMARY → EpisodeMemoryStore
    - ENTITY → EntityRegistry.upsert_entity
    - RELATION → relation_candidates table
    - FACT / PREFERENCE → ProfileMemoryStore (add or supersede)
    """
    if decision.decision in (MemoryDecisionType.DISCARD, MemoryDecisionType.EXPIRE):
        return
    if decision.new_memory is None:
        raise ValueError("non-DISCARD/EXPIRE decision must have new_memory")

    artifact = decision.new_memory
    kind = artifact.kind

    if kind == MemoryKind.EPISODE:
        await episode_store.add_episode(artifact)
        return
    if kind == MemoryKind.SUMMARY:
        await episode_store.add_summary(artifact)
        return
    if kind == MemoryKind.ENTITY:
        payload = artifact.structured_payload or {}
        await entity_registry.upsert_entity(
            canonical_name=payload.get("canonical_name", artifact.content),
            entity_type=payload.get("entity_type", "unknown"),
            aliases=payload.get("aliases", []),
            metadata=payload.get("metadata", {}),
        )
        return
    if kind == MemoryKind.RELATION:
        from sebastian.store.models import RelationCandidateRecord

        payload = artifact.structured_payload or {}
        session.add(
            RelationCandidateRecord(
                id=artifact.id or str(uuid4()),
                subject_id=artifact.subject_id,
                predicate=payload.get("predicate", ""),
                source_entity_id=payload.get("source_entity_id"),
                target_entity_id=payload.get("target_entity_id"),
                content=artifact.content,
                structured_payload=payload,
                confidence=artifact.confidence,
                status=artifact.status.value,
                provenance=artifact.provenance,
                created_at=artifact.recorded_at,
            )
        )
        await session.flush()
        return

    # FACT / PREFERENCE
    if decision.decision == MemoryDecisionType.SUPERSEDE:
        await profile_store.supersede(decision.old_memory_ids, artifact)
    else:
        await profile_store.add(artifact)
