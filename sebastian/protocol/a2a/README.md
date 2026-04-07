# a2a

> 上级索引：[protocol/](../README.md)

## 目录职责

A2A（Agent-to-Agent）通信协议定义目录。

**当前状态**：`dispatcher.py` 和 `types.py` 已在三层 Agent 架构重构中删除。Agent 间通信已改为：
- **下发任务**：通过 `capabilities/tools/delegate_to_agent` 工具直接创建 session 并异步执行
- **上报事件**：通过 `protocol/events/` EventBus 广播（`SESSION_STALLED`、`SESSION_COMPLETED` 等）

本目录保留 `__init__.py` 包标记，暂不删除以避免潜在的 import 路径变动。

## 目录结构

```
a2a/
└── __init__.py        # 包入口（空）
```

## 修改导航

如需修改 Agent 间通信逻辑，请参考：
- 委派任务：[capabilities/tools/delegate_to_agent/](../../capabilities/tools/delegate_to_agent/)
- 事件广播：[protocol/events/](../events/)

---

> 修改本目录或模块后，请同步更新此 README。
