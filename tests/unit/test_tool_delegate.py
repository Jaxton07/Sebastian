import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_delegate_to_agent_creates_session_and_dispatches():
    from sebastian.capabilities.tools.delegate_to_agent import delegate_to_agent
    from sebastian.permissions.types import ToolCallContext

    mock_state = MagicMock()
    mock_agent = MagicMock()
    mock_agent.name = "code"
    mock_state.agent_instances = {"code": mock_agent}
    mock_state.agent_registry = {
        "code": MagicMock(display_name="铁匠", max_children=5),
    }
    mock_state.session_store = AsyncMock()
    mock_state.index_store = AsyncMock()
    mock_state.event_bus = MagicMock()

    ctx = ToolCallContext(
        task_goal="build feature",
        session_id="seb_session",
        task_id=None,
        agent_type="sebastian",
        depth=1,
    )

    with patch("sebastian.capabilities.tools.delegate_to_agent._get_state", return_value=mock_state):
        result = await delegate_to_agent(
            agent_type="code", goal="write auth module", context="", _ctx=ctx,
        )

    assert result.ok is True
    assert "铁匠" in result.output
    mock_state.session_store.create_session.assert_awaited_once()
    mock_state.index_store.upsert.assert_awaited_once()
