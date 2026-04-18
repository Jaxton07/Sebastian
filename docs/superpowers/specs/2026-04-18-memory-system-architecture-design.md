---
version: "1.0"
last_updated: 2026-04-18
status: planned
---

# Sebastian 记忆系统总体架构设计

*← [Spec 根索引](../../../docs/architecture/spec/INDEX.md)*

> 本文档是 Sebastian 新的记忆系统主设计，取代旧的 `2026-04-18-semantic-memory-design.md` 作为后续实现基线。
> 旧文可保留作历史参考，但其 `memories + memory_keys` 单主表建模、双层注入和单次 session 提取方案，不再作为当前设计依据。

---

## 1. 设计目标

Sebastian 的记忆系统必须同时覆盖三类能力：

1. **个人画像**：稳定记住用户偏好、身份信息、长期事实，并在新信息到来时正确更新
2. **对话回忆**：能回想过去讨论过什么、做过什么、作出过哪些决定
3. **动态状态**：能区分“过去成立”和“当前成立”，避免把旧事实当成现状

同时满足以下工程目标：

- **先把边界设计对，再分阶段实现**
- **后续增加关系图、图谱检索、更多记忆 UI 时不需要推翻主模型**
- **让写入、检索、沉淀、审计走统一协议，而不是每条路径各写一套逻辑**

---

## 2. 非目标

本设计当前不要求首期立即实现以下内容，但必须在架构上预留兼容空间：

- 复杂图数据库或多跳图推理的完整上线
- 记忆管理 UI（浏览、审核、冲突修复）的完整前端实现
- 多用户权限模型的完整产品化体验
- 任意外部知识库导入与批量治理能力

---

## 3. 核心结论

### 3.1 逻辑模型

Sebastian 的长期记忆采用**三层逻辑模型**：

- `ProfileMemory`
  - 用户画像、偏好、长期事实、当前状态
- `EpisodicMemory`
  - 事件、经历、任务过程、会话回忆、阶段摘要
- `RelationalMemory`
  - 实体、关系、时间区间、多实体语义连接

### 3.2 物理落地

首期物理实现采用**两套长期主存储 + 一套关系层接口预留**：

- `Profile Store`
  - 承载 `fact` / `preference`
- `Episode Store`
  - 承载 `episode` / `summary`
- `Relation Layer`
  - 首期定义 artifact、接口和流水线挂点，不要求成为主检索依赖

这样做的原因：

- “事实/画像”和“经历/回忆”的数据本质不同，必须物理分开，才能让更新规则和检索规则各自最优
- “关系图层”是高价值增强层，但其最佳 schema 和查询路径通常在使用中逐步稳定，不适合作为 Day 1 主存储

### 3.3 总体原则

Sebastian 不直接把原始输入写入某个固定 memory 表，而是先把输入转成标准化的 **memory artifacts**，再由路由层分发到不同记忆后端。

---

## 4. Memory Artifact 统一抽象

### 4.1 Artifact 类型

所有写入路径都必须先产出以下逻辑对象之一：

- `fact`
  - 可被后续事实覆盖、失效或并存的结构化陈述
- `preference`
  - 用户偏好；本质上属于 fact，但因其注入优先级和更新策略特殊，单独建类
- `episode`
  - 某次实际发生过的事件、对话、任务、决策或经历
- `summary`
  - 对一个或一组 episode 的压缩表述
- `entity`
  - 需要长期识别和跟踪的对象
- `relation`
  - 实体之间的语义关系，可带时间区间和排他规则

### 4.2 统一字段集合

所有 artifacts 至少拥有以下字段：

```python
class MemoryArtifact(TypedDict):
    id: str
    kind: Literal["fact", "preference", "episode", "summary", "entity", "relation"]
    scope: str
    subject_id: str
    slot_id: str | None
    cardinality: Literal["single", "multi"] | None
    resolution_policy: Literal["supersede", "merge", "append_only", "time_bound"] | None
    content: str
    structured_payload: dict[str, Any]
    source: Literal["explicit", "inferred", "observed", "imported", "system_derived"]
    confidence: float
    status: Literal["active", "superseded", "expired", "deleted"]
    valid_from: datetime | None
    valid_until: datetime | None
    recorded_at: datetime
    last_accessed_at: datetime | None
    access_count: int
    provenance: dict[str, Any]
    links: list[str]
    embedding_ref: str | None
    dedupe_key: str | None
    policy_tags: list[str]
```

### 4.3 必须从 Day 1 保留的字段语义

- `scope`
  - 限定记忆归属范围，例如 `user` / `session` / `project` / `agent`
- `subject_id`
  - 限定记忆主体，防止未来多用户、多项目、多 agent 情况下串数据
- `slot_id + cardinality + resolution_policy`
  - 让冲突消解成为显式协议，而不是在 Resolver 中临时猜测
- `source + confidence + provenance`
  - 用于冲突判断、审计回溯和后续人工核查
- `status + valid_from + valid_until`
  - 用于表达动态状态，避免未来为“当前值”和“历史值”做破坏性迁移
- `structured_payload`
  - 让记忆不仅是可读文本，也能被程序化处理
- `links`
  - 作为未来关系层和摘要层的桥接字段

### 4.4 Artifact 不等于表

`artifact` 是统一逻辑协议，不要求和数据库表一一对应。

例如：

- `preference` 最终可能落入 `profile_facts`
- `summary` 最终可能落入 `episode_summaries`
- `relation` 首期可能只进入候选表或审计日志，而不进入主检索路径

### 4.5 Slot Registry

`slot_id` 不应是自由文本，而应关联到稳定的 slot registry。

registry 至少维护：

- `slot_id`
- `scope`
- `subject_kind`
- `cardinality`
- `resolution_policy`
- `kind_constraints`
- `description`

规则：

- `fact` / `preference` 默认必须带 `slot_id`
- `relation` 默认必须带稳定的关系谓词标识
- `episode` / `summary` 可为空，因为它们通常不是槽位覆盖模型

如果上游暂时只能产出模糊候选，也必须在 Normalize 阶段显式落成 `slot_id` 或标记为“未归槽”，不能把槽位推断留给 Persist 阶段临时决定。

---

## 5. 生命周期模型

### 5.1 状态定义

所有长期记忆统一采用四态生命周期：

- `active`
  - 当前有效，可参与检索与自动注入
- `superseded`
  - 被更新事实取代，但保留历史
- `expired`
  - 因时间条件自然失效
- `deleted`
  - 被用户或系统显式删除，不再参与正常召回

### 5.2 为什么不能只做覆盖

Sebastian 的记忆不是 KV 配置项。以下历史本身有价值：

- 用户现在主要项目从 A 变成 B
- 用户曾经偏好一种工作方式，但后来调整
- 某个项目此前处于设计阶段，现在进入实现阶段

因此，事实更新默认应保留历史轨迹，而不是直接覆盖旧行。

---

## 6. 语义槽位与冲突模型

### 6.1 Memory Slot

冲突判断不基于纯文本相似度，而基于稳定的**语义槽位**：

- `user.preference.response_style`
- `user.profile.timezone`
- `user.current_project`
- `project.sebastian.phase`
- `user.pet.name`

槽位必须表达：

- 主体是谁
- 这是哪一类事实
- 该槽位是单值还是多值
- 采用什么冲突策略

### 6.2 槽位策略

每个 slot 绑定至少两个元属性：

- `cardinality`
  - `single` 或 `multi`
- `resolution_policy`
  - `supersede` / `merge` / `append_only` / `time_bound`

### 6.3 冲突决策流程

每条新 artifact 统一走三段式：

1. `Resolve`
   - 在同 subject、同 scope、同 slot 下找候选冲突对象
2. `Decide`
   - 只允许输出以下决策之一：
   - `ADD`
   - `SUPERSEDE`
   - `MERGE`
   - `EXPIRE`
   - `DISCARD`
3. `Apply`
   - 按决策落库、写日志、更新索引

### 6.4 各类型默认策略

| Artifact | 默认规则 |
|----------|----------|
| `preference` | 单槽位、单活跃记录、默认 `SUPERSEDE` |
| `fact(single)` | 单槽位、单活跃记录、默认 `SUPERSEDE` |
| `fact(multi)` | 多值并存、去重后 `ADD` 或 `MERGE` |
| `episode` | append-only，仅做精确去重 |
| `summary` | 可替代“默认摘要”，但保留历史摘要 |
| `relation(exclusive)` | 时间边界覆盖，旧关系写 `valid_until` |
| `relation(non_exclusive)` | 并存 |

### 6.5 可信度优先级

冲突决策优先遵循以下原则：

1. `explicit` 高于 `inferred`
2. 新的明确表达高于旧的明确表达
3. 高置信度高于低置信度
4. 更具体的结构化陈述高于模糊概括

### 6.6 设计约束

文本相似度最多只能用于召回候选，不允许直接决定覆盖关系。

---

## 7. 存储架构

### 7.1 Profile Store

职责：

- 存储 `fact` / `preference`
- 按 `subject_id + slot` 做更新和冲突消解
- 支持当前有效事实检索
- 支持历史状态回溯

建议包含的最小逻辑字段：

- `slot`
- `cardinality`
- `content`
- `structured_payload`
- `source`
- `confidence`
- `status`
- `valid_from`
- `valid_until`
- `provenance`
- `policy_tags`

### 7.2 Episode Store

职责：

- 存储 `episode`
- 存储 `summary`
- 维护最近回忆、阶段摘要、决策历史
- 为 query-aware 检索提供全文、时间和主题索引

建议拆成两类逻辑对象：

- 原始 episode
- 派生 summary

### 7.3 Entity Registry

职责：

- 稳定分配实体标识
- 维护实体别名、规范化名称、类型
- 为后续 relation 层和跨 session 主题聚合提供基础

首期可轻量实现，不要求完整图谱能力，但必须成为标准物化落点之一。

首期最低要求：

- `entities` 或等价 registry 表
- 别名到规范实体 ID 的映射
- entity artifact 的持久化入口
- 可供 Retrieval Planner 做实体命中和 query expansion 的 lookup

### 7.4 Relation Layer

职责：

- 表达实体关系及其时间区间
- 支持未来的多实体查询、责任归属、项目关联和家庭成员关系

首期要求：

- 有 artifact 协议
- 有写入挂点
- 有检索接口
- 有首期可落盘的候选层，不允许直接丢弃 relation artifacts

首期不要求：

- 图数据库依赖
- 多跳图遍历作为主检索路径

首期建议物化方式：

- `relation_candidates`
  - 保存抽取得到但尚未进入主关系索引的 relation artifacts
- `relation_facts`
  - 保存已确认、可供当前读取链路使用的轻量关系记录

如果首期不启用 `relation_facts` 做主注入，至少也要把 relation artifacts 持久化到 `relation_candidates` 和 `memory_decision_log`，保证后续可重放、可回填、可重新归档。

---

## 8. 写入体系

### 8.1 统一写入流水线

所有写入来源都必须走同一条管线：

`Capture -> Extract -> Normalize -> Resolve -> Persist -> Index -> Schedule Consolidation`

各阶段职责：

- `Capture`
  - 捕获原始输入与上下文
- `Extract`
  - 生成候选 artifacts
- `Normalize`
  - 统一 slot、scope、subject、时间语义和 payload
- `Resolve`
  - 执行冲突判断与决策
- `Persist`
  - 路由到 Profile / Episode / Relation 对应后端
- `Index`
  - 更新检索索引和辅助 lookup
- `Schedule Consolidation`
  - 决定是否触发后台沉淀任务

### 8.2 写入来源分级

Sebastian 至少区分四类写入来源：

- `Explicit Write`
  - 用户明确要求记住
- `Conversational Inference`
  - 从普通对话中推断
- `Behavioral Observation`
  - 从用户长期行为、工具使用习惯中观察
- `Derived Consolidation`
  - 后台从会话或多条记忆归纳而来

这四类来源必须在 `source` 和 `provenance` 层面保留差异。

### 8.3 即时写入与后台沉淀分工

**即时写入负责：**

- 显式 `memory_save`
- 高确定性的 `fact` / `preference`
- 原始 `episode`
- 关键 `entity` 注册

**后台沉淀负责：**

- `summary`
- 跨多轮稳定偏好
- `relation`
- 习惯模式与阶段性结论
- 去重、压缩、置信度提升

### 8.4 Entity / Relation 首期落盘原则

即使 Phase B 尚未让 Relation Lane 成为主检索依赖，`entity` / `relation` artifacts 也不能在 Extract 或 Normalize 之后被直接忽略。

首期必须满足：

- `entity` 至少进入 `Entity Registry`
- `relation` 至少进入 `relation_candidates`
- 相关决策全部进入 `memory_decision_log`

这样后续 Phase D 才能基于已积累的 artifacts 做回填和重建，而不是重新修改上游协议。

---

## 9. 读取与注入架构

### 9.1 总原则

Sebastian 不做“统一 search top-k 然后塞进 prompt”，而做：

`Intent -> Retrieval Plan -> Assemble`

### 9.2 Intent 判定

每轮用户输入先做轻量记忆意图判断，至少识别：

- 是否在问长期偏好
- 是否在追问近期经历
- 是否在问当前状态
- 是否涉及实体关系
- 是否只是普通闲聊，不值得高成本检索

### 9.3 Retrieval Planner

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

Planner 在生成 retrieval plan 时，必须同时输出基于 `policy_tags` 的过滤条件，不能把权限过滤完全留到 prompt 组装末端。

### 9.4 四条检索通道

#### A. Profile Lane

职责：

- 提供高价值、稳定、当前有效的画像与偏好

特点：

- 条数小
- 高置信
- 即使不依赖当前 query 也可能注入

#### B. Context Lane

职责：

- 提供与当前用户消息强相关的动态事实与状态

特点：

- 强 query-aware
- 可结合当前 session 主题
- 侧重“当前正在做什么”

#### C. Episode Lane

职责：

- 提供过去发生过什么、怎么决定的、上次讨论到哪里

策略：

- 默认先查 `summary`
- 需要细节时再下钻原始 `episode`

#### D. Relation Lane

职责：

- 提供实体间关系与时间性状态

首期允许接口存在但数据量较少，后续随着 relation 层成熟逐步增强。

### 9.5 Assembler

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

### 9.6 Token Budget

各 lane 需要独立预算，不能共享抢占。

否则会出现：

- episode 抢光上下文
- preference 被挤掉
- 历史经历覆盖当前事实

### 9.7 当前真值与历史证据分离

注入语义必须区分：

- `current truth`
  - 仅来自 `active` 且在时间上有效的事实和关系
- `historical evidence`
  - 来自 episode、旧事实、旧关系和摘要

---

## 10. Consolidation 架构

### 10.1 Consolidation 不是单一 worker

后台沉淀至少分三类职责：

#### A. Session Consolidation

针对单次 session 在 `idle` / `stalled` / `completed` 后做：

- 生成阶段摘要
- 提取候选事实、偏好、关系
- 产生新的 artifacts

#### B. Cross-Session Consolidation

针对多个 session 做：

- 偏好强化
- 模式归纳
- 长期主题聚合
- 多来源证据合并

#### C. Memory Maintenance

负责：

- 过期
- 降权
- 重复压缩
- 摘要替换
- 索引修复

### 10.2 Consolidation 输入

后台沉淀不能只看原始对话，还应综合：

- session 消息
- 本次会话生成的 candidate artifacts
- 当前已有 active facts
- 最近相关 summaries
- 低置信、未决、待确认 artifacts

### 10.3 为什么要分三类

因为三者的关注点不同：

- Session Consolidation 关注“这一段对话发生了什么”
- Cross-Session Consolidation 关注“用户长期稳定呈现出什么模式”
- Maintenance 关注“系统里的记忆是否仍干净可用”

---

## 11. Memory Decision Log

### 11.1 设计结论

`memory_decision_log` 从第一阶段就应落数据，即使 UI 暂时不做。

### 11.2 记录内容

每次写入或维护动作至少记录：

- 原始输入来源
- 候选 artifacts
- 命中的 slot / subject / scope
- 冲突候选列表
- 决策结果：`ADD / SUPERSEDE / MERGE / EXPIRE / DISCARD`
- 决策原因摘要
- 执行该决策的 worker / 模型 / 规则版本
- 关联的旧记录 ID 和新记录 ID
- 时间戳

### 11.3 价值

这层日志是后续以下能力的基础：

- 调试“为什么记错了”
- 回答“为什么旧偏好被新偏好覆盖”
- 做人工审核 UI
- 做模型提示词和规则迭代对比
- 做自动回滚与补偿

如果首期不落这层数据，后面要补可审计性会非常被动。

---

## 12. 与 Sebastian 现有架构的集成

### 12.1 与现有 `working_memory` / `episodic_memory` 的关系

- `WorkingMemory`
  - 继续作为进程内、任务级临时状态，不纳入长期记忆体系
- 现有 `EpisodicMemory`
  - 继续保留为 session 历史读取入口
  - 但不再等同于“完整的回忆系统”

新的 Episode Store 应视为“在 session 历史之上建立的可检索回忆层”。

### 12.2 BaseAgent 集成点

后续实现时，至少需要以下 hook：

- turn 入口的 memory retrieval planner
- system prompt 组装时的 memory section assembler
- turn 结束或 session 转 idle 时的 consolidation scheduler
- 显式 `memory_*` 工具入口

### 12.3 工具层

首期建议保留以下工具作为用户可见接口：

- `memory_save`
- `memory_search`
- `memory_list`
- `memory_delete`

但工具层只负责触发统一写入/读取协议，不直接操作底层表。

---

## 13. 分阶段实现建议

### Phase A：协议先行

先定义：

- artifact schema
- slot registry
- resolution policy
- retrieval planner interface
- assembler interface
- decision log schema

目标：

- 把边界定稳
- 不急着追求能力最全

### Phase B：Profile + Episode 可用版

实现：

- `fact` / `preference` 的写入、更新、注入
- `episode` / `summary` 的存储与检索
- 基础 `Profile / Context / Episode` 三 lane
- 基础 decision log 落盘

目标：

- 先让 Sebastian “记住人”和“记住最近做过什么”

### Phase C：Consolidation 成熟版

实现：

- session consolidation
- cross-session preference strengthening
- maintenance worker
- 更稳定的 summary 策略

目标：

- 从“能记”升级到“越记越准”

### Phase D：Relation / Graph 增强

实现：

- entity normalization 强化
- relation artifact 正式入库
- relation lane 检索
- 时间区间关系和多实体关联

目标：

- 支撑复杂个人管家场景和未来多用户扩展

---

## 14. 实现侧规划与技术取舍

### 14.1 首版技术边界

首版记忆系统明确采用：

- **关系型数据库 + LLM**

首版明确不作为前置依赖：

- 独立向量数据库
- embedding 模型
- hybrid retrieval

原因：

- `ProfileMemory` 的主逻辑依赖 `slot + subject + status + validity`，不是向量检索问题
- `EpisodicMemory` 首版可通过 summary、全文检索、时间排序、entity 命中和当前 session 主题得到足够好的效果
- 当前最关键的工程问题是“记忆是否被正确提取、更新和使用”，而不是“语义召回是否做到最强”

### 14.2 向量能力的设计态度

虽然首版不实现向量能力，但架构上不阻止后续扩展。

后续如果需要增强 episode / summary / relation 的语义召回，可以新增：

- `EmbeddingProvider`
- `VectorIndex`

但这两者都应是增强层，而不是首版主路径依赖。

### 14.3 首版检索能力来源

在不使用 embedding 的前提下，首版检索主要依赖：

- 结构化查询
- 全文检索
- 时间排序
- entity 命中
- 当前 session / 项目上下文
- summary 优先、episode 下钻

这套方案应足以支撑首版的 `Profile / Context / Episode / Relation` 四 lane 检索。

### 14.4 LLM Provider 策略

记忆系统的模型来源不限定本地部署，可使用云 API，也可使用本地 provider。

关键原则：

- 能力和稳定性优先
- 部署方式可插拔
- 模型切换不应改变 memory 主协议

因此建议为记忆系统单独引入两个 provider binding：

- `memory_extractor`
- `memory_consolidator`

这两个 binding 可绑定到相同模型，也可分开绑定。

### 14.5 两类模型职责拆分

#### A. Memory Extractor

职责：

- 从用户消息、assistant 回复、tool 结果或会话片段中提取候选 artifacts
- 输出严格结构化 JSON
- 高调用频率，偏实时路径

要求：

- 快
- 稳
- 结构化输出一致
- 中文与中英混合语料理解可靠

#### B. Memory Consolidator

职责：

- 生成 session summary
- 执行 cross-session consolidation
- 对低置信候选做重判或归纳
- 提出偏好强化、关系沉淀、模式归纳建议

要求：

- 可比 extractor 稍慢
- 但输出稳定性和一致性要求更高
- 运行在异步、后台路径

### 14.6 LLM 只负责语义提炼，不负责数据库状态控制

以下能力应尽量 deterministic，而不是交给 LLM：

- 显式 `memory_save`
- slot registry 查询
- 单槽位冲突覆盖
- 生命周期更新
- `status / validity / policy_tags` 过滤
- retrieval lane 预算与过滤框架
- decision log 落盘

以下能力适合交给 LLM：

- artifact extraction
- session summary
- cross-session consolidation
- 低置信候选的语义重判

设计约束：

- LLM 永远不直接改数据库状态
- LLM 永远不直接决定最终 `ADD / SUPERSEDE / MERGE / EXPIRE`
- 最终写入前必须经过 Normalize 和 Resolve

---

## 15. Extractor / Consolidator 协议设计

### 15.1 设计原则

为避免模型切换影响主架构，记忆系统需要固定四份协议：

1. `ExtractorInput`
2. `CandidateArtifact`
3. `ConsolidatorInput`
4. `ConsolidationResult`

`Extractor` 输出候选对象，不直接输出最终记忆。
`Consolidator` 输出摘要和建议动作，不直接绕过 resolver。

### 15.2 ExtractorInput

Extractor 不应只看单句消息，而应接收一个小型上下文包：

```python
class ExtractorInput(TypedDict):
    task: Literal["extract_memory_artifacts"]
    subject_context: dict[str, Any]
    conversation_window: list[dict[str, Any]]
    known_slots: list[dict[str, Any]]
```

建议内容：

- `subject_context`
  - 默认主体、当前项目、当前 agent、session 主题
- `conversation_window`
  - 最近若干条消息或需提取的片段
- `known_slots`
  - 可供选择的 slot 定义，减少模型自由发挥

### 15.3 CandidateArtifact

Extractor 的输出不应直接使用 `MemoryArtifact`，而应使用更保守的 `CandidateArtifact`：

```python
class CandidateArtifact(TypedDict):
    kind: Literal["fact", "preference", "episode", "summary", "entity", "relation"]
    content: str
    structured_payload: dict[str, Any]
    subject_hint: str | None
    scope: str
    slot_id: str | None
    cardinality: Literal["single", "multi"] | None
    resolution_policy: Literal["supersede", "merge", "append_only", "time_bound"] | None
    confidence: float
    source: Literal["explicit", "inferred", "observed", "imported", "system_derived"]
    evidence: list[dict[str, Any]]
    valid_from: datetime | None
    valid_until: datetime | None
    policy_tags: list[str]
    needs_review: bool
```

字段语义：

- `subject_hint`
  - LLM 给出提示，不要求直接产出最终 `subject_id`
- `slot_id`
  - 能识别则给，不能识别允许为空
- `evidence`
  - 必须保留原始证据片段，为 decision log 和人工追溯服务
- `needs_review`
  - 当模型对提取结果没有足够把握时显式标记

Extractor 不负责：

- 生成最终 `subject_id`
- 决定最终冲突动作
- 直接写数据库
- 直接让旧记录失效

### 15.4 ConsolidatorInput

Consolidator 的输入必须比 Extractor 更完整：

```python
class ConsolidatorInput(TypedDict):
    task: Literal["consolidate_memory"]
    session_messages: list[dict[str, Any]]
    candidate_artifacts: list[CandidateArtifact]
    active_memories_for_subject: list[dict[str, Any]]
    recent_summaries: list[dict[str, Any]]
    slot_definitions: list[dict[str, Any]]
    entity_registry_snapshot: list[dict[str, Any]]
```

核心要求：

- 必须看到当前已有 active memories
- 必须看到 slot 定义
- 必须看到本次会话的候选 artifacts

否则 Consolidator 无法判断“这是新事实”还是“这是对旧事实的补充或更新”。

### 15.5 ConsolidationResult

Consolidator 的输出应是“摘要 + 候选对象 + 建议动作”：

```python
class ConsolidationResult(TypedDict):
    summaries: list[dict[str, Any]]
    proposed_artifacts: list[CandidateArtifact]
    proposed_actions: list[dict[str, Any]]
```

其中：

- `summaries`
  - session summary 或阶段 summary
- `proposed_artifacts`
  - 新提出的 fact / preference / relation / entity 候选
- `proposed_actions`
  - 例如强化置信度、建议过期、建议合并、建议下次复核

Consolidator 的职责是提出建议，而不是最终执行状态迁移。

### 15.6 Normalize / Resolve 的位置

在协议层必须明确：

- `Extractor`
  - 负责理解和提取
- `Normalize`
  - 负责 `subject_hint -> subject_id`、slot 校验、payload 标准化、时间标准化、policy tag 补全
- `Resolve`
  - 负责和现有 active memories 对比，并产出最终决策

Resolve 的标准输出建议至少包含：

```python
class ResolveDecision(TypedDict):
    decision: Literal["ADD", "SUPERSEDE", "MERGE", "EXPIRE", "DISCARD"]
    reason: str
    old_memory_ids: list[str]
    new_memory: dict[str, Any] | None
```

### 15.7 结构化输出要求

无论 provider 来自云 API 还是本地模型，Extractor 和 Consolidator 都必须走严格结构化输出：

- 固定 schema
- 固定枚举
- 低 temperature
- schema validation

如模型输出不满足 schema：

- 允许有限重试
- 失败后进入保守降级路径
- 不允许因为 schema 错误而直接写入主存储

---

## 16. 相对旧方案的关键升级

相较旧的 `semantic-memory-design`，本设计明确做出以下升级：

1. 不再把记忆系统主模型收敛为 `memories + memory_keys`
2. 不再将“语义记忆”理解为单表加全文检索
3. 不再把 retrieval 固定为 `profile/context` 双层注入
4. 不再把 consolidation 收敛为“session 结束后提取一次事实”
5. 明确引入：
   - artifact 层
   - slot / cardinality / resolution policy
   - current truth 与 historical evidence 分离
   - retrieval planner
   - relation lane
   - decision log

---

## 17. 风险与设计约束

### 17.1 主要风险

- 过早把 relation 层做成主查询依赖，会显著增加首期实现复杂度
- 如果 slot registry 设计随意，后面会造成大量冲突判断失准
- 如果 retrieval planner 缺失，后续容易滑回“top-k 全塞 prompt”的低质量实现

### 17.2 必须坚持的约束

- 所有写入路径统一产出 artifacts
- 所有冲突判断基于 slot，而不是纯文本相似度
- 所有自动注入都必须区分当前真值与历史证据
- 所有重要决策都要进入 decision log

---

## 18. 本文档后的执行建议

本文档完成后，后续工作应按以下顺序推进：

1. 基于本 spec 写 implementation plan
2. 先落协议、schema 和接口
3. 再逐阶段接入 Profile、Episode、Consolidation、Relation

在 implementation plan 完成之前，不应再沿用旧 spec 的单表主模型继续推进实现。

---

*← 返回 [Spec 根索引](../../../docs/architecture/spec/INDEX.md)*
