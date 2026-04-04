from __future__ import annotations

from sebastian.core.base_agent import BaseAgent


class LifeAgent(BaseAgent):
    name = "life"
    system_prompt = (
        "You are a personal life assistant. "
        "Help with schedules, reminders, daily planning, and lifestyle questions."
    )
