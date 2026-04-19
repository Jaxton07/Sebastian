from __future__ import annotations

import logging
from enum import Enum

LOGGER_NAME = "sebastian.memory.trace"
KEYWORD = "MEMORY_TRACE"
DEFAULT_PREVIEW_LIMIT = 160

logger = logging.getLogger(LOGGER_NAME)


def preview_text(text: object, limit: int = DEFAULT_PREVIEW_LIMIT) -> str:
    """Return a one-line, bounded preview safe for debug logs."""
    value = str(text)
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def record_ref(record: object) -> dict[str, object]:
    """Extract stable, non-exhaustive metadata for a memory-like record."""
    result: dict[str, object] = {}
    for attr in ("id", "kind", "slot_id", "status", "confidence"):
        value = getattr(record, attr, None)
        if value is not None:
            result[attr] = _coerce_value(value)
    content = getattr(record, "content", None)
    if content is not None:
        result["preview"] = preview_text(content)
    return result


def trace(event: str, **fields: object) -> None:
    """Emit a memory trace line to the existing Sebastian log pipeline."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    parts = [KEYWORD, event]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_format_value(value)}")
    logger.debug(" ".join(parts))


def _format_value(value: object) -> str:
    coerced = _coerce_value(value)
    if isinstance(coerced, dict):
        inner = ",".join(f"{k}:{_format_value(v)}" for k, v in coerced.items())
        return "{" + inner + "}"
    if isinstance(coerced, (list, tuple, set)):
        return "[" + ",".join(_format_value(v) for v in coerced) + "]"
    return preview_text(coerced)


def _coerce_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _coerce_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce_value(v) for v in value]
    return value
