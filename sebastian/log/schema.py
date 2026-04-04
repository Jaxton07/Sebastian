from __future__ import annotations

from pydantic import BaseModel


class LogState(BaseModel):
    """当前日志开关完整状态（GET 响应体）。"""

    llm_stream_enabled: bool
    sse_enabled: bool


class LogConfigPatch(BaseModel):
    """PATCH 请求体，仅传需要修改的字段。"""

    llm_stream_enabled: bool | None = None
    sse_enabled: bool | None = None
