from __future__ import annotations

from dataclasses import dataclass

from sebastian.context.usage import TokenUsage


@dataclass(slots=True)
class CompactionDecision:
    should_compact: bool
    reason: str
    token_count: int | None
    threshold: int


class ContextTokenMeter:
    def __init__(
        self,
        *,
        context_window: int,
        usage_ratio: float = 0.70,
        estimate_ratio: float = 0.65,
    ) -> None:
        self._context_window = context_window
        self._usage_threshold = int(context_window * usage_ratio)
        self._estimate_threshold = int(context_window * estimate_ratio)

    def should_compact(
        self,
        *,
        usage: TokenUsage | None,
        estimate: int | None,
    ) -> CompactionDecision:
        usage_tokens = usage.effective_input_tokens if usage is not None else None
        if usage_tokens is not None:
            return CompactionDecision(
                should_compact=usage_tokens >= self._usage_threshold,
                reason="usage_threshold",
                token_count=usage_tokens,
                threshold=self._usage_threshold,
            )
        return CompactionDecision(
            should_compact=estimate is not None and estimate >= self._estimate_threshold,
            reason="estimate_threshold",
            token_count=estimate,
            threshold=self._estimate_threshold,
        )
