---
version: "1.0"
last_updated: 2026-04-19
status: planned
---

# Memory（记忆）总体架构

> 模块索引：[INDEX.md](INDEX.md)
> 架构图：[../../diagrams/memory/overview.html](../../diagrams/memory/overview.html)

---

## 1. 设计目标

Sebastian 的记忆系统必须同时覆盖三类能力：

1. **个人画像**：稳定记住用户偏好、身份信息、长期事实，并在新信息到来时正确更新
2. **对话回忆**：能回想过去讨论过什么、做过什么、作出过哪些决定
3. **动态状态**：能区分“过去成立”和“当前成立”，避免把旧事实当成现状

工程目标：

- 先把边界设计对，再分阶段实现
- 后续增加关系图、图谱检索、记忆 UI 时不推翻主模型
- 写入、检索、沉淀、审计走统一协议

---

## 2. 非目标

首期不要求立即实现：

- 复杂图数据库或多跳图推理
- 记忆管理 UI
- 多用户权限模型完整产品化
- 外部知识库批量导入与治理
- 向量数据库、embedding（向量嵌入）、hybrid retrieval（混合检索）

---

## 3. 逻辑模型

Sebastian 的长期记忆采用三层逻辑模型：

| 层 | 职责 |
|----|------|
| `ProfileMemory`（画像记忆） | 用户画像、偏好、长期事实、当前状态 |
| `EpisodicMemory`（情景/经历记忆） | 事件、经历、任务过程、会话回忆、阶段摘要 |
| `RelationalMemory`（关系记忆） | 实体、关系、时间区间、多实体语义连接 |

---

## 4. 首期物理落地

首期物理实现采用：

- `Profile Store`（画像存储）
  - 承载 `fact` / `preference`
- `Episode Store`（经历存储）
  - 承载 `episode` / `summary`
- `Entity Registry`（实体注册表）
  - 承载实体规范化与 alias lookup
- `Relation Layer`（关系层）
  - 首期至少落 `relation_candidates`，不要求成为主查询依赖
- `memory_decision_log`（记忆决策日志）
  - 首期即落盘，支持审计、调试和后续 UI

设计理由：

- “事实/画像”和“经历/回忆”的数据本质不同，必须分开优化更新规则和检索规则
- 关系图层是高价值增强层，但不适合作为 Day 1 主存储
- 首版先把“记忆是否正确”做好，再增强“语义召回是否最强”

---

## 5. 与现有架构集成

### 5.1 WorkingMemory

`WorkingMemory`（工作记忆）继续作为进程内、任务级临时状态，不纳入长期记忆体系。

### 5.2 现有 EpisodicMemory

现有 `sebastian/memory/episodic_memory.py` 继续保留为 session history compatibility layer（会话历史兼容层），但不再等同于完整回忆系统。

它当前实际职责是：

- 从 `SessionStore` 读取当前 session（会话）的最近消息，供 BaseAgent 构造 LLM 上下文
- 把 user / assistant turn（轮次消息）追加回 session 消息历史
- 支撑 cancel partial flush（取消时保存部分输出）和 assistant blocks（助手消息块）持久化

因此它更接近 `SessionHistory`（会话历史）适配器，而不是新设计中的 `Episode Store`（经历存储）。

新的 `Episode Store`（经历存储）应作为“在 session 历史之上建立的可检索回忆层”新增，而不是直接替换现有主对话历史链路。

实现时建议：

- 首期保留现有 `EpisodicMemory` 以降低 BaseAgent 主链路风险
- 新增真正的 `Episode Store` 存储 `episode`（经历）/ `summary`（摘要）等 artifacts（记忆产物）
- 后续可在不影响行为的前提下，将现有类重命名为 `SessionHistory` 或 `ConversationHistory`，避免概念混淆

### 5.3 BaseAgent Hook

后续实现至少需要四个 hook：

- turn 入口的 memory retrieval planner
- system prompt 组装时的 memory section assembler
- turn 结束或 session 转 idle 时的 consolidation scheduler
- 显式 `memory_*` 工具入口

### 5.4 工具层

首期建议只提供两个 agent-facing（面向 Agent 的）工具：

- `memory_save`
- `memory_search`

工具层只触发统一写入/读取协议，不直接操作底层表。

`memory_list` / `memory_delete` 不作为首期 agent 工具。它们更适合作为后续 owner-only（仅主人可用）的管理 API 或记忆管理 UI 能力，用于用户核查、纠错、删除敏感记忆。原因：

- 常规对话中，Agent 需要的是按需检索，而不是枚举全部记忆
- 删除记忆属于高影响操作，应该有更明确的用户确认和审计
- 过早暴露给 Agent 会增加误删、越权查看或 prompt injection（提示词注入）风险

---

## 6. 分阶段实现

| Phase | 目标 | 内容 |
|-------|------|------|
| A | 协议先行 | artifact schema（记忆产物结构）、slot registry（语义槽位注册表）、resolution policy（冲突解决策略）、retrieval planner interface（检索规划接口）、assembler interface（装配器接口）、decision log schema（决策日志结构） |
| B | Profile + Episode 可用版 | fact/preference（事实/偏好）写入更新注入、episode/summary（经历/摘要）存储检索、基础三 lane（检索通道）、decision log（决策日志）落盘 |
| C | Consolidation 成熟版 | session consolidation（会话沉淀）、cross-session preference strengthening（跨会话偏好强化）、maintenance worker（维护任务）、summary（摘要）策略 |
| D | Relation / Graph 增强 | entity normalization（实体规范化）强化、relation artifact（关系记忆产物）正式入库、relation lane（关系检索通道）检索、时间区间关系 |

---

*← 返回 [Memory 索引](INDEX.md)*
