from __future__ import annotations

import json
import math
from typing import Any


class TokenEstimator:
    """Conservative local token estimator used when provider usage is unavailable."""

    def estimate_text(self, text: str) -> int:
        if not text:
            return 0
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        other = len(text) - cjk
        return math.ceil(cjk / 1.5) + math.ceil(other / 4)

    def estimate_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str = "",
    ) -> int:
        """Conservatively estimate tokens for a message list.

        Serializes each message as JSON before counting, which includes role/content
        punctuation overhead, then adds a fixed per-message budget. Biased toward
        overestimating so threshold decisions err on the side of compacting.
        """
        total = self.estimate_text(system_prompt) + 8
        for message in messages:
            total += 6
            total += self.estimate_text(json.dumps(message, ensure_ascii=False, default=str))
        return total
