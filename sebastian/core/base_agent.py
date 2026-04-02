from __future__ import annotations

import logging
from abc import ABC

import anthropic

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.agent_loop import AgentLoop
from sebastian.memory.episodic_memory import EpisodicMemory
from sebastian.memory.working_memory import WorkingMemory
from sebastian.store.session_store import SessionStore

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = (
    "You are Sebastian, a personal AI butler. You are helpful, precise, and action-oriented. "
    "You have access to tools and will use them when needed. "
    "Think step by step, act efficiently, and always confirm important actions before executing."
)


class BaseAgent(ABC):
    name: str = "base_agent"
    system_prompt: str = BASE_SYSTEM_PROMPT

    def __init__(
        self,
        registry: CapabilityRegistry,
        session_store: SessionStore,
        model: str | None = None,
    ) -> None:
        self._registry = registry
        self._session_store = session_store
        self._episodic = EpisodicMemory(session_store)
        self.working_memory = WorkingMemory()

        from sebastian.config import settings

        resolved_model = model or settings.sebastian_model
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._loop = AgentLoop(self._client, registry, resolved_model)

    async def run(
        self,
        user_message: str,
        session_id: str,
        task_id: str | None = None,
        agent_name: str | None = None,
    ) -> str:
        agent_context = agent_name or self.name
        turns = await self._episodic.get_turns(session_id, agent=agent_context, limit=20)
        messages: list[dict[str, str]] = [
            {"role": turn.role, "content": turn.content} for turn in turns
        ]
        messages.append({"role": "user", "content": user_message})

        await self._episodic.add_turn(
            session_id,
            "user",
            user_message,
            agent=agent_context,
        )

        response = await self._loop.run(
            system_prompt=self.system_prompt,
            messages=messages,
            task_id=task_id,
        )

        await self._episodic.add_turn(
            session_id,
            "assistant",
            response,
            agent=agent_context,
        )
        return response
