from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sebastian.core.tool import tool
from sebastian.core.types import ToolResult
from sebastian.permissions.types import PermissionTier

if TYPE_CHECKING:
    from sebastian.protocol.a2a.dispatcher import A2ADispatcher


def _get_dispatcher() -> A2ADispatcher:
    import sebastian.gateway.state as state

    return state.dispatcher


@tool(
    name="delegate_to_agent",
    description=(
        "Delegate a task to a specialized sub-agent. Use this when a user request requires "
        "capabilities of a specific agent type. Returns the agent's output summary."
    ),
    permission_tier=PermissionTier.LOW,
)
async def delegate_to_agent(agent_type: str, goal: str, context: str = "") -> ToolResult:
    """
    agent_type: the registered agent type (e.g. 'code', 'stock')
    goal: clear description of what the agent should accomplish
    context: optional additional context
    """
    from sebastian.protocol.a2a.types import DelegateTask

    dispatcher = _get_dispatcher()
    task = DelegateTask(
        task_id=str(uuid.uuid4()),
        goal=goal,
        context={"text": context} if context else {},
    )
    a2a_result = await dispatcher.delegate(agent_type, task)
    if a2a_result.ok:
        summary = (
            a2a_result.output.get("summary", str(a2a_result.output)) if a2a_result.output else ""
        )
        return ToolResult(ok=True, output=summary)
    return ToolResult(ok=False, error=a2a_result.error or "Delegation failed")
