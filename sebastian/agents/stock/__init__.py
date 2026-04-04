from __future__ import annotations

from sebastian.core.base_agent import BaseAgent


class StockAgent(BaseAgent):
    name = "stock"
    system_prompt = (
        "You are a stock and investment research specialist. "
        "Analyze financial data, look up prices, and provide investment insights."
    )
