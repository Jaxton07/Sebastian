from __future__ import annotations

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.types import ToolResult


def _make_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    # 注册两个普通 MCP tool
    async def mcp_fn(**kwargs):  # type: ignore[no-untyped-def]
        return ToolResult(ok=True, output="ok")

    reg.register_mcp_tool(
        "web_search",
        {"name": "web_search", "description": "search", "input_schema": {}},
        mcp_fn,
    )
    reg.register_mcp_tool(
        "shell_exec",
        {"name": "shell_exec", "description": "shell", "input_schema": {}},
        mcp_fn,
    )
    # 注册一个 Skill
    reg.register_skill_specs(
        [
            {
                "name": "research_skill",
                "description": "do research",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            }
        ]
    )
    return reg


def test_get_tool_specs_returns_only_tools_not_skills() -> None:
    reg = _make_registry()
    specs = reg.get_tool_specs()
    names = {s["name"] for s in specs}
    assert "web_search" in names
    assert "shell_exec" in names
    assert "research_skill" not in names


def test_get_skill_specs_returns_only_skills() -> None:
    reg = _make_registry()
    specs = reg.get_skill_specs()
    names = {s["name"] for s in specs}
    assert "research_skill" in names
    assert "web_search" not in names


def test_get_tool_specs_with_allowed_filter() -> None:
    reg = _make_registry()
    specs = reg.get_tool_specs(allowed={"web_search"})
    names = {s["name"] for s in specs}
    assert "web_search" in names
    assert "shell_exec" not in names


def test_get_skill_specs_with_allowed_empty_set() -> None:
    reg = _make_registry()
    specs = reg.get_skill_specs(allowed=set())
    assert specs == []


def test_get_callable_specs_combines_filtered_tools_and_skills() -> None:
    reg = _make_registry()
    specs = reg.get_callable_specs(
        allowed_tools={"web_search"},
        allowed_skills={"research_skill"},
    )
    names = {s["name"] for s in specs}
    assert names == {"web_search", "research_skill"}


def test_get_callable_specs_none_means_all() -> None:
    reg = _make_registry()
    specs = reg.get_callable_specs(allowed_tools=None, allowed_skills=None)
    names = {s["name"] for s in specs}
    assert "web_search" in names
    assert "shell_exec" in names
    assert "research_skill" in names
