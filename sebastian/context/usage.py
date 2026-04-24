from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    raw: dict[str, Any] | None = None

    @property
    def effective_input_tokens(self) -> int | None:
        parts = [
            self.input_tokens,
            self.cache_creation_input_tokens,
            self.cache_read_input_tokens,
        ]
        if all(part is None for part in parts):
            return None
        return sum(part or 0 for part in parts)

    @property
    def effective_total_tokens(self) -> int | None:
        if self.total_tokens is not None:
            return self.total_tokens
        if self.effective_input_tokens is None or self.output_tokens is None:
            return None
        return self.effective_input_tokens + self.output_tokens
