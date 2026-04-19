from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Keywords that trigger each retrieval lane (Phase R-D, spec §2)
PROFILE_LANE_KEYWORDS = ["我", "我的", "我喜欢", "我是", "my", "i am", "i like", "i prefer"]
EPISODE_LANE_KEYWORDS = ["上次", "讨论", "之前", "记得", "last time", "remember", "we discussed"]
RELATION_LANE_KEYWORDS = ["老婆", "孩子", "同事", "项目", "team", "project", "related to"]
CONTEXT_LANE_KEYWORDS = ["现在", "今天", "本周", "正在", "now", "today", "this week", "current"]
SMALL_TALK_PATTERNS = ["hi", "hello", "你好", "嗨", "ok", "谢谢", "thanks"]

DO_NOT_AUTO_INJECT_TAG = "do_not_auto_inject"
MIN_CONFIDENCE = 0.3


class RetrievalContext(BaseModel):
    subject_id: str
    session_id: str
    agent_type: str
    user_message: str
    access_purpose: str = "context_injection"


class RetrievalPlan(BaseModel):
    profile_lane: bool = True
    context_lane: bool = False
    episode_lane: bool = False
    relation_lane: bool = False
    profile_limit: int = 5
    context_limit: int = 3
    episode_limit: int = 3
    relation_limit: int = 3


class MemoryRetrievalPlanner:
    def plan(self, context: RetrievalContext) -> RetrievalPlan:
        """Determine which retrieval lanes to activate."""
        msg = context.user_message.lower().strip()
        if any(msg == p or msg.startswith(p + " ") for p in SMALL_TALK_PATTERNS):
            return RetrievalPlan(
                profile_lane=True,
                context_lane=False,
                episode_lane=False,
                relation_lane=False,
            )
        return RetrievalPlan(
            profile_lane=True,  # always on for non-small-talk (Phase R-D rule)
            context_lane=any(k in msg for k in CONTEXT_LANE_KEYWORDS),
            episode_lane=any(k in msg for k in EPISODE_LANE_KEYWORDS),
            relation_lane=any(k in msg for k in RELATION_LANE_KEYWORDS),
        )


class MemorySectionAssembler:
    def assemble(
        self,
        *,
        profile_records: list[Any],
        context_records: list[Any],
        episode_records: list[Any],
        relation_records: list[Any],
        plan: RetrievalPlan,
        context: RetrievalContext | None = None,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> str:
        """Build memory context string with 4 sections for system prompt injection.

        Applies spec retrieval.md §6 filters:
          1. Drop records tagged ``do_not_auto_inject``.
          2. Drop records with ``confidence < min_confidence``.
          3. Drop records with ``valid_until`` <= now.

        Then applies per-lane limits and renders in order:
        profiles (current facts) → contexts (current context) →
        relations (important relationships) → episodes (historical evidence).
        """
        now = datetime.now(UTC)
        effective_context = context or RetrievalContext(
            subject_id="",
            session_id="",
            agent_type="",
            user_message="",
        )

        def _keep(record: Any) -> bool:
            policy_tags = getattr(record, "policy_tags", None) or []
            if (
                effective_context.access_purpose == "context_injection"
                and DO_NOT_AUTO_INJECT_TAG in policy_tags
            ):
                return False
            for tag in policy_tags:
                if tag.startswith("access:"):
                    _, allowed_purpose = tag.split(":", 1)
                    if allowed_purpose != effective_context.access_purpose:
                        return False
                if tag.startswith("agent:"):
                    _, allowed_agent = tag.split(":", 1)
                    if allowed_agent != effective_context.agent_type:
                        return False
            confidence = getattr(record, "confidence", 1.0)
            if confidence is not None and confidence < min_confidence:
                return False
            valid_until = getattr(record, "valid_until", None)
            if valid_until is not None:
                # Treat naive datetimes as UTC to stay compatible with sqlite storage.
                if valid_until.tzinfo is None:
                    valid_until = valid_until.replace(tzinfo=UTC)
                if valid_until <= now:
                    return False
            return True

        profiles = [r for r in profile_records if _keep(r)][: plan.profile_limit]
        contexts = [r for r in context_records if _keep(r)][: plan.context_limit]
        relations = [r for r in relation_records if _keep(r)][: plan.relation_limit]
        episodes = [r for r in episode_records if _keep(r)][: plan.episode_limit]

        sections: list[str] = []

        if profiles:
            lines = "\n".join(f"- [{r.kind}] {r.content}" for r in profiles)
            sections.append(f"## Current facts about user\n{lines}")

        if contexts:
            lines = "\n".join(f"- {r.content}" for r in contexts)
            sections.append(f"## Current context\n{lines}")

        if relations:
            lines = "\n".join(f"- {_render_relation(r)}" for r in relations)
            sections.append(f"## Important relationships\n{lines}")

        if episodes:
            lines = "\n".join(f"- {r.content}" for r in episodes)
            sections.append(f"## Historical evidence (may be outdated)\n{lines}")

        return "\n\n".join(sections)


def _render_relation(record: Any) -> str:
    """Render a relation record as ``subject_id predicate object_ref``.

    ``RelationCandidateRecord`` has no ``object_ref`` column; prefer
    ``target_entity_id`` and fall back to ``content`` when both IDs are unset.
    """
    subject_id = getattr(record, "source_entity_id", None) or getattr(
        record, "subject_id", ""
    )
    predicate = getattr(record, "predicate", "")
    object_ref = (
        getattr(record, "target_entity_id", None)
        or getattr(record, "object_ref", None)
        or getattr(record, "content", "")
    )
    return f"{subject_id} {predicate} {object_ref}".strip()


async def retrieve_memory_section(
    context: RetrievalContext,
    *,
    db_session: AsyncSession,
) -> str:
    """Full retrieval pipeline: plan → fetch → assemble → return string."""
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore

    planner = MemoryRetrievalPlanner()
    plan = planner.plan(context)

    profile_store = ProfileMemoryStore(db_session)
    episode_store = EpisodeMemoryStore(db_session)

    profile_records: list[Any] = []
    if plan.profile_lane:
        profile_records = await profile_store.search_active(
            subject_id=context.subject_id,
            limit=plan.profile_limit,
        )

    context_records: list[Any] = []
    if plan.context_lane:
        context_records = await profile_store.search_recent_context(
            subject_id=context.subject_id,
            limit=plan.context_limit,
        )

    episode_records: list[Any] = []
    if plan.episode_lane:
        episode_records = await episode_store.search(
            query=context.user_message,
            subject_id=context.subject_id,
            limit=plan.episode_limit,
        )

    relation_records: list[Any] = []
    if plan.relation_lane:
        from sebastian.memory.entity_registry import EntityRegistry

        relation_registry = EntityRegistry(db_session)
        relation_records = await relation_registry.list_relations(
            subject_id=context.subject_id,
            limit=plan.relation_limit,
        )

    assembler = MemorySectionAssembler()
    return assembler.assemble(
        profile_records=profile_records,
        context_records=context_records,
        episode_records=episode_records,
        relation_records=relation_records,
        plan=plan,
        context=context,
    )
