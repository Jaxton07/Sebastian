from __future__ import annotations
import logging
from typing import Any

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.base_agent import BaseAgent
from sebastian.core.task_manager import TaskManager
from sebastian.core.types import Task
from sebastian.orchestrator.conversation import ConversationManager
from sebastian.protocol.events.bus import EventBus
from sebastian.protocol.events.types import Event, EventType

logger = logging.getLogger(__name__)

SEBASTIAN_SYSTEM_PROMPT = """You are Sebastian — an elegant, capable personal AI butler.
Your purpose: receive instructions, plan effectively, and execute precisely.
You have access to tools. Use them to fulfill requests completely.
For complex multi-step tasks, break them down and execute step by step.
When you encounter a decision that requires the user's input, ask clearly and concisely.
You never fabricate results — if a tool fails, say so and suggest alternatives."""


class Sebastian(BaseAgent):
    """Main orchestrator agent. Handles conversation turns and can delegate
    tasks to sub-agents via TaskManager (Phase 2 will add full A2A routing)."""

    name = "sebastian"
    system_prompt = SEBASTIAN_SYSTEM_PROMPT

    def __init__(
        self,
        registry: CapabilityRegistry,
        session_factory: Any,
        task_manager: TaskManager,
        conversation: ConversationManager,
        event_bus: EventBus,
    ) -> None:
        super().__init__(registry, session_factory)
        self._task_manager = task_manager
        self._conversation = conversation
        self._event_bus = event_bus

    async def chat(self, user_message: str, session_id: str) -> str:
        """Handle a conversational turn. Publishes turn events."""
        await self._event_bus.publish(Event(
            type=EventType.TURN_RECEIVED,
            data={"session_id": session_id, "message": user_message[:200]},
        ))
        response = await self.run(user_message, session_id)
        await self._event_bus.publish(Event(
            type=EventType.TURN_RESPONSE,
            data={"session_id": session_id, "response": response[:200]},
        ))
        return response

    async def submit_background_task(self, goal: str, session_id: str) -> Task:
        """Create and submit a background task. Returns the Task immediately."""
        task = Task(goal=goal, assigned_agent=self.name)

        async def execute(t: Task) -> None:
            await self.run(t.goal, session_id=session_id, task_id=t.id)

        await self._task_manager.submit(task, execute)
        return task
