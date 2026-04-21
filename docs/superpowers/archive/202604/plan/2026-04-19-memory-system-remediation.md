# Memory 系统修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-04-19 审核报告中识别的 Memory 系统 Phase A/B/C 全部 P0/P1/P2 问题以及测试薄弱点，让记忆系统对齐 `docs/architecture/spec/memory/` 所有关键约束。

**Architecture:** 在现有 Phase A/B/C 代码基础上做补丁与扩展，不重构。按依赖关系分 7 组（R-A 契约基础 → R-B P0 bug → R-C 写入分发/Subject → R-D Retrieval 四通道 → R-E Consolidation 硬化 → R-F 启动与基建 → R-G 测试补强），每组独立可合并。Phase R-A/R-B 是线上 bug 必须先修；R-C 之后才允许 Phase C Consolidator 正式启用；R-D/R-E 补齐 spec 核心价值；R-F/R-G 收尾。

**Tech Stack:** Python 3.12、Pydantic v2、SQLAlchemy async、SQLite + FTS5、jieba、pytest、pytest-asyncio。

---

## 源 Spec 与审核依据

- `docs/architecture/spec/memory/INDEX.md` 以及 overview/artifact-model/storage/write-pipeline/retrieval/consolidation/implementation.md
- 审核报告（本 plan 所在 session 的上游对话）

## 分支与提交

- 在现有 `feat/agent-memory` 分支继续工作；大组任务完成后开 PR 合入 `main`。
- 每组（R-A … R-G）内部保持一个 commit 一个原子动作，commit message 格式 `fix(memory): 中文摘要` 或 `refactor(memory): 中文摘要` 或 `test(memory): 中文摘要`。
- 结尾 `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`。
- 禁止 `git add .`；使用 `git add <具体文件>`。

## 文件改动总览

**新增**：
- `sebastian/memory/subject.py`（subject resolver）
- `sebastian/memory/errors.py`（MemoryError 族）
- `sebastian/memory/write_router.py`（按 kind 分发的写入路由）

**修改**：
- `sebastian/memory/types.py`（枚举大写；Pydantic `extra="forbid"`；`MemorySummary.scope` 枚举化；`ResolveDecision` model_validator）
- `sebastian/memory/profile_store.py`（`search_active` 加 `valid_until` 过滤；scope 过滤补 `subject_id`）
- `sebastian/memory/episode_store.py`（FTS MATCH 转义）
- `sebastian/memory/resolver.py`（source/confidence 优先级；SUPERSEDE 前置比较；provenance 注入 session_id）
- `sebastian/memory/consolidation.py`（ConsolidatorInput 上下文组装；summary 经 resolver 写 log；proposed_actions 执行；LLM 异常兜底；catch-up sweep；subject 走 resolver；MemorySummary 枚举）
- `sebastian/memory/extraction.py`（接入生产路径：由 Worker 调用；同样加 LLM 异常兜底）
- `sebastian/memory/retrieval.py`（RetrievalPlan 扩 4 lane；Context/Relation Lane；Assembler 完整过滤；显式 current/historical 标题；Intent planner 增强）
- `sebastian/memory/entity_registry.py`（SQL-based indexed lookup，替换全表扫描）
- `sebastian/memory/slots.py`（SebastianError 子类；validate_candidate 被写路径调用）
- `sebastian/memory/decision_log.py`（provenance 含 session_id；支持 model 字段透传）
- `sebastian/memory/startup.py`（调用 `sync_jieba_terms`；seed 内建 slots；catch-up sweep 入口）
- `sebastian/capabilities/tools/memory_save/__init__.py`（DISCARD 写 log；按 kind 分发到 EntityRegistry / relation_candidates；validate_candidate）
- `sebastian/capabilities/tools/memory_search/__init__.py`（结构化 citations 输出）
- `sebastian/core/base_agent.py`（subject resolver 替换硬编码 "owner"）
- `sebastian/store/models.py`（RelationCandidate 加 `valid_from/valid_until/status`）
- `sebastian/gateway/app.py`（lifespan 调 `sync_jieba_terms` + seed slots + catch-up sweep）

**测试**：
- 修 `tests/unit/memory/test_consolidation.py` 假阳性 `test_does_not_write_to_db`
- 补 `tests/unit/memory/test_resolver.py` 缺失分支
- 新增 `tests/integration/test_memory_supersede_chain.py` 全链路 SUPERSEDE
- 新增 `tests/integration/test_memory_consolidation_concurrency.py` 并发幂等
- 改 `tests/unit/memory/test_extraction.py` / `test_consolidation.py` 断言 LLM 参数
- 新增 `tests/unit/memory/test_write_router.py`、`test_errors.py`、`test_subject.py`
- 新增 `tests/integration/test_memory_catchup_sweep.py`

## 全局验证（每组 PR 前必须跑）

- [ ] `ruff check sebastian/ tests/`
- [ ] `ruff format --check sebastian/ tests/`
- [ ] `mypy sebastian/`
- [ ] `pytest`
- [ ] 更新 `CHANGELOG.md` 的 `[Unreleased]` 段（按 Added/Changed/Fixed 分类）
- [ ] 不改 Android 代码就不跑 Android CI

---

## Phase R-A：契约基础修复（先行，解锁后续任务）

### Task A1：`MemoryDecisionType` 枚举值改大写

**Files:**
- Modify: `sebastian/memory/types.py:41-46`
- Modify: `sebastian/memory/decision_log.py:28`（删除 `.value.upper()`）
- Test: `tests/unit/memory/test_types.py`、`tests/unit/memory/test_decision_log.py`

- [ ] **Step 1：先写失败测试**

在 `tests/unit/memory/test_types.py` 末尾加：

```python
def test_memory_decision_type_values_are_uppercase():
    from sebastian.memory.types import MemoryDecisionType
    assert MemoryDecisionType.ADD.value == "ADD"
    assert MemoryDecisionType.SUPERSEDE.value == "SUPERSEDE"
    assert MemoryDecisionType.MERGE.value == "MERGE"
    assert MemoryDecisionType.EXPIRE.value == "EXPIRE"
    assert MemoryDecisionType.DISCARD.value == "DISCARD"
```

- [ ] **Step 2：运行测试确认失败**

```bash
pytest tests/unit/memory/test_types.py::test_memory_decision_type_values_are_uppercase -v
```
期望：FAIL（当前值是小写）

- [ ] **Step 3：改枚举值**

`sebastian/memory/types.py:41-46`：

```python
class MemoryDecisionType(StrEnum):
    ADD = "ADD"
    SUPERSEDE = "SUPERSEDE"
    MERGE = "MERGE"
    EXPIRE = "EXPIRE"
    DISCARD = "DISCARD"
```

- [ ] **Step 4：移除 decision_log 里的 `.value.upper()`**

`sebastian/memory/decision_log.py` 里原本：
```python
decision=decision.decision.value.upper(),
```
改为：
```python
decision=decision.decision.value,
```

- [ ] **Step 5：跑单测与一致性测试**

```bash
pytest tests/unit/memory/test_types.py tests/unit/memory/test_decision_log.py -v
```
期望：PASS。如果有引用旧小写字符串的测试（如 `assert record.decision == "add"`）同步改大写。

- [ ] **Step 6：commit**

```bash
git add sebastian/memory/types.py sebastian/memory/decision_log.py tests/unit/memory/test_types.py tests/unit/memory/test_decision_log.py
git commit -m "fix(memory): 统一 MemoryDecisionType 枚举值为大写"
```

---

### Task A2：Pydantic 契约加严（`extra="forbid"` + `MemorySummary.scope` 枚举 + `ResolveDecision` model_validator）

**Files:**
- Modify: `sebastian/memory/types.py`
- Modify: `sebastian/memory/consolidation.py:43-47`（MemorySummary）
- Test: `tests/unit/memory/test_types.py`

- [ ] **Step 1：写失败测试**

追加到 `tests/unit/memory/test_types.py`：

```python
def test_candidate_artifact_rejects_unknown_field():
    import pytest
    from pydantic import ValidationError
    from sebastian.memory.types import CandidateArtifact, MemoryKind, MemoryScope, MemorySource

    with pytest.raises(ValidationError):
        CandidateArtifact(
            kind=MemoryKind.FACT, content="x", structured_payload={}, subject_hint=None,
            scope=MemoryScope.USER, slot_id=None, cardinality=None, resolution_policy=None,
            confidence=0.5, source=MemorySource.EXPLICIT, evidence=[],
            valid_from=None, valid_until=None, policy_tags=[], needs_review=False,
            bogus_field="nope",
        )


def test_resolve_decision_add_requires_new_memory():
    import pytest
    from pydantic import ValidationError
    from sebastian.memory.types import (
        CandidateArtifact, MemoryDecisionType, MemoryKind, MemoryScope, MemorySource, ResolveDecision,
    )
    candidate = CandidateArtifact(
        kind=MemoryKind.FACT, content="x", structured_payload={}, subject_hint=None,
        scope=MemoryScope.USER, slot_id=None, cardinality=None, resolution_policy=None,
        confidence=0.5, source=MemorySource.EXPLICIT, evidence=[],
        valid_from=None, valid_until=None, policy_tags=[], needs_review=False,
    )
    with pytest.raises(ValidationError):
        ResolveDecision(
            decision=MemoryDecisionType.ADD, reason="r", old_memory_ids=[],
            new_memory=None, candidate=candidate, subject_id="owner",
            scope=MemoryScope.USER, slot_id=None,
        )
```

在 `tests/unit/memory/test_consolidation.py` 里加：

```python
def test_memory_summary_rejects_invalid_scope():
    import pytest
    from pydantic import ValidationError
    from sebastian.memory.consolidation import MemorySummary

    with pytest.raises(ValidationError):
        MemorySummary(content="x", subject_id="owner", scope="User", session_id=None)
```

- [ ] **Step 2：运行验证失败**

```bash
pytest tests/unit/memory/test_types.py::test_candidate_artifact_rejects_unknown_field tests/unit/memory/test_types.py::test_resolve_decision_add_requires_new_memory tests/unit/memory/test_consolidation.py::test_memory_summary_rejects_invalid_scope -v
```

- [ ] **Step 3：在 `types.py` 顶部加 ConfigDict import 并给两个 Artifact 加严 + 加 model_validator**

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

给 `CandidateArtifact` 和 `MemoryArtifact` 都加：
```python
    model_config = ConfigDict(extra="forbid")
```

给 `ResolveDecision` 底部加：
```python
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_decision_shape(self) -> "ResolveDecision":
        if self.decision in (MemoryDecisionType.ADD, MemoryDecisionType.SUPERSEDE, MemoryDecisionType.MERGE):
            if self.new_memory is None:
                raise ValueError(f"{self.decision} must include new_memory")
        if self.decision == MemoryDecisionType.ADD and self.old_memory_ids:
            raise ValueError("ADD must not have old_memory_ids")
        if self.decision in (MemoryDecisionType.SUPERSEDE, MemoryDecisionType.MERGE):
            if not self.old_memory_ids:
                raise ValueError(f"{self.decision} must include old_memory_ids")
        if self.decision == MemoryDecisionType.DISCARD and self.new_memory is not None:
            raise ValueError("DISCARD must not have new_memory")
        return self
```

- [ ] **Step 4：把 `MemorySummary.scope` 改成 enum**

`sebastian/memory/consolidation.py:43-47`：

```python
class MemorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    subject_id: str
    scope: MemoryScope = MemoryScope.USER
    session_id: str | None = None
```

同文件顶部补 `from pydantic import ConfigDict` 与 `from sebastian.memory.types import MemoryScope`（已有则不动）。

- [ ] **Step 5：`_summary_to_artifact` 不再 `MemoryScope(summary.scope)`**

`sebastian/memory/consolidation.py:251` 改为：
```python
scope=summary.scope,
```

- [ ] **Step 6：跑全部 memory 单测**

```bash
pytest tests/unit/memory -v
```
期望：PASS。若旧测试构造 artifact 时带了不存在字段，去掉多余字段。

- [ ] **Step 7：commit**

```bash
git add sebastian/memory/types.py sebastian/memory/consolidation.py tests/unit/memory/test_types.py tests/unit/memory/test_consolidation.py
git commit -m "fix(memory): Pydantic 契约禁额外字段且锁定 MemorySummary.scope 枚举"
```

---

### Task A3：新增 `MemoryError` 族，替换裸 `KeyError` / `RuntimeError`

**Files:**
- Create: `sebastian/memory/errors.py`
- Modify: `sebastian/memory/slots.py:101`（`require` 抛自定义异常）
- Test: `tests/unit/memory/test_errors.py`

- [ ] **Step 1：写失败测试**

`tests/unit/memory/test_errors.py`：

```python
from __future__ import annotations
import pytest
from sebastian.memory.errors import UnknownSlotError, InvalidCandidateError, MemoryError
from sebastian.memory.slots import DEFAULT_SLOT_REGISTRY


def test_unknown_slot_is_subclass_of_memory_error():
    assert issubclass(UnknownSlotError, MemoryError)
    assert issubclass(InvalidCandidateError, MemoryError)


def test_require_unknown_slot_raises_unknown_slot_error():
    with pytest.raises(UnknownSlotError):
        DEFAULT_SLOT_REGISTRY.require("no.such.slot")
```

- [ ] **Step 2：运行验证失败**

```bash
pytest tests/unit/memory/test_errors.py -v
```

- [ ] **Step 3：创建 errors 模块**

`sebastian/memory/errors.py`：

```python
from __future__ import annotations

from sebastian.core.errors import SebastianError


class MemoryError(SebastianError):
    """Base class for all memory subsystem errors."""


class UnknownSlotError(MemoryError):
    """Raised when a slot_id is referenced but not registered."""


class InvalidCandidateError(MemoryError):
    """Raised when a CandidateArtifact fails normalization/validation."""


class DecisionLogPersistenceError(MemoryError):
    """Raised when decision_log append fails at persistence layer."""
```

> 若 `sebastian.core.errors.SebastianError` 尚不存在，先搜索 `grep -r "class SebastianError" sebastian/`；若确实不存在则暂以 `class MemoryError(Exception):` 实现，并把后续 core errors 模块的创建拆为独立任务。

- [ ] **Step 4：改 `SlotRegistry.require`**

`sebastian/memory/slots.py:101` 附近：

```python
def require(self, slot_id: str) -> SlotDefinition:
    definition = self.get(slot_id)
    if definition is None:
        from sebastian.memory.errors import UnknownSlotError
        raise UnknownSlotError(f"slot_id '{slot_id}' not registered")
    return definition
```

（若原来 `raise KeyError(...)` 有测试断言 KeyError，改测试为 UnknownSlotError；或者同时捕获：优先只捕获 UnknownSlotError。）

- [ ] **Step 5：跑测试**

```bash
pytest tests/unit/memory/test_errors.py tests/unit/memory/test_slots.py -v
```

- [ ] **Step 6：commit**

```bash
git add sebastian/memory/errors.py sebastian/memory/slots.py tests/unit/memory/test_errors.py tests/unit/memory/test_slots.py
git commit -m "refactor(memory): 新增 MemoryError 体系并替换 SlotRegistry 裸异常"
```

---

### Task A4：修复假阳性测试 `test_does_not_write_to_db`

**Files:**
- Modify: `tests/unit/memory/test_consolidation.py:377-402`

- [ ] **Step 1：理解原测试**

原测试用 `db_write_called = False`，但没有任何代码会把它设 True，`assert not db_write_called` 永远通过。

- [ ] **Step 2：改为真正检测**

把测试改写为：在 `memory_settings_fn` 返回 False 的前提下运行 Worker，断言 DB 里 `ProfileMemoryRecord / EpisodeMemoryRecord / SessionConsolidationRecord` 行数均为 0：

```python
@pytest.mark.asyncio
async def test_worker_writes_nothing_when_memory_disabled(
    tmp_engine, session_with_messages
):
    from sqlalchemy import select
    from sebastian.store.models import (
        ProfileMemoryRecord, EpisodeMemoryRecord, SessionConsolidationRecord,
    )
    # ... construct worker with memory_settings_fn=lambda: False
    await worker.consolidate_session("s1", "default")

    async with factory() as s:
        profiles = (await s.scalars(select(ProfileMemoryRecord))).all()
        episodes = (await s.scalars(select(EpisodeMemoryRecord))).all()
        markers = (await s.scalars(select(SessionConsolidationRecord))).all()
        assert profiles == []
        assert episodes == []
        assert markers == []
```

具体 fixture 名字与测试文件已有 `tmp_engine / session_with_messages` 类似 helper 对齐（如果没有就抄 `test_memory_consolidation.py` 里的构造法）。

- [ ] **Step 3：跑测试确认新测试在 memory_disabled 情况下通过；把 Worker 改成忽略 flag 再重跑可见 FAIL（反证可用）**

```bash
pytest tests/unit/memory/test_consolidation.py -v
```

- [ ] **Step 4：commit**

```bash
git add tests/unit/memory/test_consolidation.py
git commit -m "test(memory): 修复假阳性的沉淀禁用测试，改为真正断言 DB 为空"
```

---

## Phase R-B：P0 bug 直接修复

### Task B1：`ProfileMemoryStore.search_active` 加 `valid_until` 过滤 + scope 用 `MemoryScope`

**Files:**
- Modify: `sebastian/memory/profile_store.py:65-81`
- Test: `tests/unit/memory/test_profile_store.py`

- [ ] **Step 1：写失败测试**

在 `tests/unit/memory/test_profile_store.py` 追加：

```python
@pytest.mark.asyncio
async def test_search_active_filters_expired_records(profile_store, session):
    from datetime import UTC, datetime, timedelta
    from sebastian.memory.types import (
        Cardinality, MemoryArtifact, MemoryKind, MemoryScope, MemorySource, MemoryStatus,
        ResolutionPolicy,
    )
    now = datetime.now(UTC)
    expired = MemoryArtifact(
        id="m-expired", kind=MemoryKind.FACT, scope=MemoryScope.USER, subject_id="owner",
        slot_id="user.profile.name", cardinality=Cardinality.SINGLE,
        resolution_policy=ResolutionPolicy.SUPERSEDE, content="old", structured_payload={},
        source=MemorySource.EXPLICIT, confidence=1.0, status=MemoryStatus.ACTIVE,
        valid_from=None, valid_until=now - timedelta(days=1),
        recorded_at=now, last_accessed_at=None, access_count=0,
        provenance={}, links=[], embedding_ref=None, dedupe_key=None, policy_tags=[],
    )
    active = expired.model_copy(update={
        "id": "m-active", "content": "fresh", "valid_until": None,
    })
    await profile_store.add(expired)
    await profile_store.add(active)
    await session.commit()

    rows = await profile_store.search_active(subject_id="owner")
    ids = {r.id for r in rows}
    assert ids == {"m-active"}
```

- [ ] **Step 2：运行测试确认失败**

```bash
pytest tests/unit/memory/test_profile_store.py::test_search_active_filters_expired_records -v
```
期望：FAIL。

- [ ] **Step 3：修 `search_active`**

`sebastian/memory/profile_store.py:65-81`：

```python
async def search_active(
    self,
    *,
    subject_id: str,
    scope: str | None = None,
    limit: int = 8,
) -> list[ProfileMemoryRecord]:
    now = datetime.now(UTC)
    statement = select(ProfileMemoryRecord).where(
        ProfileMemoryRecord.subject_id == subject_id,
        ProfileMemoryRecord.status == MemoryStatus.ACTIVE.value,
        or_(
            ProfileMemoryRecord.valid_until.is_(None),
            ProfileMemoryRecord.valid_until > now,
        ),
    )
    if scope is not None:
        statement = statement.where(ProfileMemoryRecord.scope == scope)
    statement = statement.order_by(ProfileMemoryRecord.created_at.desc()).limit(limit)

    result = await self._session.scalars(statement)
    return list(result.all())
```

- [ ] **Step 4：跑测试通过**

```bash
pytest tests/unit/memory/test_profile_store.py -v
```

- [ ] **Step 5：commit**

```bash
git add sebastian/memory/profile_store.py tests/unit/memory/test_profile_store.py
git commit -m "fix(memory): search_active 过滤过期记录避免把失效事实注入 prompt"
```

---

### Task B2：`memory_save` DISCARD 分支写 decision log

**Files:**
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py:82-83`
- Test: `tests/unit/capabilities/test_memory_tools.py`

- [ ] **Step 1：写失败测试**

追加到 `tests/unit/capabilities/test_memory_tools.py`（需要一个 fixture 能构造 CandidateArtifact 触发 DISCARD——`memory_save` 目前 confidence 固定 1.0 所以无法触发。我们换思路：先把 `memory_save` 的 DISCARD 分支改成也写 log，然后用 monkeypatch `resolve_candidate` 让它返回 DISCARD 来验证 log 被写）：

```python
@pytest.mark.asyncio
async def test_memory_save_discard_writes_decision_log(
    enabled_memory_state, monkeypatch
):
    from sqlalchemy import select
    from sebastian.store.models import MemoryDecisionLogRecord
    from sebastian.memory.types import MemoryDecisionType, ResolveDecision
    from sebastian.capabilities.tools.memory_save import memory_save

    async def fake_resolve(candidate, *, subject_id, profile_store, slot_registry):
        return ResolveDecision(
            decision=MemoryDecisionType.DISCARD, reason="test",
            old_memory_ids=[], new_memory=None, candidate=candidate,
            subject_id=subject_id, scope=candidate.scope, slot_id=candidate.slot_id,
        )
    monkeypatch.setattr(
        "sebastian.capabilities.tools.memory_save.resolve_candidate", fake_resolve,
        raising=False,
    )

    result = await memory_save(content="x")
    assert result.ok is False

    async with enabled_memory_state.db_factory() as s:
        rows = (await s.scalars(select(MemoryDecisionLogRecord))).all()
        assert len(rows) == 1
        assert rows[0].decision == MemoryDecisionType.DISCARD.value
```

> 由于原文件是用 `from sebastian.memory.resolver import resolve_candidate` 局部 import，monkeypatch 需要先让 import 生效（可在测试前 `import sebastian.capabilities.tools.memory_save` 一次），或者把 import 移到模块顶部。

- [ ] **Step 2：运行测试确认失败**

```bash
pytest tests/unit/capabilities/test_memory_tools.py::test_memory_save_discard_writes_decision_log -v
```

- [ ] **Step 3：修 `memory_save`：DISCARD 也写 log 再 return**

`sebastian/capabilities/tools/memory_save/__init__.py:82-83` 改为：

```python
        if decision.decision == MemoryDecisionType.DISCARD:
            await decision_logger.append(
                decision, worker="memory_save_tool",
                model=None, rule_version="phase_b_v1",
            )
            await session.commit()
            return ToolResult(ok=False, error="记忆被丢弃：置信度不足或槽位不匹配")
```

（等价：把 `await decision_logger.append(...)` 和 `await session.commit()` 挪到同一入口前。）

- [ ] **Step 4：跑测试**

```bash
pytest tests/unit/capabilities/test_memory_tools.py -v
```

- [ ] **Step 5：commit**

```bash
git add sebastian/capabilities/tools/memory_save/__init__.py tests/unit/capabilities/test_memory_tools.py
git commit -m "fix(memory): memory_save DISCARD 分支补写决策日志"
```

---

### Task B3：Consolidation summaries 经 resolver 写 decision log

**Files:**
- Modify: `sebastian/memory/consolidation.py:204-206`
- Test: `tests/integration/test_memory_consolidation.py`

- [ ] **Step 1：写失败测试**

在 `tests/integration/test_memory_consolidation.py` 追加：

```python
@pytest.mark.asyncio
async def test_consolidate_logs_summary_decision(...):
    from sqlalchemy import select
    from sebastian.store.models import MemoryDecisionLogRecord
    # 用已有 FakeConsolidator 预置一条 summary，跑 worker，
    # 断言 memory_decision_log 里有一条 decision=ADD 且 candidate.kind="summary"
    ...
    async with factory() as s:
        logs = (await s.scalars(select(MemoryDecisionLogRecord))).all()
        assert any(l.candidate_payload.get("kind") == "summary" for l in logs)
        assert all(l.decision == "ADD" for l in logs)
```

- [ ] **Step 2：运行验证失败**

```bash
pytest tests/integration/test_memory_consolidation.py::test_consolidate_logs_summary_decision -v
```

- [ ] **Step 3：改 `SessionConsolidationWorker.consolidate_session`**

在 `sebastian/memory/consolidation.py:204-206` 把 summary 写入路径改为：构造 `CandidateArtifact`（kind=SUMMARY）→ `resolve_candidate`（因 kind=SUMMARY 会走 ADD 分支）→ `episode_store.add_summary(decision.new_memory)` → `decision_logger.append(decision, ...)`。

核心片段：

```python
for summary in result.summaries:
    candidate = CandidateArtifact(
        kind=MemoryKind.SUMMARY,
        content=summary.content,
        structured_payload={},
        subject_hint=summary.subject_id,
        scope=summary.scope,
        slot_id=None, cardinality=None, resolution_policy=None,
        confidence=0.8, source=MemorySource.SYSTEM_DERIVED,
        evidence=[{"session_id": session_id}],
        valid_from=None, valid_until=None,
        policy_tags=[], needs_review=False,
    )
    decision = await resolve_candidate(
        candidate, subject_id=summary.subject_id,
        profile_store=profile_store, slot_registry=DEFAULT_SLOT_REGISTRY,
    )
    if decision.new_memory is not None:
        await episode_store.add_summary(decision.new_memory)
    await decision_logger.append(
        decision, worker=self._WORKER_ID, model=None,
        rule_version=self._RULE_VERSION,
    )
```

删掉原先的 `_summary_to_artifact` helper 或保留为未导出的内部纯转换（不再被调用也可以删）。

- [ ] **Step 4：跑测试**

```bash
pytest tests/integration/test_memory_consolidation.py tests/unit/memory/test_consolidation.py -v
```

- [ ] **Step 5：commit**

```bash
git add sebastian/memory/consolidation.py tests/integration/test_memory_consolidation.py
git commit -m "fix(memory): 沉淀 summary 走 resolver 并写决策日志"
```

---

### Task B4：Resolver 引入 source/confidence 优先级

**Files:**
- Modify: `sebastian/memory/resolver.py`
- Test: `tests/unit/memory/test_resolver.py`

**设计准则**（参考 `artifact-model.md §9`）：
- `EXPLICIT > IMPORTED > OBSERVED > INFERRED > SYSTEM_DERIVED`
- 当 SINGLE cardinality 命中 existing 时：
  - 若 `new.source` 严格弱于 `existing.source` 且 `new.confidence < existing.confidence + 0.1` → DISCARD（同槽保留高权威）
  - 否则 SUPERSEDE
- `needs_review=True` 也走 DISCARD 路径（由 Phase D 人审）。

- [ ] **Step 1：写失败测试**

```python
@pytest.mark.asyncio
async def test_resolver_discards_low_priority_overwrite():
    # existing EXPLICIT + confidence=0.95；new INFERRED + confidence=0.6
    # 期望 decision=DISCARD，old_memory_ids=[]（不覆盖）
    ...

@pytest.mark.asyncio
async def test_resolver_supersedes_when_new_has_higher_source_or_confidence():
    # existing INFERRED + 0.5；new EXPLICIT + 0.9 → SUPERSEDE
    ...
```

- [ ] **Step 2：在 `resolver.py` 加 `_SOURCE_PRIORITY` 常量与判定函数**

```python
_SOURCE_PRIORITY: dict[MemorySource, int] = {
    MemorySource.EXPLICIT: 5,
    MemorySource.IMPORTED: 4,
    MemorySource.OBSERVED: 3,
    MemorySource.INFERRED: 2,
    MemorySource.SYSTEM_DERIVED: 1,
}


def _new_is_weaker(
    new: CandidateArtifact,
    existing: ProfileMemoryRecord,
) -> bool:
    existing_source = MemorySource(existing.source)
    new_rank = _SOURCE_PRIORITY[new.source]
    old_rank = _SOURCE_PRIORITY[existing_source]
    if new_rank < old_rank and new.confidence < existing.confidence + 0.1:
        return True
    return False
```

然后在 SINGLE 分支命中 existing 时：

```python
weakest = all(_new_is_weaker(candidate, r) for r in existing)
if weakest:
    return ResolveDecision(
        decision=MemoryDecisionType.DISCARD,
        reason="new candidate has weaker source/confidence than all existing records",
        old_memory_ids=[], new_memory=None,
        candidate=candidate, subject_id=subject_id,
        scope=candidate.scope, slot_id=candidate.slot_id,
    )
```

- [ ] **Step 3：跑测试**

```bash
pytest tests/unit/memory/test_resolver.py -v
```

- [ ] **Step 4：commit**

```bash
git add sebastian/memory/resolver.py tests/unit/memory/test_resolver.py
git commit -m "fix(memory): resolver 按 source/confidence 优先级决策 SUPERSEDE 或 DISCARD"
```

---

### Task B5：`memory_save` / 写入路径统一调用 `validate_candidate`

**Files:**
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py`（在 resolve 之前 validate）
- Modify: `sebastian/memory/consolidation.py`（proposed_artifacts 也 validate）
- Test: `tests/unit/memory/test_slots.py`、`tests/unit/capabilities/test_memory_tools.py`

- [ ] **Step 1：写失败测试**

`memory_save` 传入 `slot_id="no.such.slot"` + `kind=FACT`：应该返回 `ok=False, error` 且不写任何 profile 行，不抛 UnknownSlotError 到外层（捕获后降级为错误返回）。

```python
@pytest.mark.asyncio
async def test_memory_save_rejects_unknown_slot(enabled_memory_state):
    from sebastian.capabilities.tools.memory_save import memory_save
    result = await memory_save(content="x", slot_id="no.such.slot")
    assert result.ok is False
    assert "slot" in (result.error or "").lower()
```

- [ ] **Step 2：在 `memory_save` 构造 candidate 后加 validate**

```python
    try:
        DEFAULT_SLOT_REGISTRY.validate_candidate(candidate)
    except InvalidCandidateError as e:
        return ToolResult(ok=False, error=f"记忆参数校验失败：{e}")
```

> 若当前 `validate_candidate` 抛 `KeyError` / `ValueError`，先把它改成 `raise InvalidCandidateError(...)`（属于 Task A3 的延伸）。

- [ ] **Step 3：Consolidator 里同样 validate**

`SessionConsolidationWorker.consolidate_session` 在 `for candidate in result.proposed_artifacts:` 循环内第一步：

```python
try:
    DEFAULT_SLOT_REGISTRY.validate_candidate(candidate)
except InvalidCandidateError as e:
    await decision_logger.append(
        ResolveDecision(
            decision=MemoryDecisionType.DISCARD, reason=f"validate: {e}",
            old_memory_ids=[], new_memory=None, candidate=candidate,
            subject_id="owner", scope=candidate.scope, slot_id=candidate.slot_id,
        ),
        worker=self._WORKER_ID, model=None, rule_version=self._RULE_VERSION,
    )
    continue
```

- [ ] **Step 4：跑测试**

```bash
pytest tests/unit/capabilities/test_memory_tools.py tests/unit/memory/test_slots.py tests/integration/test_memory_consolidation.py -v
```

- [ ] **Step 5：commit**

```bash
git add sebastian/capabilities/tools/memory_save/__init__.py sebastian/memory/consolidation.py sebastian/memory/slots.py tests/unit/capabilities/test_memory_tools.py tests/unit/memory/test_slots.py
git commit -m "fix(memory): 写入前统一 validate_candidate 拒绝非法 slot"
```

---

## Phase R-C：写入分发 & Subject Resolver

### Task C1：新增 `subject resolver` 模块

**Files:**
- Create: `sebastian/memory/subject.py`
- Test: `tests/unit/memory/test_subject.py`

目标：抽掉写死的 `"owner"` 字符串，Phase B 行为不变（永远返回 `"owner"`），但为 Phase 5 多用户预留唯一注入点。

- [ ] **Step 1：写测试**

```python
from __future__ import annotations
import pytest
from sebastian.memory.subject import resolve_subject
from sebastian.memory.types import MemoryScope


@pytest.mark.asyncio
async def test_resolve_subject_owner_scope_defaults_to_owner():
    assert await resolve_subject(MemoryScope.USER, session_id="s1", agent_type="default") == "owner"


@pytest.mark.asyncio
async def test_resolve_subject_agent_scope_uses_agent_type():
    assert await resolve_subject(MemoryScope.AGENT, session_id="s1", agent_type="calendar") == "agent:calendar"


@pytest.mark.asyncio
async def test_resolve_subject_session_scope_uses_session_id():
    assert await resolve_subject(MemoryScope.SESSION, session_id="s1", agent_type="default") == "session:s1"
```

- [ ] **Step 2：实现**

```python
from __future__ import annotations

from sebastian.memory.types import MemoryScope

OWNER_SUBJECT = "owner"


async def resolve_subject(
    scope: MemoryScope,
    *,
    session_id: str,
    agent_type: str,
) -> str:
    """Resolve the subject_id for a given memory scope.

    Phase B: only owner exists for USER/PROJECT scopes.
    """
    if scope == MemoryScope.AGENT:
        return f"agent:{agent_type}"
    if scope == MemoryScope.SESSION:
        return f"session:{session_id}"
    return OWNER_SUBJECT
```

- [ ] **Step 3：跑测试**

```bash
pytest tests/unit/memory/test_subject.py -v
```

- [ ] **Step 4：commit**

```bash
git add sebastian/memory/subject.py tests/unit/memory/test_subject.py
git commit -m "feat(memory): 新增 subject resolver 替代硬编码 owner"
```

---

### Task C2：所有 memory 入口调用 `resolve_subject`

**Files:**
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py:46`
- Modify: `sebastian/capabilities/tools/memory_search/__init__.py:28`
- Modify: `sebastian/core/base_agent.py:256`
- Modify: `sebastian/memory/consolidation.py:211`
- Test: 现有测试应全部通过；补一个断言 BaseAgent 传入了正确 subject。

- [ ] **Step 1：在 memory_save 替换硬编码**

```python
from sebastian.memory.subject import resolve_subject
subject_id = await resolve_subject(
    MemoryScope(scope),
    session_id=state.current_session_id or "",
    agent_type=state.current_agent_type or "default",
)
```

> 若 `state` 中目前没有 `current_session_id/current_agent_type`，Phase B 可降级为 `session_id=""`、`agent_type="default"`——函数返回仍是 `"owner"`。真正的 session/agent 上下文由 Phase 5 注入。

- [ ] **Step 2：在 memory_search 做同样替换**

- [ ] **Step 3：BaseAgent `_memory_section` 也用 `resolve_subject`**

原本：
```python
context = RetrievalContext(
    subject_id="owner", session_id=..., agent_type=..., user_message=...,
)
```
改为：
```python
subject_id = await resolve_subject(MemoryScope.USER, session_id=session_id, agent_type=agent_type)
context = RetrievalContext(subject_id=subject_id, ...)
```

- [ ] **Step 4：Consolidator 用 session_id + agent_type 解析**

`consolidate_session(session_id, agent_type)` 已有入参，替换循环里的 `subject_id="owner"`：

```python
subject_id = await resolve_subject(
    candidate.scope, session_id=session_id, agent_type=agent_type,
)
decision = await resolve_candidate(candidate, subject_id=subject_id, ...)
```

- [ ] **Step 5：跑全量 memory 测试**

```bash
pytest tests/unit/memory tests/integration/test_memory_consolidation.py tests/unit/capabilities/test_memory_tools.py tests/unit/core/test_base_agent_memory.py -v
```

- [ ] **Step 6：commit**

```bash
git add sebastian/capabilities/tools/memory_save/__init__.py sebastian/capabilities/tools/memory_search/__init__.py sebastian/core/base_agent.py sebastian/memory/consolidation.py
git commit -m "refactor(memory): 接入 subject resolver 替换硬编码 owner"
```

---

### Task C3：新增 `write_router`，按 kind 分发到正确 store

**Files:**
- Create: `sebastian/memory/write_router.py`
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py`
- Modify: `sebastian/memory/consolidation.py`
- Test: `tests/unit/memory/test_write_router.py`

目标：消除 `memory_save` 里 `if kind in (episode, summary)` 的硬编码，把 entity/relation 也引到正确物理层（`EntityRegistry` / `relation_candidates` 表）。

- [ ] **Step 1：写测试**

```python
from __future__ import annotations
import pytest
from sebastian.memory.write_router import persist_decision
from sebastian.memory.types import (
    MemoryArtifact, MemoryDecisionType, MemoryKind, MemoryScope, MemorySource, MemoryStatus, ResolveDecision,
)
# ... 用真 SQLite in-memory engine，验证：
#   - kind=FACT + ADD → ProfileMemoryRecord 1 行
#   - kind=FACT + SUPERSEDE → 旧行 status=SUPERSEDED 且新行 ACTIVE
#   - kind=EPISODE + ADD → EpisodeMemoryRecord 1 行
#   - kind=SUMMARY + ADD → EpisodeMemoryRecord 1 行（kind=summary）
#   - kind=ENTITY + ADD → EntityRecord 1 行，aliases 合并
#   - kind=RELATION + ADD → RelationCandidateRecord 1 行
#   - DISCARD → 零写入
```

- [ ] **Step 2：实现 `write_router.py`**

```python
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sebastian.memory.types import MemoryDecisionType, MemoryKind, ResolveDecision

if TYPE_CHECKING:
    from sebastian.memory.entity_registry import EntityRegistry
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sqlalchemy.ext.asyncio import AsyncSession


async def persist_decision(
    decision: ResolveDecision,
    *,
    session: AsyncSession,
    profile_store: ProfileMemoryStore,
    episode_store: EpisodeMemoryStore,
    entity_registry: EntityRegistry,
) -> None:
    """Route a ResolveDecision to the correct store based on memory kind."""
    if decision.decision == MemoryDecisionType.DISCARD:
        return
    if decision.new_memory is None:
        raise ValueError("non-DISCARD decision must have new_memory")

    artifact = decision.new_memory
    kind = artifact.kind

    if kind == MemoryKind.EPISODE:
        await episode_store.add_episode(artifact)
        return
    if kind == MemoryKind.SUMMARY:
        await episode_store.add_summary(artifact)
        return
    if kind == MemoryKind.ENTITY:
        payload = artifact.structured_payload or {}
        await entity_registry.upsert_entity(
            canonical_name=payload.get("canonical_name", artifact.content),
            entity_type=payload.get("entity_type", "unknown"),
            aliases=payload.get("aliases", []),
            metadata=payload.get("metadata", {}),
        )
        return
    if kind == MemoryKind.RELATION:
        from sebastian.store.models import RelationCandidateRecord
        payload = artifact.structured_payload or {}
        session.add(
            RelationCandidateRecord(
                id=artifact.id or str(uuid4()),
                subject_id=artifact.subject_id,
                predicate=payload.get("predicate", ""),
                object_ref=payload.get("object_ref", ""),
                content=artifact.content,
                confidence=artifact.confidence,
                status=artifact.status.value,
                valid_from=artifact.valid_from,
                valid_until=artifact.valid_until,
                provenance=artifact.provenance,
                created_at=artifact.recorded_at,
                updated_at=artifact.recorded_at,
            )
        )
        await session.flush()
        return

    # FACT / PREFERENCE
    if decision.decision == MemoryDecisionType.SUPERSEDE:
        await profile_store.supersede(decision.old_memory_ids, artifact)
    else:
        await profile_store.add(artifact)
```

- [ ] **Step 3：把 `memory_save` 的 store 分支改成 `persist_decision`**

原 88-95 行整块替换为：

```python
from sebastian.memory.write_router import persist_decision
from sebastian.memory.entity_registry import EntityRegistry

entity_registry = EntityRegistry(session)
await persist_decision(
    decision,
    session=session,
    profile_store=profile_store,
    episode_store=episode_store,
    entity_registry=entity_registry,
)
```

- [ ] **Step 4：Consolidator 循环里同样替换**

`consolidation.py` 里 `for candidate in result.proposed_artifacts` 循环：

```python
await persist_decision(
    decision, session=session,
    profile_store=profile_store, episode_store=episode_store,
    entity_registry=entity_registry,
)
```

（summaries 循环也收敛到 write_router，同 Task B3 的 CandidateArtifact 构造。）

- [ ] **Step 5：跑测试**

```bash
pytest tests/unit/memory/test_write_router.py tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py -v
```

- [ ] **Step 6：commit**

```bash
git add sebastian/memory/write_router.py sebastian/capabilities/tools/memory_save/__init__.py sebastian/memory/consolidation.py tests/unit/memory/test_write_router.py
git commit -m "feat(memory): 新增 write_router 按 kind 分发到 Profile/Episode/Entity/Relation 存储"
```

---

### Task C4：Resolver 的 `_make_artifact` provenance 注入 session_id

**Files:**
- Modify: `sebastian/memory/resolver.py:162-188`
- Test: `tests/unit/memory/test_resolver.py`

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_resolver_provenance_includes_session_id():
    # candidate.evidence=[{"session_id": "s-xyz"}]
    # decision.new_memory.provenance 应包含 "session_id": "s-xyz"
    ...
```

- [ ] **Step 2：改 `_make_artifact`**

```python
def _make_artifact(candidate: CandidateArtifact, subject_id: str) -> MemoryArtifact:
    now = datetime.now(UTC)
    session_id: str | None = None
    for ev in candidate.evidence:
        if isinstance(ev, dict) and "session_id" in ev:
            session_id = ev["session_id"]
            break
    provenance = {"evidence": candidate.evidence}
    if session_id is not None:
        provenance["session_id"] = session_id
    return MemoryArtifact(
        ...
        provenance=provenance,
        ...
    )
```

- [ ] **Step 3：跑测试**

```bash
pytest tests/unit/memory/test_resolver.py -v
```

- [ ] **Step 4：commit**

```bash
git add sebastian/memory/resolver.py tests/unit/memory/test_resolver.py
git commit -m "fix(memory): provenance 注入 session_id 便于回溯"
```

---

## Phase R-D：Retrieval 四通道扩展

### Task D1：`RetrievalPlan` 扩展为 4 lane 的独立 budget

**Files:**
- Modify: `sebastian/memory/retrieval.py`
- Test: `tests/unit/memory/test_retrieval.py`

- [ ] **Step 1：写失败测试**

追加到 `tests/unit/memory/test_retrieval.py`：

```python
def test_retrieval_plan_has_four_lanes():
    from sebastian.memory.retrieval import RetrievalPlan
    plan = RetrievalPlan()
    assert plan.profile_lane is True
    assert hasattr(plan, "context_lane")
    assert hasattr(plan, "episode_lane")
    assert hasattr(plan, "relation_lane")
    assert plan.profile_limit + plan.context_limit + plan.episode_limit + plan.relation_limit > 0


def test_planner_skips_profile_for_small_talk():
    from sebastian.memory.retrieval import MemoryRetrievalPlanner, RetrievalContext
    plan = MemoryRetrievalPlanner().plan(RetrievalContext(
        subject_id="owner", session_id="s", agent_type="default",
        user_message="hi",
    ))
    # small-talk → 关闭 profile_lane（成本意识）
    assert plan.profile_lane is False
    assert plan.episode_lane is False
```

- [ ] **Step 2：运行验证失败**

```bash
pytest tests/unit/memory/test_retrieval.py -v
```

- [ ] **Step 3：扩展 `RetrievalPlan` 和 `MemoryRetrievalPlanner`**

`sebastian/memory/retrieval.py`：

```python
PROFILE_LANE_KEYWORDS = ["我", "我的", "我喜欢", "我是", "my", "i am", "i like", "i prefer"]
EPISODE_LANE_KEYWORDS = ["上次", "讨论", "之前", "记得", "last time", "remember", "we discussed"]
RELATION_LANE_KEYWORDS = ["老婆", "孩子", "同事", "项目", "team", "project", "related to"]
CONTEXT_LANE_KEYWORDS = ["现在", "今天", "本周", "正在", "now", "today", "this week", "current"]
SMALL_TALK_PATTERNS = ["hi", "hello", "你好", "嗨", "ok", "谢谢", "thanks"]


class RetrievalPlan(BaseModel):
    profile_lane: bool = True
    context_lane: bool = False
    episode_lane: bool = False
    relation_lane: bool = False
    profile_limit: int = 5
    context_limit: int = 3
    episode_limit: int = 3
    relation_limit: int = 3


class MemoryRetrievalPlanner:
    def plan(self, context: RetrievalContext) -> RetrievalPlan:
        msg = context.user_message.lower().strip()
        if any(msg == p or msg.startswith(p + " ") for p in SMALL_TALK_PATTERNS):
            return RetrievalPlan(
                profile_lane=False, context_lane=False,
                episode_lane=False, relation_lane=False,
            )
        return RetrievalPlan(
            profile_lane=any(k in msg for k in PROFILE_LANE_KEYWORDS) or True,
            context_lane=any(k in msg for k in CONTEXT_LANE_KEYWORDS),
            episode_lane=any(k in msg for k in EPISODE_LANE_KEYWORDS),
            relation_lane=any(k in msg for k in RELATION_LANE_KEYWORDS),
        )
```

> Profile Lane 对非 small-talk 默认开启（因为用户事实始终是个性化基底）。spec 后续可以演进为 LLM-based intent classifier，但 Phase R-D 先用关键词规则对齐 spec §2 的 5 类意图。

- [ ] **Step 4：跑测试**

```bash
pytest tests/unit/memory/test_retrieval.py -v
```

- [ ] **Step 5：commit**

```bash
git add sebastian/memory/retrieval.py tests/unit/memory/test_retrieval.py
git commit -m "feat(memory): RetrievalPlan 扩展为 Profile/Context/Episode/Relation 四通道"
```

---

### Task D2：Context Lane 实现（访问近期 active memory with time window）

**Files:**
- Modify: `sebastian/memory/profile_store.py`（新增 `search_recent_context`）
- Modify: `sebastian/memory/retrieval.py`（`retrieve_memory_section` 新增 context lane 调用）
- Test: `tests/unit/memory/test_profile_store.py`、`tests/unit/memory/test_retrieval.py`

Context Lane：返回最近 N 天内 `policy_tags` 含 `current_state` 或 `status=ACTIVE` 且 `kind=FACT`+`valid_from` 在最近窗口的记忆。与 Profile Lane 区别：Profile 是稳定偏好；Context 是"正在做什么"、"今天状态如何"这类时效性事实。

- [ ] **Step 1：新增 `search_recent_context`**

```python
from datetime import timedelta

async def search_recent_context(
    self, *, subject_id: str, window_days: int = 7, limit: int = 3,
) -> list[ProfileMemoryRecord]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    statement = (
        select(ProfileMemoryRecord)
        .where(
            ProfileMemoryRecord.subject_id == subject_id,
            ProfileMemoryRecord.status == MemoryStatus.ACTIVE.value,
            or_(
                ProfileMemoryRecord.valid_until.is_(None),
                ProfileMemoryRecord.valid_until > now,
            ),
            ProfileMemoryRecord.created_at >= cutoff,
        )
        .order_by(ProfileMemoryRecord.created_at.desc())
        .limit(limit)
    )
    result = await self._session.scalars(statement)
    return list(result.all())
```

- [ ] **Step 2：`retrieve_memory_section` 接通 Context Lane**

```python
context_records: list[Any] = []
if plan.context_lane:
    context_records = await profile_store.search_recent_context(
        subject_id=context.subject_id, limit=plan.context_limit,
    )
```

- [ ] **Step 3：测试**

```python
@pytest.mark.asyncio
async def test_search_recent_context_returns_recent_only(profile_store, session):
    # 插入 created_at 距今 1 天 / 30 天 两条 active 记忆
    # 断言默认 7 天窗口只返回 1 天那条
    ...
```

- [ ] **Step 4：commit**

```bash
git add sebastian/memory/profile_store.py sebastian/memory/retrieval.py tests/unit/memory/test_profile_store.py tests/unit/memory/test_retrieval.py
git commit -m "feat(memory): 新增 Context Lane 注入近期时效性记忆"
```

---

### Task D3：Relation Lane 实现

**Files:**
- Modify: `sebastian/memory/entity_registry.py`（新增 `list_relations`）
- Modify: `sebastian/memory/retrieval.py`（Relation Lane 调用）
- Test: `tests/unit/memory/test_entity_registry.py`、`tests/unit/memory/test_retrieval.py`

Relation Lane：从 `relation_candidates` 表拉当前 active 关系，按 subject_id 过滤，可按 `user_message` 里实体词做精确匹配（EntityRegistry.lookup）。

- [ ] **Step 1：EntityRegistry 新增 `list_relations`**

```python
async def list_relations(
    self, *, subject_id: str, limit: int = 3,
) -> list[RelationCandidateRecord]:
    from sebastian.store.models import RelationCandidateRecord
    now = datetime.now(UTC)
    statement = (
        select(RelationCandidateRecord)
        .where(
            RelationCandidateRecord.subject_id == subject_id,
            RelationCandidateRecord.status == MemoryStatus.ACTIVE.value,
            or_(
                RelationCandidateRecord.valid_until.is_(None),
                RelationCandidateRecord.valid_until > now,
            ),
        )
        .order_by(RelationCandidateRecord.created_at.desc())
        .limit(limit)
    )
    result = await self._session.scalars(statement)
    return list(result.all())
```

> 依赖 Task F3 给 `RelationCandidateRecord` 补 `status/valid_from/valid_until` 字段，如果 F3 还没做就先执行 F3。

- [ ] **Step 2：Retrieval 接通**

```python
relation_records: list[Any] = []
if plan.relation_lane:
    relation_registry = EntityRegistry(db_session)
    relation_records = await relation_registry.list_relations(
        subject_id=context.subject_id, limit=plan.relation_limit,
    )
```

- [ ] **Step 3：测试 + commit**

```bash
git add sebastian/memory/entity_registry.py sebastian/memory/retrieval.py tests/unit/memory/test_entity_registry.py tests/unit/memory/test_retrieval.py
git commit -m "feat(memory): 新增 Relation Lane 注入当前有效关系"
```

---

### Task D4：Assembler 完整过滤 + current/historical 显式标题

**Files:**
- Modify: `sebastian/memory/retrieval.py`（`MemorySectionAssembler`）
- Test: `tests/unit/memory/test_retrieval.py`

过滤维度（spec `retrieval.md §6`）：`policy_tags`、`status`、`valid_until`、`confidence >= threshold`、`reader_agent_type 白名单`。

- [ ] **Step 1：写测试**

```python
def test_assembler_filters_low_confidence_records(fake_records):
    # 构造两条 profile：confidence=0.9 / 0.2；threshold=0.3
    # 断言只有 0.9 那条出现在输出
    ...


def test_assembler_renders_current_vs_historical_sections(...):
    text = assembler.assemble(...)
    assert "## Current facts about user" in text
    assert "## Current context" in text  # context lane section
    assert "## Historical evidence" in text
    assert "may be outdated" in text  # 显式标注历史证据
```

- [ ] **Step 2：新 `MemorySectionAssembler`**

```python
MIN_CONFIDENCE = 0.3


class MemorySectionAssembler:
    def assemble(
        self,
        *,
        profile_records: list[Any],
        context_records: list[Any],
        episode_records: list[Any],
        relation_records: list[Any],
        plan: RetrievalPlan,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> str:
        now = datetime.now(UTC)

        def _keep(r: Any) -> bool:
            if DO_NOT_AUTO_INJECT_TAG in (getattr(r, "policy_tags", []) or []):
                return False
            if getattr(r, "confidence", 1.0) < min_confidence:
                return False
            valid_until = getattr(r, "valid_until", None)
            if valid_until is not None and valid_until <= now:
                return False
            return True

        profiles = [r for r in profile_records if _keep(r)][: plan.profile_limit]
        contexts = [r for r in context_records if _keep(r)][: plan.context_limit]
        episodes = [r for r in episode_records if _keep(r)][: plan.episode_limit]
        relations = [r for r in relation_records if _keep(r)][: plan.relation_limit]

        sections: list[str] = []
        if profiles:
            lines = "\n".join(f"- [{r.kind}] {r.content}" for r in profiles)
            sections.append(f"## Current facts about user\n{lines}")
        if contexts:
            lines = "\n".join(f"- {r.content}" for r in contexts)
            sections.append(f"## Current context\n{lines}")
        if relations:
            lines = "\n".join(
                f"- {r.subject_id} {r.predicate} {r.object_ref}" for r in relations
            )
            sections.append(f"## Important relationships\n{lines}")
        if episodes:
            lines = "\n".join(f"- {r.content}" for r in episodes)
            sections.append(
                f"## Historical evidence (may be outdated)\n{lines}"
            )
        return "\n\n".join(sections)
```

- [ ] **Step 3：`retrieve_memory_section` 传入 4 个 lane 结果**

- [ ] **Step 4：跑测试 + commit**

```bash
git add sebastian/memory/retrieval.py tests/unit/memory/test_retrieval.py
git commit -m "feat(memory): Assembler 四段输出并按 confidence/valid_until 过滤"
```

---

### Task D5：`memory_search` 返回结构化 citations

**Files:**
- Modify: `sebastian/capabilities/tools/memory_search/__init__.py`
- Test: `tests/unit/capabilities/test_memory_tools.py`

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_memory_search_returns_structured_items(enabled_memory_state):
    # 预置一条 profile / 一条 episode，调用 memory_search
    result = await memory_search(query="detail")
    assert result.ok
    items = result.output["items"]
    assert all({"kind", "content", "source", "confidence", "is_current"} <= it.keys() for it in items)
```

- [ ] **Step 2：改工具实现**

```python
@tool(name="memory_search", ...)
async def memory_search(query: str, limit: int = 5) -> ToolResult:
    ...
    planner = MemoryRetrievalPlanner()
    plan = planner.plan(RetrievalContext(
        subject_id=subject_id, session_id=..., agent_type=..., user_message=query,
    ))
    # 并行拉 4 lane（目前串行也可以，Phase R-D 先不做真并行）
    profiles = await profile_store.search_active(subject_id=subject_id, limit=plan.profile_limit) if plan.profile_lane else []
    episodes = await episode_store.search(query=query, subject_id=subject_id, limit=plan.episode_limit) if plan.episode_lane else []
    items = []
    for r in profiles:
        items.append({
            "kind": r.kind, "content": r.content, "source": r.source,
            "confidence": r.confidence, "is_current": True,
        })
    for r in episodes:
        items.append({
            "kind": r.kind, "content": r.content, "source": r.source,
            "confidence": r.confidence, "is_current": False,
        })
    return ToolResult(ok=True, output={"items": items[:limit]})
```

- [ ] **Step 3：跑测试 + commit**

```bash
git add sebastian/capabilities/tools/memory_search/__init__.py tests/unit/capabilities/test_memory_tools.py
git commit -m "feat(memory): memory_search 返回结构化 citations 区分 current/historical"
```

---

## Phase R-E：Consolidation 硬化

### Task E1：组装 `ConsolidatorInput` 全量上下文

**Files:**
- Modify: `sebastian/memory/consolidation.py:177-184`
- Test: `tests/integration/test_memory_consolidation.py`

目标：让 LLM 看到 slot 定义、当前 active memory、最近 summary、entity registry 快照，否则归纳无法避免重复。

- [ ] **Step 1：写集成测试**

```python
@pytest.mark.asyncio
async def test_consolidator_input_includes_context(...):
    # 预置 2 条 active profile + 1 条 summary + 1 个 entity
    # Hook 一个 FakeConsolidator 捕获 consolidator_input
    # 断言 active_memories_for_subject 至少含 2 条；recent_summaries 至少 1 条；
    #   slot_definitions 至少含 6 个内建 slot；entity_registry_snapshot 至少 1 个 entity
```

- [ ] **Step 2：在 `consolidate_session` 开事务后先拉上下文**

把构建 `ConsolidatorInput` 的逻辑后移到"开了 session 再构建"，这样可以访问 store：

```python
async with self._db_factory() as session:
    profile_store = ProfileMemoryStore(session)
    episode_store = EpisodeMemoryStore(session)
    entity_registry = EntityRegistry(session)

    subject_id = await resolve_subject(
        MemoryScope.USER, session_id=session_id, agent_type=agent_type,
    )
    active_rows = await profile_store.search_active(subject_id=subject_id, limit=32)
    recent_summary_rows = await episode_store.search_summaries(
        subject_id=subject_id, limit=8,
    )
    entity_rows = await entity_registry.snapshot(limit=64)

    consolidator_input = ConsolidatorInput(
        session_messages=messages,
        candidate_artifacts=[],
        active_memories_for_subject=[
            {"id": r.id, "slot_id": r.slot_id, "kind": r.kind, "content": r.content,
             "confidence": r.confidence, "source": r.source}
            for r in active_rows
        ],
        recent_summaries=[{"content": r.content} for r in recent_summary_rows],
        slot_definitions=[s.model_dump() for s in DEFAULT_SLOT_REGISTRY.list_all()],
        entity_registry_snapshot=[
            {"canonical_name": r.canonical_name, "aliases": r.aliases,
             "type": r.entity_type}
            for r in entity_rows
        ],
    )
    result = await self._consolidator.consolidate(consolidator_input)
    ...
```

> 需要在 `EpisodeMemoryStore` 加 `search_summaries(subject_id, limit)`、在 `EntityRegistry` 加 `snapshot(limit)`、在 `SlotRegistry` 加 `list_all() -> list[SlotDefinition]`。这几个 helper 一并加到本任务里，各自一小段代码。

- [ ] **Step 3：跑测试 + commit**

```bash
git add sebastian/memory/consolidation.py sebastian/memory/episode_store.py sebastian/memory/entity_registry.py sebastian/memory/slots.py tests/integration/test_memory_consolidation.py
git commit -m "feat(memory): 沉淀输入携带 active/summary/slot/entity 上下文"
```

---

### Task E2：把 `MemoryExtractor` 接入生产路径

**Files:**
- Modify: `sebastian/memory/consolidation.py`（Worker 先跑 Extractor 再跑 Consolidator）
- Test: `tests/integration/test_memory_consolidation.py`

spec 要求：Session Consolidation 先由 Extractor 产出 `candidate_artifacts`，再由 Consolidator 汇总、去重、产出 summary / proposed_artifacts。

- [ ] **Step 1：在 `SessionConsolidationWorker` 构造函数增加 `extractor: MemoryExtractor`**

```python
def __init__(
    self, *, db_factory, consolidator: MemoryConsolidator,
    extractor: MemoryExtractor, session_store, memory_settings_fn,
) -> None:
    ...
    self._extractor = extractor
```

- [ ] **Step 2：`consolidate_session` 里先 extract**

```python
candidate_artifacts = await self._extractor.extract(
    ExtractorInput(
        session_messages=messages,
        slot_definitions=[s.model_dump() for s in DEFAULT_SLOT_REGISTRY.list_all()],
    )
)
consolidator_input = ConsolidatorInput(
    session_messages=messages,
    candidate_artifacts=candidate_artifacts,
    ...
)
```

- [ ] **Step 3：在 `gateway/app.py` lifespan 构造 extractor 并传入 worker**

```python
extractor = MemoryExtractor(llm_registry=state.llm_registry)
worker = SessionConsolidationWorker(
    db_factory=state.db_factory, consolidator=consolidator,
    extractor=extractor, session_store=..., memory_settings_fn=...,
)
```

- [ ] **Step 4：测试**

```python
@pytest.mark.asyncio
async def test_worker_runs_extractor_before_consolidator(...):
    # FakeExtractor 返回 2 条 candidate
    # FakeConsolidator 断言 consolidator_input.candidate_artifacts 长度 == 2
```

- [ ] **Step 5：commit**

```bash
git add sebastian/memory/consolidation.py sebastian/gateway/app.py tests/integration/test_memory_consolidation.py
git commit -m "feat(memory): Worker 接入 MemoryExtractor 产出候选记忆"
```

---

### Task E3：执行 `proposed_actions`（SUPERSEDE / EXPIRE）

**Files:**
- Modify: `sebastian/memory/consolidation.py`
- Test: `tests/integration/test_memory_consolidation.py`

spec 要求 Consolidator 可以对已有 memory 提出 SUPERSEDE / EXPIRE 建议；当前完全忽略。

- [ ] **Step 1：写失败测试**

```python
@pytest.mark.asyncio
async def test_worker_executes_proposed_expire_action(...):
    # 预置一条 active profile id="m-old"
    # FakeConsolidator 返回 proposed_actions=[{action: EXPIRE, memory_id: "m-old", reason: "stale"}]
    # 断言跑完后 m-old.status == "EXPIRED" 且 memory_decision_log 有一条 decision=EXPIRE
```

- [ ] **Step 2：在 Worker 循环末尾加 action 执行**

```python
for action in result.proposed_actions:
    if action.action == "EXPIRE" and action.memory_id:
        await profile_store.expire(action.memory_id)
        decision = ResolveDecision(
            decision=MemoryDecisionType.EXPIRE, reason=action.reason,
            old_memory_ids=[action.memory_id], new_memory=None,
            candidate=CandidateArtifact(...stub...),  # 用 zero-confidence placeholder
            subject_id=subject_id, scope=MemoryScope.USER, slot_id=None,
        )
        await decision_logger.append(decision, worker=self._WORKER_ID, model=None, rule_version=self._RULE_VERSION)
    elif action.action == "SUPERSEDE" and action.memory_id:
        # Consolidator 必须配对给 proposed_artifact；这里忽略 action 防止双重处理
        continue
```

- [ ] **Step 3：`ProfileMemoryStore.expire`**

```python
async def expire(self, memory_id: str) -> None:
    now = datetime.now(UTC)
    await self._session.execute(
        update(ProfileMemoryRecord)
        .where(ProfileMemoryRecord.id == memory_id)
        .values(status=MemoryStatus.EXPIRED.value, updated_at=now)
    )
    await self._session.flush()
```

- [ ] **Step 4：跑测试 + commit**

```bash
git add sebastian/memory/consolidation.py sebastian/memory/profile_store.py tests/integration/test_memory_consolidation.py
git commit -m "feat(memory): 执行 Consolidator 的 proposed_actions 中 EXPIRE 动作"
```

---

### Task E4：LLM 调用异常兜底（Extractor + Consolidator）

**Files:**
- Modify: `sebastian/memory/extraction.py:55-74`
- Modify: `sebastian/memory/consolidation.py:89-107`
- Test: `tests/unit/memory/test_extraction.py`、`tests/unit/memory/test_consolidation.py`

目标：除 Pydantic 错误外，`APIStatusError / TimeoutError / NetworkError` 也要被 catch，走重试，重试耗尽仍失败时返回空并 log warning，不让 Worker 整体崩溃。

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_consolidator_returns_empty_when_stream_raises(fake_registry_raises_timeout):
    result = await consolidator.consolidate(some_input)
    assert result.summaries == [] and result.proposed_artifacts == []
```

- [ ] **Step 2：统一异常处理**

在 `_call_llm` 外层包一层，或者把 `consolidate/extract` 循环改为：

```python
empty = ConsolidationResult()
for attempt in range(self._max_retries + 1):
    try:
        raw = await self._call_llm(resolved, system, messages)
        return ConsolidationResult.model_validate_json(raw)
    except (ValidationError, ValueError, TimeoutError) as e:
        last_exc: Exception | None = e
    except Exception as e:  # noqa: BLE001 — 捕获 provider 具体异常
        last_exc = e
    if attempt < self._max_retries:
        logger.warning("Consolidator attempt %d failed: %s", attempt + 1, last_exc)
        await asyncio.sleep(0.5 * (2 ** attempt))  # 指数退避，0.5 / 1.0 / 2.0s
        continue
    logger.warning("Consolidator exhausted retries: %s", last_exc)
    return empty
```

同样方式改 `MemoryExtractor.extract`。

- [ ] **Step 3：跑测试 + commit**

```bash
git add sebastian/memory/extraction.py sebastian/memory/consolidation.py tests/unit/memory/test_extraction.py tests/unit/memory/test_consolidation.py
git commit -m "fix(memory): LLM 异常兜底重试后返回空结果避免 Worker 崩溃"
```

---

### Task E5：Catch-up sweep（启动时扫描未沉淀的 completed session）

**Files:**
- Modify: `sebastian/memory/startup.py`
- Modify: `sebastian/gateway/app.py`（lifespan 调用）
- Modify: `sebastian/memory/consolidation.py`（新增 `sweep_unconsolidated` 方法）
- Test: `tests/integration/test_memory_catchup_sweep.py`

- [ ] **Step 1：新增 sweep 函数**

在 `SessionConsolidationScheduler` 或 Worker 模块加一个启动级 coroutine：

```python
async def sweep_unconsolidated(
    *, db_factory, worker: SessionConsolidationWorker, memory_settings_fn,
) -> None:
    if not memory_settings_fn():
        return
    async with db_factory() as s:
        from sqlalchemy import select
        from sebastian.store.models import SessionRecord, SessionConsolidationRecord
        done_q = select(SessionRecord.id, SessionRecord.agent_type).where(
            SessionRecord.status == "completed"
        )
        marker_q = select(SessionConsolidationRecord.session_id, SessionConsolidationRecord.agent_type)
        done = {(a, b) async for a, b in s.stream(done_q)}
        marked = {(a, b) async for a, b in s.stream(marker_q)}
        todo = done - marked
    for session_id, agent_type in todo:
        await worker.consolidate_session(session_id, agent_type)
```

> 若 `SessionRecord.status` 字段不同（项目里实际字段名），按真实字段调整。`async for` 迭代 `session.stream` 的语法若无需，改为直接 `scalars().all()` 取一次。

- [ ] **Step 2：`gateway/app.py` lifespan 启动完成后调一次**

```python
await sweep_unconsolidated(
    db_factory=state.db_factory, worker=worker,
    memory_settings_fn=lambda: state.memory_settings.enabled,
)
```

- [ ] **Step 3：集成测试 + commit**

测试：先插入一个 completed session，无 marker，启动 sweep，断言 marker 被写入、记忆落库。

```bash
git add sebastian/memory/consolidation.py sebastian/memory/startup.py sebastian/gateway/app.py tests/integration/test_memory_catchup_sweep.py
git commit -m "feat(memory): 启动时 sweep 未沉淀 session 避免崩溃丢失"
```

---

## Phase R-F：启动与基础设施

### Task F1：启动时 `sync_jieba_terms()` + seed 内建 slots

**Files:**
- Modify: `sebastian/memory/startup.py`
- Modify: `sebastian/gateway/app.py`（lifespan 调用）
- Test: `tests/integration/test_memory_startup.py`

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_startup_seeds_builtin_slots_and_jieba(tmp_engine):
    from sqlalchemy import select
    from sebastian.store.models import MemorySlotRecord
    import jieba
    # 调 init_memory_storage + seed_builtin_slots + sync_jieba_terms
    ...
    async with factory() as s:
        rows = (await s.scalars(select(MemorySlotRecord))).all()
        assert len(rows) >= 6  # 6 个内建 slot
        assert all(r.is_builtin for r in rows)
```

- [ ] **Step 2：在 startup.py 增加 `seed_builtin_slots` + 更新 `init_memory_storage` 汇总**

```python
async def seed_builtin_slots(session: AsyncSession) -> None:
    from sqlalchemy import select
    from sebastian.memory.slots import DEFAULT_SLOT_REGISTRY
    from sebastian.store.models import MemorySlotRecord

    existing = {
        r[0] for r in (await session.execute(select(MemorySlotRecord.slot_id))).all()
    }
    for slot in DEFAULT_SLOT_REGISTRY.list_all():
        if slot.slot_id in existing:
            continue
        session.add(MemorySlotRecord(
            slot_id=slot.slot_id,
            scope=slot.scope.value,
            subject_kind=slot.subject_kind,
            cardinality=slot.cardinality.value,
            resolution_policy=slot.resolution_policy.value,
            kind_constraints=[k.value for k in slot.kind_constraints],
            description=slot.description,
            is_builtin=True,
        ))
    await session.commit()
```

- [ ] **Step 3：gateway `lifespan` 里依次调**

```python
await init_memory_storage(state.db_engine)
async with state.db_factory() as s:
    await seed_builtin_slots(s)
    registry = EntityRegistry(s)
    await registry.sync_jieba_terms()
```

- [ ] **Step 4：commit**

```bash
git add sebastian/memory/startup.py sebastian/gateway/app.py tests/integration/test_memory_startup.py
git commit -m "feat(memory): 启动时 seed 内建 slots 并同步 jieba 词典"
```

---

### Task F2：EntityRegistry 用 SQL 索引查找替换全表扫描

**Files:**
- Modify: `sebastian/memory/entity_registry.py:62-69`
- Modify: `sebastian/store/models.py`（给 `EntityRecord.canonical_name` 加 index，若未加）
- Test: `tests/unit/memory/test_entity_registry.py`

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_lookup_matches_by_canonical_and_alias(registry, session):
    await registry.upsert_entity("小橘", "pet", aliases=["橘猫", "橘子"])
    await session.commit()
    assert len(await registry.lookup("小橘")) == 1
    assert len(await registry.lookup("橘猫")) == 1
    assert len(await registry.lookup("其他")) == 0
```

- [ ] **Step 2：改 `lookup` 用 SQL 而非 Python 过滤**

```python
from sqlalchemy import func, or_

async def lookup(self, text: str) -> list[EntityRecord]:
    # canonical 用等值索引；aliases 是 JSON，用 json_each 或字符串包含（SQLite 单库可接受）
    result = await self._session.scalars(
        select(EntityRecord).where(
            or_(
                EntityRecord.canonical_name == text,
                func.instr(func.json(EntityRecord.aliases), f'"{text}"') > 0,
            )
        )
    )
    return list(result.all())
```

> 迁移到 Postgres 时可改为 `aliases @> jsonb_build_array(...)`；当前 SQLite 可用 `instr` + JSON 文本匹配。确保 `EntityRecord.canonical_name` 有 `Index`。

- [ ] **Step 3：给 `canonical_name` 加索引（若未加）**

`sebastian/store/models.py` `EntityRecord.__table_args__` 或列上加 `index=True`。

- [ ] **Step 4：跑测试 + commit**

```bash
git add sebastian/memory/entity_registry.py sebastian/store/models.py tests/unit/memory/test_entity_registry.py
git commit -m "perf(memory): EntityRegistry.lookup 改走 SQL 索引避免全表扫描"
```

---

### Task F3：`RelationCandidateRecord` 补 `valid_from / valid_until / status`

**Files:**
- Modify: `sebastian/store/models.py:179-192`
- Test: `tests/unit/memory/test_schema.py`

- [ ] **Step 1：加字段**

```python
class RelationCandidateRecord(Base):
    __tablename__ = "relation_candidates"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    subject_id: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[str] = mapped_column(String)
    object_ref: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default=MemoryStatus.ACTIVE.value, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 2：test_schema 断言新字段存在**

```python
def test_relation_candidate_has_time_fields():
    from sebastian.store.models import RelationCandidateRecord
    cols = RelationCandidateRecord.__table__.c
    assert "valid_from" in cols
    assert "valid_until" in cols
    assert "status" in cols
```

- [ ] **Step 3：commit**

```bash
git add sebastian/store/models.py tests/unit/memory/test_schema.py
git commit -m "feat(memory): RelationCandidate 补 valid_from/valid_until/status 字段"
```

> 若项目在生产环境已跑过 `init_db`，需要提供一次性迁移脚本（Alembic 或手写 `ALTER TABLE`）。开发阶段删库重建即可。请在 commit 消息或 `docs/architecture/spec/memory/migration.md` 说明迁移方式。

---

### Task F4：FTS MATCH 查询转义

**Files:**
- Modify: `sebastian/memory/episode_store.py:65-70`
- Test: `tests/unit/memory/test_episode_store.py`

- [ ] **Step 1：写测试**

```python
@pytest.mark.asyncio
async def test_episode_store_search_escapes_fts_operators(episode_store, session):
    # 预置一条 episode 内容包含 "OR"
    # 查询 "OR" 应该返回内容匹配的那条，而非触发 FTS OR 运算导致异常
    ...
```

- [ ] **Step 2：改查询构造**

```python
def _build_match_query(terms: list[str]) -> str:
    # 把每个 term 包成 phrase，防止 OR/AND/* 被解释为操作符
    safe = [f'"{t.replace(chr(34), chr(34)*2)}"' for t in terms if t]
    return " ".join(safe) or '""'

# 查询时：
match_query = _build_match_query(terms_for_query(query))
await self._session.execute(
    text("SELECT memory_id FROM episode_fts WHERE content_segmented MATCH :q"),
    {"q": match_query},
)
```

- [ ] **Step 3：commit**

```bash
git add sebastian/memory/episode_store.py tests/unit/memory/test_episode_store.py
git commit -m "fix(memory): FTS MATCH 查询按 phrase 转义避免解析错误"
```

---

### Task F5：`MemoryDecisionLogger` 透传 model + session_id

**Files:**
- Modify: `sebastian/memory/decision_log.py`
- Modify: `sebastian/memory/consolidation.py`（传 model + resolved provider 信息）
- Test: `tests/unit/memory/test_decision_log.py`

- [ ] **Step 1：`append` 接口保持，写入时把 `decision.new_memory.provenance["session_id"]`（如果有）回填到 log record 的 metadata 列**

```python
record = MemoryDecisionLogRecord(
    id=str(uuid4()),
    ...
    model=model,
    session_id=(decision.new_memory.provenance.get("session_id")
               if decision.new_memory else None),
    ...
)
```

需同步在 `store/models.py` 的 `MemoryDecisionLogRecord` 增加 `session_id: str | None`。

- [ ] **Step 2：Consolidator 调用时传 model**

在 `MemoryConsolidator` 暴露最近一次 resolved provider / model：

```python
class MemoryConsolidator:
    ...
    last_resolved: ResolvedProvider | None = None

    async def consolidate(self, ...):
        self.last_resolved = resolved
        ...
```

Worker 侧：

```python
await decision_logger.append(
    decision, worker=self._WORKER_ID,
    model=getattr(self._consolidator.last_resolved, "model", None),
    rule_version=self._RULE_VERSION,
)
```

- [ ] **Step 3：测试 + commit**

```bash
git add sebastian/memory/decision_log.py sebastian/memory/consolidation.py sebastian/store/models.py tests/unit/memory/test_decision_log.py
git commit -m "feat(memory): decision_log 透传 model 与 session_id 便于审计"
```

---

## Phase R-G：测试补强

### Task G1：Resolver 全分支覆盖

**Files:**
- Modify: `tests/unit/memory/test_resolver.py`

补 6 条用例：
1. `SINGLE + slot + no existing → ADD`
2. `APPEND_ONLY policy（non-SINGLE cardinality）→ ADD`
3. `INFERRED + no slot + confidence=0.5 → 走 fallback ADD`
4. `kind=RELATION → fallback ADD（slot_id 可为 None）`
5. `source=EXPLICIT 覆盖 source=INFERRED 的 existing → SUPERSEDE`（配合 Task B4）
6. `source=INFERRED + low confidence 对 EXPLICIT existing → DISCARD`（配合 Task B4）

每条用例先写出期望断言、运行失败、检查源码是否缺陷。

- [ ] 写 6 条用例
- [ ] 跑 `pytest tests/unit/memory/test_resolver.py -v`
- [ ] commit: `test(memory): 补齐 resolver 全部决策分支用例`

---

### Task G2：SUPERSEDE 全链路集成测试

**Files:**
- Create: `tests/integration/test_memory_supersede_chain.py`

场景：
1. 预置一条 `ProfileMemoryRecord`（slot=`user.profile.name`, content="旧名"）。
2. 跑 `memory_save(content="新名", slot_id="user.profile.name")`。
3. 断言：
   - 旧记录 `status=SUPERSEDED`
   - 新记录 `status=ACTIVE`
   - `MemoryDecisionLogRecord` 有一条 `decision=SUPERSEDE`、`old_memory_ids=[旧id]`、`new_memory_id=新id`
   - `memory_search(query="名")` 只返回新记录（走 `search_active` 带 valid_until 过滤）

- [ ] 写测试文件（用真 SQLite in-memory + 真 tool 调用）
- [ ] 跑通
- [ ] commit: `test(memory): 新增 SUPERSEDE 全链路集成测试`

---

### Task G3：并发幂等测试（触发 IntegrityError catch）

**Files:**
- Create: `tests/integration/test_memory_consolidation_concurrency.py`

```python
@pytest.mark.asyncio
async def test_two_concurrent_consolidations_produce_one_marker(...):
    # 用 asyncio.gather 并发跑 2 次 worker.consolidate_session(session_id, agent_type)
    # 断言 SessionConsolidationRecord 只有一行、episode_memories 没出现重复 summary
    results = await asyncio.gather(
        worker.consolidate_session("s1", "default"),
        worker.consolidate_session("s1", "default"),
        return_exceptions=True,
    )
    # 两个都不应抛异常
    assert all(not isinstance(r, Exception) for r in results)
```

- [ ] 写测试（关键：两个 worker 共享同一个 `db_factory` 但各自 `async with` 开独立 session）
- [ ] 跑通
- [ ] commit: `test(memory): 并发沉淀幂等覆盖 IntegrityError 回滚路径`

---

### Task G4：Extractor/Consolidator LLM 参数断言

**Files:**
- Modify: `tests/unit/memory/test_extraction.py`、`tests/unit/memory/test_consolidation.py`

现状：`FakeLLMProvider.stream(**kwargs)` 吞掉所有参数，prompt contract 改错无人发现。

- [ ] **Step 1：把 Fake 改为记录参数**

```python
class CapturingLLMProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def stream(self, **kwargs):
        self.calls.append(kwargs)
        from sebastian.core.stream_events import TextDelta
        yield TextDelta(delta=self.response)
```

- [ ] **Step 2：断言参数内容**

```python
async def test_extractor_prompt_contains_schema_instruction(...):
    await extractor.extract(sample_input)
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert "ExtractorOutput" in call["system"] or "json" in call["system"].lower()
    user_content = call["messages"][0]["content"]
    # user_content 应是合法 JSON 且包含 session_messages 字段
    import json
    payload = json.loads(user_content)
    assert "session_messages" in payload
    assert "slot_definitions" in payload
```

同样改 test_consolidation.

- [ ] **Step 3：commit**

```bash
git add tests/unit/memory/test_extraction.py tests/unit/memory/test_consolidation.py
git commit -m "test(memory): 断言 LLM 调用的 system/messages/schema 契约"
```

---

### Task G5：`memory_tools` 加 DB-state 断言

**Files:**
- Modify: `tests/unit/capabilities/test_memory_tools.py`

原断言只写 `assert result.output is not None`，改为 `select` 真实表行数并比对内容。

- [ ] 改断言
- [ ] commit: `test(memory): memory_save/search 测试补 DB state 断言`

---

### Task G6：`MemoryConsolidationScheduler` 暴露 public `drain()` API

**Files:**
- Modify: `sebastian/memory/consolidation.py`
- Modify: `tests/integration/test_memory_consolidation_lifecycle.py`

当前测试用 `list(scheduler._pending_tasks)` 访问私有集合。加个公开：

```python
async def drain(self) -> None:
    """Wait for all pending consolidation tasks to finish (for tests and graceful shutdown)."""
    pending = list(self._pending_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
```

并把 lifecycle 测试改为调用 `drain()`。

- [ ] commit: `refactor(memory): Scheduler 暴露 drain() 替代私有集合访问`

---

## 自检（Self-Review）

> 执行人每组 commit 前对照本列表确认：

- [ ] 所有 Step 3/4（实现+测试）的代码片段与真实导入路径一致
- [ ] 新引用的符号（`resolve_subject`、`persist_decision`、`seed_builtin_slots`、`sweep_unconsolidated`、`EntityRegistry.snapshot`、`SlotRegistry.list_all`、`MemorySlotRecord`、`ProfileMemoryStore.expire`、`ProfileMemoryStore.search_recent_context`、`EpisodeMemoryStore.search_summaries`、`EntityRegistry.list_relations`）都在前置任务里已定义
- [ ] `MemoryScope`、`MemoryDecisionType`、`MemorySource` 在本 plan 之后全部大写（Task A1 已改）
- [ ] CHANGELOG.md 有对应变更条目：
  - Fixed：search_active 过期过滤；memory_save DISCARD 审计；沉淀 summary 审计；resolver 优先级；FTS MATCH 转义；LLM 异常兜底；假阳性测试
  - Added：write_router；subject resolver；Context/Relation Lane；memory_search 结构化输出；catch-up sweep；启动 seed slots & jieba 同步；proposed_actions 执行
  - Changed：MemoryDecisionType 枚举大写；`MemorySummary.scope` 枚举化；RelationCandidate 表结构
- [ ] 不引入向量库、不注册 memory_list/memory_delete 工具、不把 DB session 做成 singleton、`memory_enabled=False` 时不自动读/写/沉淀

## 执行顺序约束

- R-A 必须先做（A1 改枚举会影响 B/C/D/E 所有涉及 `MemoryDecisionType` 的代码）
- B1/B2/B3 相互独立，可并行
- B4 前提：A1/A2 已合入（需要 `ResolveDecision` validator 与大写枚举）
- C3（write_router）依赖 C1/C2（subject resolver）和 F3（RelationCandidate 字段），建议在 F3 之后做 C3；若先做 C3，relation 分支先临时写成 `raise NotImplementedError`，F3 合入后再补。
- E1 依赖 C1/C2/C3 完整组合
- E2 依赖 E1
- E3 依赖 E2
- E5 依赖 E2
- F1 独立可做
- G1–G6 最后做，需要 R-A 到 R-F 全部合入

## 执行选择

Plan 完成并保存在 `docs/superpowers/plans/2026-04-19-memory-system-remediation.md`。可选执行方式：

1. **Subagent-Driven（推荐）**：由 superpowers:subagent-driven-development 每任务派发 fresh subagent，任务间 review。
2. **Inline Execution**：使用 superpowers:executing-plans 在当前会话分批执行 + checkpoint。

请选择执行方式。
