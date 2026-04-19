---
version: "1.0"
last_updated: 2026-04-19
status: planned
---

# Memory（记忆）读取与注入

> 模块索引：[INDEX.md](INDEX.md)
> 架构图：[../../diagrams/memory/retrieval.html](../../diagrams/memory/retrieval.html)

---

## 1. 总原则

Sebastian 不做“统一 search top-k 然后塞进 prompt”，而做：

`Intent（意图） -> Retrieval Plan（检索计划） -> Assemble（装配）`

---

## 2. Intent 判定

每轮用户输入先做轻量记忆意图判断，至少识别：

- 是否在问长期偏好
- 是否在追问近期经历
- 是否在问当前状态
- 是否涉及实体关系
- 是否只是普通闲聊，不值得高成本检索

---

## 3. Retrieval Planner（检索规划器）

Planner 输入：

- `user_message`
- `session_context`
- `subject_id`
- `active_project_or_agent_context`
- `reader_agent_type`
- `reader_session_id`
- `access_purpose`

Planner 输出：

- 应启用哪些检索 lane
- 每条 lane 的预算
- 是否优先当前事实还是历史回忆
- 是否允许深挖原始 episode
- 基于 `policy_tags` 的过滤条件

---

## 4. 四条检索通道（Retrieval Lane）

### 4.1 Profile Lane（画像检索通道）

提供高价值、稳定、当前有效的画像与偏好。

特点：

- 条数小
- 高置信
- 即使不依赖当前 query 也可能注入

### 4.2 Context Lane（上下文检索通道）

提供与当前用户消息强相关的动态事实与状态。

特点：

- 强 query-aware
- 可结合当前 session 主题
- 侧重“当前正在做什么”

### 4.3 Episode Lane（经历检索通道）

提供过去发生过什么、怎么决定的、上次讨论到哪里。

策略：

- 默认先查 `summary`
- 需要细节时再下钻原始 `episode`

### 4.4 Relation Lane（关系检索通道）

提供实体间关系与时间性状态。

首期允许接口存在但数据量较少，后续随着 relation 层成熟逐步增强。

---

## 5. Assembler（上下文装配器）

最终注入不做平铺列表，而按语义分区装配：

- `What I know about the user`
- `Relevant current context`
- `Relevant past episodes`
- `Important relationships`

Assembler 在最终注入前，必须统一执行以下过滤：

- `status`
- `valid_from / valid_until`
- `scope / subject_id`
- `policy_tags`
- `confidence threshold`
- `reader_agent_type / access_purpose`

---

## 6. Token Budget（上下文预算）

各 lane 需要独立预算，不能共享抢占。

否则会出现：

- episode 抢光上下文
- preference 被挤掉
- 历史经历覆盖当前事实

---

## 7. 当前真值与历史证据分离

注入语义必须区分：

- `current truth`（当前真值）
  - 仅来自 `active` 且在时间上有效的事实和关系
- `historical evidence`（历史证据）
  - 来自 episode、旧事实、旧关系和摘要

---

*← 返回 [Memory 索引](INDEX.md)*
