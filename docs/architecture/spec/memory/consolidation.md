---
version: "1.0"
last_updated: 2026-04-20
status: partially-implemented
---

# Memory（记忆）后台沉淀与审计

> 模块索引：[INDEX.md](INDEX.md)
> 架构图：[../../diagrams/memory/consolidation.html](../../diagrams/memory/consolidation.html)

---

## 实现状态速览

| 模块 | 状态 | 备注 |
|------|------|------|
| Session Consolidation | **implemented** | `SessionConsolidationWorker` + startup catch-up sweep 已实现 |
| Cross-Session Consolidation | **planned** | 需单独 spec 设计触发频率、扫描窗口、证据合并规则、幂等 key |
| Memory Maintenance（过期扫描） | **partial** | EXPIRE 动作和 catch-up sweep 已有；降权、重复压缩、索引修复 planned |

---

## 1. Consolidation（后台沉淀）不是单一 Worker（后台任务）

后台沉淀至少分三类职责：

### 1.1 Session Consolidation（会话沉淀）

针对单次 session 在 `completed` 后做：

- 生成阶段摘要
- 提取候选事实、偏好、关系
- 产生新的 artifacts
- 对已有记忆提出生命周期操作（如 EXPIRE）

#### ConsolidationResult 三个输出字段的语义分工

| 字段 | 操作对象 | 是否经过 Resolver | 说明 |
|------|----------|-------------------|------|
| `summaries` | 不存在的新摘要 | 是（走 resolve_candidate） | Consolidator 生成的会话摘要，经 resolver 判断是否 ADD/DISCARD |
| `proposed_artifacts` | 不存在的新候选记忆 | 是（走 resolve_candidate） | Consolidator 提议的新 fact/preference/episode/entity/relation，最终 ADD/SUPERSEDE/MERGE/DISCARD 由 resolver 决定，LLM 不直接控制 |
| `proposed_actions` | 数据库中已存在的记忆（by memory_id） | 否（直接执行） | Consolidator 对已有记忆提出生命周期操作，唯一合法值为 `EXPIRE` |

#### proposed_actions 的定位与边界

`proposed_actions` 解决的是 `proposed_artifacts → resolver` 路径**无法覆盖的场景**：

- `proposed_artifacts` + resolver 处理"新候选 vs 现有记录的冲突"，resolver 产出 SUPERSEDE 时同时有 old_id 和 new_memory
- 但有一类场景是"**不需要新记忆、只需要让旧记忆失效**"：某条 active 事实没有设置 `valid_until`，但 Consolidator 从本次会话语义中判断它已经不再成立

典型例子：上次记录了 `user.current_project_focus = "项目 A"`（无截止时间），本次会话用户说"已把项目 A 交给别人了"。Consolidator 通过 `proposed_actions EXPIRE + memory_id` 把该记录显式标为 `expired`，无需产生替代记忆。

这与 `valid_until` 自动失效的区别：

| | `valid_until` 到期 | `proposed_actions EXPIRE` |
|---|---|---|
| 触发方式 | 写入时设定，检索层过滤 | Consolidator 从会话语义主动判断 |
| 适用场景 | 已知时效性的事实 | 无截止时间但被新对话语义推翻的事实 |
| DB status 变化 | 无需改变（过滤层排除） | 显式从 active 改为 expired |
| 需要 memory_id | 否 | 是 |

**约束：**

- `proposed_actions.action` 只允许 `"EXPIRE"`；ADD/SUPERSEDE 的语义由 `proposed_artifacts → resolver` 路径承担，不在此处执行
- `memory_id` 必须非空且指向 active 的 profile memory 记录；0 命中时记录 `failed_expire` decision log，不写成功状态
- 所有 EXPIRE 操作必须进入 `memory_decision_log`

**Phase C 实现状态**：`SessionConsolidationWorker`（`sebastian/memory/consolidation.py`）已实现，由 `MemoryConsolidationScheduler` 订阅 `SESSION_COMPLETED` 事件触发。幂等性通过 `SessionConsolidationRecord(session_id, agent_type)` DB 标记保证；写入原子性通过单事务实现。启动时的 catch-up sweep 会补处理未沉淀的 completed session。

`idle` / `stalled` 触发当前不属于已实现契约。未来如果需要支持，应先补独立 spec，明确：

- 什么状态算 session idle / stalled。
- 是否允许对仍可能继续追加消息的 session 做沉淀。
- 幂等标记如何区分部分沉淀与最终沉淀。
- 后续 `SESSION_COMPLETED` 到来时如何避免重复摘要和重复写入。

### 1.2 Cross-Session Consolidation（跨会话沉淀）

针对多个 session 做：

- 偏好强化
- 模式归纳
- 长期主题聚合
- 多来源证据合并

**实现状态**：未实现。Cross-Session Consolidation 属于后续增强能力，不能直接复用当前 Session Consolidation 的完成事件语义。实现前需要单独 spec 讨论触发频率、扫描窗口、证据合并规则、幂等 key、decision log 记录方式和人工审核边界。

### 1.3 Memory Maintenance（记忆维护）

负责：

- 过期
- 降权
- 重复压缩
- 摘要替换
- 索引修复

**实现状态**：部分实现。当前已有 EXPIRE 类生命周期动作和 startup catch-up sweep，但还没有独立周期性 Maintenance Worker。降权、重复压缩、摘要替换和索引修复都需要单独 spec，先定义可观测输入、决策规则、审计字段和回滚方式。

---

## 2. Consolidation（后台沉淀）输入

后台沉淀不能只看原始对话，还应综合：

- session 消息
- 本次会话生成的 candidate artifacts
- 当前已有 active facts
- 最近相关 summaries
- 低置信、未决、待确认 artifacts

---

## 3. 为什么要分三类

- Session Consolidation 关注“这一段对话发生了什么”
- Cross-Session Consolidation 关注“用户长期稳定呈现出什么模式”
- Maintenance 关注“系统里的记忆是否仍干净可用”

---

## 4. Decision Log（决策日志）

`memory_decision_log` 从第一阶段就应落数据，即使 UI 暂时不做。

记录内容：

- 原始输入来源
- 候选 artifacts
- 命中的 slot / subject / scope
- 冲突候选列表
- 决策结果：`ADD / SUPERSEDE / MERGE / EXPIRE / DISCARD`
- 决策原因摘要
- 执行该决策的 worker / 模型 / 规则版本
- 关联的旧记录 ID 和新记录 ID
- 时间戳

价值：

- 调试“为什么记错了”
- 回答“为什么旧偏好被新偏好覆盖”
- 做人工审核 UI
- 做模型提示词和规则迭代对比
- 做自动回滚与补偿

---

*← 返回 [Memory 索引](INDEX.md)*
