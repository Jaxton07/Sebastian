"""stop_agent / resume_agent 共用的权限校验。

约束（与 docs/architecture/spec/overview/three-tier-agent.md 对齐）：
- depth=1（Sebastian）：可作用于任何 depth=2 或 depth=3 session
- depth=2（组长）：只能作用于自己创建的 depth=3 组员
  （`parent_session_id == 调用方 session_id`）
- 其他 depth（含 depth=3 组员）：拒绝

spec §6.3 明确权限写在工具内部，这里只是把两份相同逻辑抽到同目录 helper，
调用方依然在工具函数内。
"""

from __future__ import annotations

from typing import Any, Literal

SessionAction = Literal["stop", "resume"]

_ACTION_VERB: dict[SessionAction, str] = {
    "stop": "停止",
    "resume": "恢复",
}


def assert_session_action_permission(
    *,
    action: SessionAction,
    ctx_session_id: str,
    ctx_depth: int,
    index_entry: dict[str, Any],
    session_id: str,
) -> str | None:
    """返回权限错误文案；None 表示通过。"""
    verb = _ACTION_VERB[action]

    if ctx_depth == 1:
        return None

    if ctx_depth == 2:
        if index_entry.get("depth") != 3 or index_entry.get("parent_session_id") != ctx_session_id:
            return (
                f"无权{verb} session {session_id}："
                "你只能作用于自己创建的 depth=3 子代理 session。"
                f"请向 Sebastian 汇报需要{verb}该任务。"
            )
        return None

    return (
        f"无权{verb} session {session_id}："
        "仅 Sebastian(depth=1) 或组长(depth=2) 可执行。"
        f"请向上汇报需要{verb}该任务。"
    )
