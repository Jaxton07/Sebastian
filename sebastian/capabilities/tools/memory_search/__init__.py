from __future__ import annotations

from typing import Any

from sebastian.core.tool import tool
from sebastian.core.tool_context import get_tool_context
from sebastian.core.types import ToolResult
from sebastian.memory.subject import resolve_subject
from sebastian.memory.trace import preview_text, record_ref, trace
from sebastian.memory.types import MemoryScope
from sebastian.permissions.types import PermissionTier


@tool(
    name="memory_search",
    description="Search long-term memory for relevant facts, preferences, summaries, or episodes.",
    permission_tier=PermissionTier.LOW,
)
async def memory_search(query: str, limit: int = 5) -> ToolResult:
    import sebastian.gateway.state as state

    trace(
        "tool.memory_search.start",
        query_preview=preview_text(query),
        limit=limit,
    )
    if not state.memory_settings.enabled:
        return ToolResult(ok=False, error="记忆功能已关闭")

    if not hasattr(state, "db_factory") or state.db_factory is None:
        return ToolResult(ok=False, error="记忆存储不可用")

    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.memory.retrieval import MemoryRetrievalPlanner, RetrievalContext

    ctx = get_tool_context()
    session_id = ctx.session_id if ctx else "unknown"

    subject_id = await resolve_subject(
        MemoryScope.USER,
        session_id=session_id,
        agent_type="memory_search_tool",
    )
    retrieval_ctx = RetrievalContext(
        subject_id=subject_id,
        session_id=session_id,
        agent_type="memory_search_tool",
        user_message=query,
        access_purpose="tool_search",
    )

    planner = MemoryRetrievalPlanner()
    plan = planner.plan(retrieval_ctx)

    async with state.db_factory() as session:
        profile_store = ProfileMemoryStore(session)
        episode_store = EpisodeMemoryStore(session)

        profile_records = (
            await profile_store.search_active(
                subject_id=subject_id,
                limit=plan.profile_limit,
            )
            if plan.profile_lane
            else []
        )
        episode_records = (
            await episode_store.search(
                subject_id=subject_id,
                query=query,
                limit=plan.episode_limit,
            )
            if plan.episode_lane
            else []
        )

    items: list[dict[str, Any]] = []
    for record in profile_records:
        items.append(
            {
                "kind": record.kind,
                "content": record.content,
                "source": record.source,
                "confidence": record.confidence if record.confidence is not None else 1.0,
                "citation_type": "current_truth",
                "is_current": True,
            }
        )
    for record in episode_records:
        citation_type = (
            "historical_summary" if record.kind == "summary" else "historical_evidence"
        )
        items.append(
            {
                "kind": record.kind,
                "content": record.content,
                "source": record.source,
                "confidence": record.confidence if record.confidence is not None else 1.0,
                "citation_type": citation_type,
                "is_current": False,
            }
        )

    items = items[:limit]
    trace(
        "tool.memory_search.done",
        query_preview=preview_text(query),
        result_count=len(items),
        current_count=sum(1 for item in items if item["is_current"]),
        historical_count=sum(1 for item in items if not item["is_current"]),
        items=[record_ref(r) for r in [*profile_records, *episode_records]][:limit],
    )

    if not items:
        return ToolResult(
            ok=True,
            output={"items": []},
            empty_hint="记忆库中暂无匹配内容",
        )
    return ToolResult(ok=True, output={"items": items})
