---
version: "1.0"
last_updated: 2026-04-19
status: planned
---

# Memory Artifact（记忆产物）与冲突模型

> 模块索引：[INDEX.md](INDEX.md)

---

## 1. 核心原则

Sebastian 不直接把原始输入写入某个固定 memory 表，而是先把输入转成标准化 `MemoryArtifact`，再由路由层分发到不同记忆后端。

`artifact`（记忆产物）是统一逻辑协议，不等于数据库表。

---

## 2. Artifact 类型

| 类型 | 说明 |
|------|------|
| `fact`（事实） | 可被后续事实覆盖、失效或并存的结构化陈述 |
| `preference`（偏好） | 用户偏好；本质属于 fact，但注入优先级和更新策略特殊 |
| `episode`（经历） | 实际发生过的事件、对话、任务、决策或经历 |
| `summary`（摘要） | 对一个或一组 episode 的压缩表述 |
| `entity`（实体） | 需要长期识别和跟踪的对象 |
| `relation`（关系） | 实体之间的语义关系，可带时间区间和排他规则 |

---

## 3. MemoryArtifact 字段

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

首期不实现 embedding 时，`embedding_ref` 保留为空即可。

---

## 4. 必须从 Day 1 保留的语义

- `scope`（作用域）
  - 限定记忆归属范围，例如 `user` / `session` / `project` / `agent`
- `subject_id`（主体 ID）
  - 限定记忆主体，防止未来多用户、多项目、多 agent 情况下串数据
- `slot_id`（语义槽位）+ `cardinality`（单值/多值）+ `resolution_policy`（冲突解决策略）
  - 让冲突消解成为显式协议，而不是在 resolver 中临时猜测
- `source`（来源）+ `confidence`（置信度）+ `provenance`（来源证据）
  - 用于冲突判断、审计回溯和后续人工核查
- `status`（状态）+ `valid_from`（生效时间）+ `valid_until`（失效时间）
  - 表达动态状态，避免未来为“当前值”和“历史值”做破坏性迁移
- `structured_payload`（结构化载荷）
  - 让记忆不仅是可读文本，也能被程序化处理
- `links`（关联）
  - 作为关系层和摘要层的桥接字段

---

## 5. Slot Registry（语义槽位注册表）

`slot_id`（语义槽位 ID）不应是自由文本，而应关联到稳定的 slot registry（语义槽位注册表）。

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
- 如果上游只能产出模糊候选，必须在 Normalize 阶段显式落成 `slot_id` 或标记为“未归槽”

---

## 6. 生命周期模型

| 状态 | 说明 |
|------|------|
| `active`（有效） | 当前有效，可参与检索与自动注入 |
| `superseded`（被取代） | 被更新事实取代，但保留历史 |
| `expired`（已过期） | 因时间条件自然失效 |
| `deleted`（已删除） | 被用户或系统显式删除，不再参与正常召回 |

记忆不是 KV 配置项。事实更新默认应保留历史轨迹，而不是直接覆盖旧行。

---

## 7. 冲突决策流程

每条新 artifact 统一走三段式：

1. `Resolve`（解析冲突）
   - 在同 subject、同 scope、同 slot 下找候选冲突对象
2. `Decide`（做出决策）
   - 只允许输出 `ADD / SUPERSEDE / MERGE / EXPIRE / DISCARD`
3. `Apply`（应用决策）
   - 按决策落库、写日志、更新索引

文本相似度最多只能用于召回候选，不允许直接决定覆盖关系。

---

## 8. 默认策略

| Artifact | 默认规则 |
|----------|----------|
| `preference` | 单槽位、单活跃记录、默认 `SUPERSEDE` |
| `fact(single)` | 单槽位、单活跃记录、默认 `SUPERSEDE` |
| `fact(multi)` | 多值并存，去重后 `ADD` 或 `MERGE` |
| `episode` | append-only，仅做精确去重 |
| `summary` | 可替代默认摘要，但保留历史摘要 |
| `relation(exclusive)` | 时间边界覆盖，旧关系写 `valid_until` |
| `relation(non_exclusive)` | 并存 |

---

## 9. 可信度优先级

冲突决策优先遵循：

1. `explicit` 高于 `inferred`
2. 新的明确表达高于旧的明确表达
3. 高置信度高于低置信度
4. 更具体的结构化陈述高于模糊概括

---

*← 返回 [Memory 索引](INDEX.md)*
