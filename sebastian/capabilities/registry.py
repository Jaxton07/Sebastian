from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sebastian.core.tool import ToolFn, get_tool, list_tool_specs
from sebastian.core.types import ToolResult

logger = logging.getLogger(__name__)

McpToolFn = Callable[..., Awaitable[ToolResult]]


class CapabilityRegistry:
    """Unified access point for native tools and MCP-sourced tools."""

    def __init__(self) -> None:
        self._mcp_tools: dict[str, tuple[dict[str, Any], McpToolFn]] = {}
        self._skill_names: set[str] = set()

    def get_all_tool_specs(self) -> list[dict[str, Any]]:
        """Return all tool specs in Anthropic API `tools` format (backward compat)."""
        return self.get_callable_specs(allowed_tools=None, allowed_skills=None)

    def get_tool_specs(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        """Return native + MCP tool specs (excluding skills). allowed=None means all."""
        specs: list[dict[str, Any]] = []
        for spec in list_tool_specs():
            if allowed is None or spec.name in allowed:
                specs.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.parameters,
                    }
                )
        for name, (spec_dict, _) in self._mcp_tools.items():
            if name in self._skill_names:
                continue
            if allowed is None or name in allowed:
                specs.append(spec_dict)
        return specs

    def get_skill_specs(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        """Return skill specs only. allowed=None means all."""
        specs: list[dict[str, Any]] = []
        for name, (spec_dict, _) in self._mcp_tools.items():
            if name not in self._skill_names:
                continue
            if allowed is None or name in allowed:
                specs.append(spec_dict)
        return specs

    def get_callable_specs(
        self,
        allowed_tools: set[str] | None = None,
        allowed_skills: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return combined filtered tool + skill specs for LLM API calls."""
        return self.get_tool_specs(allowed_tools) + self.get_skill_specs(allowed_skills)

    async def call(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name. Native tools take priority over MCP."""
        native = get_tool(tool_name)
        if native is not None:
            _, fn = native
            return await fn(**kwargs)
        mcp_entry = self._mcp_tools.get(tool_name)
        if mcp_entry is not None:
            _, fn = mcp_entry
            return await fn(**kwargs)
        return ToolResult(ok=False, error=f"Unknown tool: {tool_name}")

    def register_mcp_tool(
        self,
        name: str,
        spec: dict[str, Any],
        fn: ToolFn,
    ) -> None:
        """Register a tool sourced from MCP."""
        self._mcp_tools[name] = (spec, fn)
        logger.info("MCP tool registered: %s", name)

    def register_skill_specs(self, specs: list[dict[str, Any]]) -> None:
        """Register skill tool specs (read-only — LLM uses description as instructions)."""
        for spec in specs:
            name = spec["name"]
            description = spec["description"]

            async def _skill_fn(instructions: str = "", _desc: str = description) -> ToolResult:
                return ToolResult(ok=True, output=_desc)

            self._mcp_tools[name] = (spec, _skill_fn)
            self._skill_names.add(name)
            logger.info("Skill registered: %s", name)


# Global singleton shared by all agents
registry = CapabilityRegistry()
