# Dynamic Slot System — Design Spec

**Date**: 2026-04-20
**Status**: Draft — pending user review
**Scope**: `sebastian/memory/` 记忆模块
**Related**: `docs/architecture/spec/memory/INDEX.md`（§7 write-pipeline §9 implementation）、`sebastian/memory/data-flow.md`

---

## 1. Goals

让记忆系统从"只接受 6 个硬编码 slot"升级为"运行时可扩展的 slot 登记系统"，具体：

1. 新增 `slot_definitions` 数据库表，持久化所有 slot 定义（builtin + LLM 提议）
2. `SlotRegistry` 支持启动加载、运行时动态注册
3. Extractor / Consolidator 在无法匹配 `known_slots` 时，可以提议新 slot（带命名规则校验）
4. Extractor 自行判定 `kind` 并选/提 slot，**调用方（memory_save tool / SessionConsolidationWorker）对 kind 无感知**
5. 抽象 `SlotProposalHandler` 共享组件，Extractor / Consolidator 共用注册 + 并发冲突处理逻辑
6. 补齐 3 个 seed slot（`user.profile.name` / `user.profile.location` / `user.profile.occupation`）
7. Prompt 中 `known_slots` 按 kind 分组呈现，防止上下文膨胀

## 2. Non-Goals

- **多进程 / 多机部署场景**：当前设计假定单 Python 进程，多进程扩展列为 §13 未来工作
- **Slot 生命周期管理**：deprecated / merged_into / rename 等操作不在本 spec，走人工 migration
- **Embedding-based slot 预筛选**：等实际 slot 数膨胀到 50+ 再做
- **已存在 slot 的 metadata 更新**：永不更新，LLM 只能"新增"不能"改"
- **Retrieval 路径优化**：属于 Spec B，另写

---

## 3. 现状（v0.x）

- `sebastian/memory/slots.py` 定义 `_BUILTIN_SLOTS`（6 条硬编码）+ `SlotRegistry`
- `DEFAULT_SLOT_REGISTRY = SlotRegistry()` 模块级单例
- `SlotRegistry.validate_candidate()` 对 `kind ∈ {fact, preference}` 且 `slot_id` 不在 registry 里的 candidate 抛 `InvalidCandidateError`
- 无 `slot_definitions` DB 表，无运行时 register API，无 LLM 提议通道
- Extractor prompt 极简（`extraction.py:47-53`），不含 slot 选择规则
- Consolidator `ConsolidationResult` 缺 `proposed_slots` 字段

---

## 4. 术语

| 术语 | 含义 |
|---|---|
| **slot** | 语义容器，三段式命名如 `user.profile.like_book`。定义存储结构与冲突策略，本身是**不可变元数据** |
| **artifact** | 挂在 slot 下的具体记忆实例，如"用户喜欢《三体》" |
| **kind** | 记忆类型（fact / preference / episode / summary / entity / relation） |
| **cardinality** | slot 允许挂多少 artifact：`SINGLE` 只一条，`MULTI` 可多条 |
| **resolution_policy** | 写入冲突策略：`SUPERSEDE` / `MERGE` / `APPEND_ONLY` / `TIME_BOUND` |
| **ProposedSlot** | LLM 提议的新 slot，未注册前不能被 artifact 引用 |
| **proposal winner** | 并发注册同一 slot_id 时，首个 INSERT 成功的 worker |

---

## 5. 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│ memory_save tool                  SessionConsolidationWorker │
│      │                                   │                   │
│      ▼                                   ▼                   │
│   MemoryExtractor ◀───── 共用 ─────▶ MemoryConsolidator     │
│      │                                   │                   │
│      │  Output:                          │  Output:          │
│      │   candidates + proposed_slots     │   candidates      │
│      │                                   │   + proposed_slots│
│      │                                   │   + summaries     │
│      │                                   │   + EXPIREs       │
│      ▼                                   ▼                   │
│   ┌─────────────────────────────────────────────────┐        │
│   │          process_candidates() pipeline          │        │
│   │                                                 │        │
│   │   Step 1: for p in proposed_slots:              │        │
│   │            SlotProposalHandler.register_or_reuse│        │
│   │                                                 │        │
│   │   Step 2: for c in candidates:                  │        │
│   │            validate → resolve → persist → log  │        │
│   └─────────────────────────────────────────────────┘        │
│            │                                                 │
│            ▼                                                 │
│   ┌─────────────┐   ┌─────────────────┐                     │
│   │SlotRegistry │   │SlotDefinitionStore│                   │
│   │ (内存单例)  │◀──│   (DB CRUD)      │                   │
│   └─────────────┘   └─────────────────┘                     │
│         ▲                   │                                │
│         │                   ▼                                │
│   bootstrap_from_db()  slot_definitions 表                   │
│   (服务启动时一次)                                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Schema 变更

### 6.1 新增 `slot_definitions` 表

```sql
CREATE TABLE slot_definitions (
    slot_id              TEXT PRIMARY KEY,           -- "user.profile.like_book"
    scope                TEXT NOT NULL,              -- user / session / project / agent
    subject_kind         TEXT NOT NULL,              -- user / project / agent
    cardinality          TEXT NOT NULL,              -- single / multi
    resolution_policy    TEXT NOT NULL,              -- supersede / merge / append_only / time_bound
    kind_constraints     TEXT NOT NULL,              -- JSON array: ["fact", "preference"]
    description          TEXT NOT NULL,              -- 人类可读描述，也是 LLM 选 slot 的依据
    source               TEXT NOT NULL,              -- builtin / llm_proposed
    proposed_by          TEXT,                       -- extractor / consolidator / NULL (builtin)
    proposed_in_session  TEXT,                       -- session_id / NULL (builtin)
    created_at           TIMESTAMP NOT NULL
);

CREATE INDEX idx_slot_def_scope ON slot_definitions(scope);
CREATE INDEX idx_slot_def_source ON slot_definitions(source);
```

**字段决策**：
- `slot_id` PRIMARY KEY + UNIQUE 天然解决并发冲突（见 §10.2）
- `kind_constraints` 用 JSON 而非 join 表：slot 数量级小，查询都按 slot_id 走 PK，不需要 kind 反查
- `source` 区分 builtin / llm_proposed 便于后续治理与 observability
- 无 `deprecated` / `merged_into` 字段：生命周期走人工 migration（§2 Non-Goal）

### 6.2 Alembic migration

新建 `sebastian/store/migrations/versions/xxxx_add_slot_definitions.py`：
- upgrade(): `CREATE TABLE slot_definitions (...)` + 两个索引
- downgrade(): `DROP TABLE slot_definitions`
- **同 migration 内**：把 6 个 builtin slot 作为初始数据 INSERT（source='builtin', proposed_by=NULL）

---

## 7. 新组件

### 7.1 `sebastian/memory/slot_definition_store.py`

```python
class SlotDefinitionStore:
    """slot_definitions 表的 CRUD 封装，纯 DB 层，无业务逻辑。"""

    def __init__(self, session: AsyncSession) -> None: ...

    async def insert(self, record: SlotDefinitionRecord) -> None:
        """INSERT 一行；slot_id 冲突时抛 sqlalchemy.exc.IntegrityError。"""

    async def get(self, slot_id: str) -> SlotDefinitionRecord | None: ...

    async def list_all(self) -> list[SlotDefinitionRecord]: ...
```

`SlotDefinitionRecord` 是 SQLAlchemy ORM 模型，和 `SlotDefinition` 之间提供 `to_schema()` / `from_schema()` 互转。

### 7.2 `sebastian/memory/slot_proposals.py`

```python
class InvalidSlotProposalError(SebastianError):
    """Slot proposal 违反命名规则 / 字段约束。"""

class SlotProposalHandler:
    """共享组件：把 ProposedSlot 注册到系统（DB + in-memory registry）。

    不含 LLM 调用 / 不含重试循环 —— 重试策略由调用方（Extractor / Consolidator）掌控。
    """

    def __init__(
        self,
        store: SlotDefinitionStore,
        registry: SlotRegistry,
    ) -> None: ...

    async def register_or_reuse(
        self,
        proposed: ProposedSlot,
        *,
        proposed_by: Literal["extractor", "consolidator"],
        proposed_in_session: str | None,
    ) -> SlotDefinition:
        """
        流程：
          1. 命名校验（三段式 {scope}.{category}.{attribute}）
          2. 字段校验（cardinality/resolution_policy 合法组合）
             → 任一失败抛 InvalidSlotProposalError
          3. 查 registry：已存在 → 直接返回（不覆盖 metadata）
          4. 不存在 → INSERT slot_definitions
             - 成功 → registry.register() → 返回
             - IntegrityError (并发 race) → rollback → re-fetch → 比对差异写 trace → 返回赢家
        """
```

**命名规则**：
- 形如 `^[a-z][a-z_]*\.[a-z][a-z_]*\.[a-z][a-z_]*$` 三段纯小写 + 下划线
- 第一段必须 ∈ {user, session, project, agent}（和 MemoryScope 对齐）
- 总长 ≤ 64 字符
- 违反 → `InvalidSlotProposalError("slot_id 'X' 不符合命名规则")`

**字段组合合法性**：
- `kind_constraints` 必须至少 1 项，且都是合法 MemoryKind
- 禁止 `cardinality=single + resolution_policy=append_only`（矛盾）
- `resolution_policy=time_bound` 要求 kind_constraints 至少含 `fact` 或 `preference`

### 7.3 `ProposedSlot` 类型

加到 `sebastian/memory/types.py`：

```python
class ProposedSlot(BaseModel):
    """LLM 提议的新 slot，由 Extractor/Consolidator 产出，经 SlotProposalHandler 验证后注册。"""
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    scope: MemoryScope
    subject_kind: str
    cardinality: Cardinality
    resolution_policy: ResolutionPolicy
    kind_constraints: list[MemoryKind]
    description: str
```

---

## 8. `SlotRegistry` 扩展

在 `sebastian/memory/slots.py` 加两个方法：

```python
class SlotRegistry:
    # ... 既有方法 ...

    async def bootstrap_from_db(self, store: SlotDefinitionStore) -> None:
        """服务启动时调用一次，把 DB 里所有 slot 灌入内存。

        内部实现：
          - 先清空 self._slots（除了 builtin？不，builtin 已在 migration 写进 DB）
          - rows = await store.list_all()
          - for r in rows: self._slots[r.slot_id] = r.to_schema()
        """

    def register(self, schema: SlotDefinition) -> None:
        """运行时注册。覆盖同 slot_id 的现存条目（正常情况下 DB 已保证唯一，
        这里仅防御性覆盖，不触发数据一致性问题）。"""
        self._slots[schema.slot_id] = schema
```

**`_BUILTIN_SLOTS` 保留在代码里作为 seed fallback**，但构造函数不再自动加载。生产路径走 migration → DB → bootstrap，测试可以 `SlotRegistry(slots=_BUILTIN_SLOTS)` 注入。

**启动 hook**（gateway lifespan）：

```python
# sebastian/gateway/app.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    ...
    async with state.db_factory() as session:
        slot_store = SlotDefinitionStore(session)
        await DEFAULT_SLOT_REGISTRY.bootstrap_from_db(slot_store)
    ...
```

---

## 9. Extractor / Consolidator 变更

### 9.1 Extractor 契约调整（核心）

**原则**：Extractor 自己判 kind + 选/提 slot，调用方无感知。

**`ExtractorInput` 保持不变**：`{task, subject_context, conversation_window, known_slots}`
- `known_slots` 依旧由 **memory 模块内部** 从 `DEFAULT_SLOT_REGISTRY.list_all()` 注入
- 调用方（memory_save tool / Consolidator）不传 kind，不过滤 slot

**`ExtractorOutput` 扩展**：

```python
class ExtractorOutput(BaseModel):
    artifacts: list[CandidateArtifact]
    proposed_slots: list[ProposedSlot] = []   # ← 新增
```

**调用链调整**：`MemoryExtractor.extract()` 返回类型从 `list[CandidateArtifact]` 改为 `ExtractorOutput`，所有上游相应适配。

### 9.2 Consolidator 契约调整

`ConsolidationResult` 加字段：

```python
class ConsolidationResult(BaseModel):
    summaries: list[...]
    proposed_artifacts: list[CandidateArtifact]
    proposed_actions: list[...]
    proposed_slots: list[ProposedSlot] = []   # ← 新增
```

### 9.3 重试机制（方案 C + X）

**Extractor 内联重试**（方案 C：最多 1 次额外重试）：

```
第一次调用 LLM
  ↓
解析 ExtractorOutput
  ↓
for p in proposed_slots:
    try: SlotProposalHandler.register_or_reuse(p)
    except InvalidSlotProposalError: 收集到 failed_proposals
  ↓
if failed_proposals:
    第二次调用 LLM（在 system prompt 追加失败反馈）
    "以下 slot 提议不合规，请换命名重新给出：{failed_proposals}"
    ↓
    再次解析 + 再次 register_or_reuse
    ↓
    仍失败的 ProposedSlot：丢弃
    ↓
    受影响的 candidate（引用了被丢弃 slot 的）的处理：
      → 方案 X：将 candidate.slot_id 置 None 后交给 validate_candidate
         - 若 kind ∈ {fact, preference}：
             validate_candidate 规则要求 slot_id 存在
             → 当前规则下会被 DISCARD + log(reason="slot_proposal_failed_no_fallback")
         - 若 kind ∈ {episode, summary, entity, relation}：
             slot_id=None 合法，正常走 resolver（episode/summary 会 ADD，
             entity/relation 按各自逻辑）
      → 保留 candidate 流入 validate_candidate，由 validate 决定去留；
         **不跳过 validate 做绕过**，保证规则一致性
```

**Consolidator 的重试**走 spec §9.1 协议（最多 N 次，在 consolidation.py 已有框架），与 Extractor 类似但循环次数更高（建议 3 次）。

### 9.4 Trace 事件

| 事件 | 字段 |
|---|---|
| `slot.proposal.accepted` | `slot_id`, `proposed_by`, `session_id` |
| `slot.proposal.rejected` | `slot_id`, `reason`, `proposed_by`, `retry_attempt` |
| `slot.proposal.concurrent_lost` | `slot_id`, `winner_fields`, `loser_fields`, `proposed_by` |
| `slot.proposal.candidate_downgrade` | `slot_id`, `candidate_kind`, `outcome` (validate_discarded / kept_as_orphan) |

---

## 10. Pipeline 集成

### 10.1 `process_candidates()` 签名扩展

```python
async def process_candidates(
    candidates: list[CandidateArtifact],
    proposed_slots: list[ProposedSlot],   # ← 新增
    *,
    session_id: str,
    agent_type: str,
    db_session: AsyncSession,
    profile_store: ProfileMemoryStore,
    episode_store: EpisodeMemoryStore,
    entity_registry: EntityRegistry,
    decision_logger: MemoryDecisionLogger,
    slot_registry: SlotRegistry,
    slot_proposal_handler: SlotProposalHandler,   # ← 新增
    worker_id: str,
    model_name: str | None,
    rule_version: str,
    input_source: dict[str, Any],
    proposed_by: Literal["extractor", "consolidator"],   # ← 新增（给 trace 用）
) -> PipelineResult:
    ...
```

**处理顺序**：

```python
# Step 1: 先登记所有 proposed_slots
registered_or_reused: list[SlotDefinition] = []
failed_slot_ids: set[str] = set()

for p in proposed_slots:
    try:
        schema = await slot_proposal_handler.register_or_reuse(
            p, proposed_by=proposed_by, proposed_in_session=session_id,
        )
        registered_or_reused.append(schema)
    except InvalidSlotProposalError as e:
        failed_slot_ids.add(p.slot_id)
        trace("slot.proposal.rejected", slot_id=p.slot_id, reason=str(e), ...)

# Step 2: candidates 循环 —— 受影响的 candidate 走 fallback
for c in candidates:
    if c.slot_id in failed_slot_ids:
        c = c.model_copy(update={"slot_id": None})
        trace("slot.proposal.candidate_downgrade", ...)
    # ... 后续 validate → resolve → persist → log 不变
```

### 10.2 并发冲突（"复用赢家"机制）

两个 worker 几乎同时提议同一 slot_id：

```
Worker A                       Worker B
register_or_reuse(X)           register_or_reuse(X)
  registry.get(X) → None         registry.get(X) → None
  store.insert(X) ✓              store.insert(X) ✗ IntegrityError
  registry.register(X)           rollback
  return schema(A)               store.get(X) → schema(A)
                                 比对 A 和 B 的字段差异
                                 trace("slot.proposal.concurrent_lost",
                                       winner_fields={...A...},
                                       loser_fields={...B...})
                                 return schema(A)
```

两边最终拿到的 schema 完全一致，A、B 的 candidate 都能通过 validate_candidate。

---

## 11. Prompt 模板

### 11.1 `known_slots` 按 kind 分组呈现

**呈现格式**（注入 prompt 的 user_content 里）：

```json
{
  "subject_context": {...},
  "conversation_window": [...],
  "known_slots_by_kind": {
    "fact": [
      {"slot_id": "user.profile.name", "cardinality": "single", "resolution_policy": "supersede", "description": "用户姓名"},
      {"slot_id": "user.profile.location", "cardinality": "single", "resolution_policy": "supersede", "description": "用户所在地"},
      ...
    ],
    "preference": [
      {"slot_id": "user.preference.language", ...},
      ...
    ],
    "entity": [...],
    "relation": [...]
  }
}
```

实现：memory 模块内部在组装 ExtractorInput 时，把 `SlotRegistry.list_all()` 按 `kind_constraints` 分桶。若一个 slot 含多个 kind，复制到所有相关桶。

### 11.2 Extractor system prompt（新增 slot 选择 / 提议规则）

```
You are a memory extraction assistant. Analyze the conversation and extract memory artifacts.

# Task
For each piece of memorable content, output a CandidateArtifact with:
- kind: one of {fact, preference, episode, summary, entity, relation}
- slot_id: MUST match a registered slot (see known_slots_by_kind) OR be null

# Slot Selection Rules
1. Only kind=fact and kind=preference REQUIRE a slot_id. Others may have slot_id=null.
2. ALWAYS prefer reusing an existing slot from known_slots_by_kind[kind] that semantically matches.
3. If NO existing slot fits, you may propose a new slot. Output it in "proposed_slots".
   - naming MUST be: {scope}.{category}.{attribute}, all lowercase, underscores allowed
   - scope MUST be one of: user / session / project / agent
   - total length ≤ 64 chars
   - description MUST be in Chinese, ≤ 40 chars
4. When you propose a slot AND produce an artifact using it in the same output:
   - The artifact's slot_id must equal the proposed slot_id.
   - The pipeline will register the slot first, then store the artifact.

# Cardinality / Resolution Policy Reference Table
Use this table when proposing new slots:

| Semantic Pattern | cardinality | resolution_policy | Example |
|---|---|---|---|
| 唯一属性（姓名/时区/当前焦点） | single | supersede | user.profile.name |
| 可枚举爱好（喜欢的书/音乐/电影） | multi | append_only | user.profile.like_book |
| 可合并集合（擅长领域列表） | multi | merge | user.profile.skill |
| 时效性状态（本周安排/年度目标） | single | time_bound | user.goal.current_quarter |
| 行为/事件记录 | multi | append_only | user.behavior.login_event |

# Output Format
Respond with ONLY valid JSON:
{
  "artifacts": [<CandidateArtifact>, ...],
  "proposed_slots": [<ProposedSlot>, ...]
}

No explanation, no markdown, no code blocks.
```

### 11.3 Extractor 第二次重试（slot 命名失败后）

第二次调用时在 system 前追加：

```
# Retry Context
Previous attempt proposed slots that were rejected:
{failed_proposals_json}

Reject reasons: {reason_summary}

Please rename and resubmit. Do not repeat the same names.
```

### 11.4 Consolidator prompt 扩展

在现有 Consolidator prompt 末尾追加相同的 "Slot Selection Rules" + "Cardinality Reference Table"，并把输出 schema 的 `proposed_slots` 字段加入 JSON 结构说明。重试协议复用 Consolidator 现有的 spec §9.1 多轮迭代（上限 3 次）。

---

## 12. Seed Slots 补齐

在 migration 的 INSERT 阶段追加 3 个（与现有 6 个合并为 9 个 builtin）：

| slot_id | scope | subject_kind | cardinality | resolution_policy | kind_constraints | description |
|---|---|---|---|---|---|---|
| `user.profile.name` | user | user | single | supersede | [fact] | 用户姓名 |
| `user.profile.location` | user | user | single | supersede | [fact] | 用户所在地 |
| `user.profile.occupation` | user | user | single | supersede | [fact] | 用户职业 |

---

## 13. 未来工作（Non-Goals 的 TODO 痕迹）

代码里以 `# TODO(dynamic-slot-multiprocess):` 注释标记，spec 记录：

1. **多进程同步**：当前 `SlotRegistry` 内存单例仅对单 Python 进程生效。多进程部署需：
   - 方案 A：`register_or_reuse()` 前 `registry.refresh_from_db()`（牺牲性能换一致性）
   - 方案 B：DB 层 listen/notify 或 Redis pub/sub 广播 slot 增量
2. **Slot embedding 预筛**：slot 数量突破 50 时，prompt token 开销不可忽略。届时：
   - 在 `slot_definitions` 加 `embedding_ref` 列
   - Extractor 调用前用内容 embedding 召回 top-K slot
3. **Slot 生命周期**：deprecated / merged_into / rename，走人工 migration 不在自动化范围

---

## 14. 测试期望

单元测试（`tests/unit/memory/`）：

1. `test_slot_definition_store.py`
   - insert / get / list_all 基本 CRUD
   - UNIQUE 冲突抛 IntegrityError
2. `test_slot_proposals.py`
   - 合法 proposal 成功 register + registry 内存同步
   - 命名违规（段数不对 / 含大写 / 超长）抛 InvalidSlotProposalError
   - cardinality=single + resolution_policy=append_only 组合抛 InvalidSlotProposalError
   - 已存在 slot_id 直接返回既有 schema（不覆盖 metadata）
   - 并发 race：mock IntegrityError 路径返回赢家
3. `test_slot_registry_bootstrap.py`
   - bootstrap_from_db 把 DB 行灌回内存
   - register() 运行时同步
4. `test_extraction_with_proposed_slots.py`
   - 返回 ExtractorOutput 含 proposed_slots
   - 第二次重试拿到失败反馈
5. `test_pipeline_proposed_slots_flow.py`
   - proposed_slots 先于 candidates 处理
   - slot 注册失败时对应 candidate 降级为无 slot（不整体 DISCARD）

集成测试（`tests/integration/memory/`）：

6. `test_memory_save_proposes_new_slot.py`
   - memory_save 触发 Extractor 提议新 slot
   - DB `slot_definitions` 多一行
   - `DEFAULT_SLOT_REGISTRY` 内存同步
   - 后续第二条 memory_save 引用该 slot 成功入库
7. `test_session_consolidation_proposes_slots.py`
   - 会话结束触发 Consolidator，结果中含 proposed_slots
   - slot 被注册，相关 artifact 正确落库

---

## 15. 向后兼容

- 6 个现有 builtin slot 语义保持不变（migration 从 `_BUILTIN_SLOTS` seed 进 DB）
- `ExtractorOutput` 现有字段不变，仅追加 `proposed_slots`（默认 `[]`）
- `ConsolidationResult` 同上
- `process_candidates` 签名扩展，调用方（memory_save tool / Consolidator worker）需相应更新一次
- 测试中 `SlotRegistry(slots=...)` 注入路径不变，单测可继续绕过 DB

---

## 16. 验收标准

- [ ] `slot_definitions` 表创建、migration 可双向迁移
- [ ] 9 个 builtin slot（含 3 个新 seed）首次 migration 后存在于 DB
- [ ] 服务启动时 `DEFAULT_SLOT_REGISTRY.bootstrap_from_db()` 执行一次，失败阻止启动
- [ ] `SlotProposalHandler.register_or_reuse()` 命名校验、字段组合校验、并发冲突全部测试通过
- [ ] Extractor / Consolidator 能产出 proposed_slots，且重试机制（C + X）生效
- [ ] `process_candidates()` 处理顺序正确（slot 先 / candidate 后，降级路径工作）
- [ ] Trace 事件全部落到 `memory_decision_log` 表
- [ ] 所有相关单测 + 集成测试通过

---

## 17. 开放问题（spec 落地过程中可能出现的决策点）

这些**不阻碍 spec 通过**，但实现计划里需要明确：

1. Migration 执行时机：是否阻塞启动？（建议阻塞，否则 registry 灌空有副作用）
2. Extractor 首次 LLM 调用若返回 proposed_slots 且 artifact，register 失败时第二次重试要不要把 artifact 也清掉？—— 当前设计保留 artifact 做降级，但可能 prompt 上难让 LLM 产生"不含新 slot 的 artifact"
3. Consolidator 的 §9.1 重试上限是否复用现有配置？需查 consolidation.py 当前值
