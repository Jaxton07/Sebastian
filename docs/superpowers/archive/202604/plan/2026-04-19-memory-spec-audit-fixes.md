# Memory Spec Audit Fixes Implementation Plan

> **Status: NOT ADOPTED / 未采纳。**
>
> 这份计划保留为 Claude spec audit 的参考材料，不作为执行计划使用。
> 主要原因：
> - 范围过大，试图一次修复 12 个 GAP，会把 correctness 修复和未定语义的 Phase C/D 能力混在一起。
> - BaseAgent session-idle hook 方案会把 turn completion 误用为 `SESSION_COMPLETED`，可能导致过早沉淀。
> - Cross-session / maintenance MVP 片段缺少完整 decision log 审计和失败语义，不符合 memory 写入统一审计约束。
> - summary replacement 与 relation(exclusive) 需要先定义唯一键、冲突范围和生命周期策略，不能临时以 payload 字段拼接。
>
> 当前采用的执行计划是：
> [`2026-04-19-memory-spec-audit-targeted-fixes.md`](../../../plans/2026-04-19-memory-spec-audit-targeted-fixes.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-04-19 memory spec 合规审查发现的全部 13 个 GAP，使记忆模块实现完全对齐 `docs/architecture/spec/memory/` 下 7 份 spec。

**Architecture:** 分 4 个阶段渐进修复：(1) Schema/Filter 本地修复；(2) Resolver/Policy 默认策略补齐；(3) BaseAgent hook 拆分；(4) Cross-Session & Maintenance 两类 Phase C 后台 Worker。每阶段独立可提交、可验证，可按优先级分批 merge。

> **Deferred**：GAP #4（LLMProvider temperature）暂不修，先用 provider 默认参数跑，评估效果后再决定是否打通 `stream(temperature=...)`——否则所有 provider 调用点都要同步改。

**Tech Stack:** Python 3.12 + SQLAlchemy async + Pydantic v2 + pytest + aiosqlite + FTS5 + jieba。

---

## 审查 GAP 与任务映射

| GAP # | 审查条款 | 严重度 | 任务 |
|---|---|---|---|
| 1 | retrieval §6 `valid_from` 过滤缺失 | 🔴 | Task 2 |
| 2 | retrieval §4.3 Episode Lane summary 优先未实现 | 🔴 | Task 6 |
| 3 | implementation §6 `ExtractorInput.task` 字段缺失 | 🔴 | Task 1 |
| 4 | implementation §11 LLM temperature 不可控 | 🔴 | **Deferred**（先用 provider 默认） |
| 5 | artifact-model §10 summary 默认替换未实现 | 🟡 | Task 8 |
| 6 | artifact-model §10 relation(exclusive) 时间边界未实现 | 🟡 | Task 9 |
| 7 | consolidation §1.2 Cross-Session 未实现 | 🟡 | Task 13 |
| 8 | consolidation §1.3 Maintenance 只有 EXPIRE | 🟡 | Task 14 |
| 9 | overview §5.3 BaseAgent hook 拆分不足 | 🟡 | Task 11, 12 |
| 10 | retrieval §6 Assembler 缺 status/scope 安全网 | 🟢 | Task 3 |
| 11 | retrieval §8 memory_search current truth 标注不明 | 🟢 | Task 4 |
| 12 | storage §6 decision_log 缺 input_source | 🟢 | Task 7 |
| 13 | retrieval §6 Assembler 标题措辞偏差 | 🟢 | Task 5 |

---

## 文件结构总览

**新增文件：**
- `sebastian/memory/maintenance.py` — MemoryMaintenanceWorker（Task 14）
- `sebastian/memory/cross_session.py` — CrossSessionConsolidationWorker（Task 13）
- `tests/unit/memory/test_maintenance.py`（Task 14）
- `tests/unit/memory/test_cross_session.py`（Task 13）

**修改文件：**
- `sebastian/memory/extraction.py` — ExtractorInput.task 字段（Task 1）
- `sebastian/memory/retrieval.py` — Assembler 过滤器扩展 + Episode Lane 两段式 + 标题对齐（Task 2, 3, 5, 6, 11）
- `sebastian/memory/resolver.py` — summary 默认替换 + relation exclusive time_bound（Task 8, 9）
- `sebastian/memory/write_router.py` — relation exclusive supersede 逻辑（Task 9）
- `sebastian/memory/decision_log.py` — input_source 字段透传（Task 7）
- `sebastian/store/models.py` — MemoryDecisionLogRecord 增加 input_source 列（Task 7）
- `sebastian/capabilities/tools/memory_search/__init__.py` — citations current_truth 语义（Task 4）
- `sebastian/core/base_agent.py` — 拆分 `_memory_plan` / `_memory_section` + session-idle hook（Task 11, 12）
- `sebastian/gateway/app.py` — 注册 MaintenanceWorker / CrossSessionWorker 启动项（Task 13, 14）
- `CHANGELOG.md` — 每阶段末尾追加条目

**新增测试文件：**
- `tests/unit/memory/test_maintenance.py`
- `tests/unit/memory/test_cross_session.py`

**扩展测试文件：**
- `tests/unit/memory/test_retrieval.py`
- `tests/unit/memory/test_resolver.py`
- `tests/unit/memory/test_extraction.py`
- `tests/unit/memory/test_consolidation.py`
- `tests/unit/memory/test_decision_log.py`
- `tests/unit/memory/test_write_router.py`
- `tests/unit/memory/test_memory_search_tool.py`

---

## Phase 1: Schema & Filter 修复（Task 1–7）

本阶段修复 🔴/🟢 本地 GAP，不触及 Worker 和 BaseAgent 主链路，风险最低。可独立 PR。

---

### Task 1: ExtractorInput 增加 `task` 字段（GAP #3）

**Files:**
- Modify: `sebastian/memory/extraction.py:18-21`
- Test: `tests/unit/memory/test_extraction.py`

**背景：** spec `implementation.md §6` 要求 `ExtractorInput` 第一个字段必须是 `task: Literal["extract_memory_artifacts"]`，用于区分不同 LLM 请求类型与 schema。当前实现只有 3 字段。

- [ ] **Step 1: 补一个会失败的测试**

在 `tests/unit/memory/test_extraction.py` 末尾追加：

```python
def test_extractor_input_has_task_field_with_fixed_literal() -> None:
    """ExtractorInput 必须带 task 字段且值固定为 extract_memory_artifacts。"""
    from sebastian.memory.extraction import ExtractorInput

    inp = ExtractorInput(
        subject_context={},
        conversation_window=[],
        known_slots=[],
    )
    assert inp.task == "extract_memory_artifacts"

    # 显式传非法值应被 Pydantic 拒绝
    import pytest
    with pytest.raises(Exception):
        ExtractorInput(
            task="wrong_task",  # type: ignore[arg-type]
            subject_context={},
            conversation_window=[],
            known_slots=[],
        )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_extraction.py::test_extractor_input_has_task_field_with_fixed_literal -v
```

Expected: FAIL（`task` 属性不存在）。

- [ ] **Step 3: 实现 task 字段**

修改 `sebastian/memory/extraction.py:18-21`：

```python
from typing import Literal

class ExtractorInput(BaseModel):
    task: Literal["extract_memory_artifacts"] = "extract_memory_artifacts"
    subject_context: dict[str, Any]
    conversation_window: list[dict[str, Any]]
    known_slots: list[dict[str, Any]]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_extraction.py -v
```

Expected: PASS。

- [ ] **Step 5: 全量 lint/type/test**

```bash
ruff check sebastian/memory/extraction.py tests/unit/memory/test_extraction.py
mypy sebastian/memory/extraction.py
```

Expected: 0 error。

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/extraction.py tests/unit/memory/test_extraction.py
git commit -m "fix(memory): ExtractorInput 补 task 字段满足 spec §6"
```

---

### Task 2: Assembler 增加 `valid_from` 过滤（GAP #1 🔴）

**Files:**
- Modify: `sebastian/memory/retrieval.py:92-118`
- Test: `tests/unit/memory/test_retrieval.py`

**背景：** spec `retrieval.md §6` 要求 Assembler 过滤 `valid_from / valid_until`。当前 `_keep` 仅检查 `valid_until`，未生效（`valid_from > now`）记忆仍会被注入 prompt，违反 spec §8 "current truth"。

- [ ] **Step 1: 补一个会失败的测试**

在 `tests/unit/memory/test_retrieval.py` 的 `TestMemorySectionAssembler` 类中追加：

```python
def test_assemble_drops_records_not_yet_valid(self) -> None:
    """valid_from 在未来的记录不得被注入（尚未生效）。"""
    from datetime import UTC, datetime, timedelta
    from sebastian.memory.retrieval import MemorySectionAssembler, RetrievalPlan

    now = datetime.now(UTC)
    future = now + timedelta(days=1)

    class FakeRec:
        def __init__(self, vf: datetime | None) -> None:
            self.kind = "fact"
            self.content = "future fact"
            self.confidence = 0.9
            self.policy_tags: list[str] = []
            self.valid_from = vf
            self.valid_until = None

    assembler = MemorySectionAssembler()
    out = assembler.assemble(
        profile_records=[FakeRec(future)],
        context_records=[],
        episode_records=[],
        relation_records=[],
        plan=RetrievalPlan(profile_lane=True),
    )
    assert "future fact" not in out
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler::test_assemble_drops_records_not_yet_valid -v
```

Expected: FAIL（当前未过滤 `valid_from`）。

- [ ] **Step 3: 在 `_keep` 增加 valid_from 分支**

修改 `sebastian/memory/retrieval.py:111-118`：

```python
            valid_from = getattr(record, "valid_from", None)
            if valid_from is not None:
                if valid_from.tzinfo is None:
                    valid_from = valid_from.replace(tzinfo=UTC)
                if valid_from > now:
                    return False
            valid_until = getattr(record, "valid_until", None)
            if valid_until is not None:
                if valid_until.tzinfo is None:
                    valid_until = valid_until.replace(tzinfo=UTC)
                if valid_until <= now:
                    return False
            return True
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add sebastian/memory/retrieval.py tests/unit/memory/test_retrieval.py
git commit -m "fix(memory): Assembler 过滤 valid_from 未生效的记忆"
```

---

### Task 3: Assembler 增加 status/scope/subject_id 安全网（GAP #10）

**Files:**
- Modify: `sebastian/memory/retrieval.py:61-118`
- Test: `tests/unit/memory/test_retrieval.py`

**背景：** spec `retrieval.md §6` 明确 Assembler 必须过滤 status / scope / subject_id，当前仅靠 store 层查询条件约束，Assembler 层无二次校验。若未来新增写入路径绕过 store 层直传记录给 Assembler 会泄漏。

- [ ] **Step 1: 补一个会失败的测试**

```python
def test_assemble_drops_non_active_records(self) -> None:
    """即使 store 返回 status != active 的记录，Assembler 必须过滤掉。"""
    from sebastian.memory.retrieval import MemorySectionAssembler, RetrievalPlan

    class FakeRec:
        def __init__(self, status: str) -> None:
            self.kind = "fact"
            self.content = f"rec-{status}"
            self.status = status
            self.confidence = 0.9
            self.policy_tags: list[str] = []
            self.valid_from = None
            self.valid_until = None

    assembler = MemorySectionAssembler()
    out = assembler.assemble(
        profile_records=[FakeRec("active"), FakeRec("superseded"), FakeRec("expired")],
        context_records=[],
        episode_records=[],
        relation_records=[],
        plan=RetrievalPlan(profile_lane=True),
    )
    assert "rec-active" in out
    assert "rec-superseded" not in out
    assert "rec-expired" not in out


def test_assemble_drops_mismatched_subject(self) -> None:
    """Assembler 必须过滤掉 subject_id 与 context 不一致的记录（防串数据）。"""
    from sebastian.memory.retrieval import (
        MemorySectionAssembler,
        RetrievalContext,
        RetrievalPlan,
    )

    class FakeRec:
        def __init__(self, sid: str) -> None:
            self.kind = "fact"
            self.content = f"rec-{sid}"
            self.subject_id = sid
            self.status = "active"
            self.confidence = 0.9
            self.policy_tags: list[str] = []
            self.valid_from = None
            self.valid_until = None

    assembler = MemorySectionAssembler()
    ctx = RetrievalContext(
        subject_id="alice",
        session_id="s1",
        agent_type="test",
        user_message="hi",
    )
    out = assembler.assemble(
        profile_records=[FakeRec("alice"), FakeRec("bob")],
        context_records=[],
        episode_records=[],
        relation_records=[],
        plan=RetrievalPlan(profile_lane=True),
        context=ctx,
    )
    assert "rec-alice" in out
    assert "rec-bob" not in out
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler::test_assemble_drops_non_active_records tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler::test_assemble_drops_mismatched_subject -v
```

Expected: FAIL。

- [ ] **Step 3: `_keep` 增加 status / subject_id 过滤**

在 `sebastian/memory/retrieval.py:92` 的 `_keep` 函数起始位置追加（在 policy_tags 判定之前）：

```python
        def _keep(record: Any) -> bool:
            status = getattr(record, "status", None)
            if status is not None and status != "active":
                return False
            record_subject = getattr(record, "subject_id", None)
            if (
                record_subject is not None
                and effective_context.subject_id
                and record_subject != effective_context.subject_id
            ):
                return False
            policy_tags = getattr(record, "policy_tags", None) or []
            # ... 以下保持原样
```

> **说明：** scope 安全网同理——由于目前所有 store 查询都按 subject_id 过滤，scope 隐含在 subject 内，不再单独做字段校验。如果未来引入跨 scope 拉取需要再加。

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_retrieval.py -v
```

Expected: PASS，且不破坏已有测试。

- [ ] **Step 5: 提交**

```bash
git add sebastian/memory/retrieval.py tests/unit/memory/test_retrieval.py
git commit -m "fix(memory): Assembler 增补 status/subject_id 二次过滤安全网"
```

---

### Task 4: memory_search 工具补 valid_from 过滤 + 明确 current truth（GAP #11）

**Files:**
- Modify: `sebastian/capabilities/tools/memory_search/__init__.py:72-92`
- Test: `tests/unit/memory/test_memory_save_search_tools.py`（现有）或新建 `tests/unit/memory/test_memory_search_tool.py`

**背景：** spec `retrieval.md §8` 要求 current truth 仅来自 `active + 时间上有效` 的事实。memory_search 的 citations 用布尔 `is_current`，但 profile_records 并未二次检查 `valid_from`，且 episode 一律 `is_current=False` 也不对（summary 也是 episode）。

- [ ] **Step 1: 找到现有测试文件**

```bash
ls tests/unit/memory/ | grep -i memory_save
```

若存在测试文件，在该文件追加；若不存在则新建 `tests/unit/memory/test_memory_search_tool.py`。

- [ ] **Step 2: 补一个会失败的测试**

```python
# tests/unit/memory/test_memory_search_tool.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sebastian.capabilities.tools.memory_search import memory_search
from sebastian.memory.types import (
    MemoryArtifact,
    MemoryKind,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)


@pytest.mark.asyncio
async def test_memory_search_excludes_not_yet_valid_from_current_truth(
    memory_enabled_gateway,
) -> None:
    """valid_from 在未来的 profile 记录不应作为 current truth 返回。"""
    from sebastian.memory.profile_store import ProfileMemoryStore

    future = datetime.now(UTC) + timedelta(days=1)
    artifact = MemoryArtifact(
        id="m-future",
        kind=MemoryKind.FACT,
        scope=MemoryScope.USER,
        subject_id="owner",
        slot_id="user.location.city",
        cardinality=None,
        resolution_policy=None,
        content="住在东京",
        structured_payload={},
        source=MemorySource.EXPLICIT,
        confidence=0.9,
        status=MemoryStatus.ACTIVE,
        valid_from=future,
        valid_until=None,
        recorded_at=datetime.now(UTC),
        last_accessed_at=None,
        access_count=0,
        provenance={},
        links=[],
        embedding_ref=None,
        dedupe_key=None,
        policy_tags=[],
    )
    async with memory_enabled_gateway.db_factory() as session:
        await ProfileMemoryStore(session).add(artifact)
        await session.commit()

    result = await memory_search(query="东京")
    assert result.ok
    items = result.output["items"]
    assert all(item["content"] != "住在东京" for item in items)
```

> **说明：** 若没有 `memory_enabled_gateway` fixture，参考 `tests/unit/memory/` 下其它文件的 fixture 使用方式；必要时 mock `state.db_factory` 与 `state.memory_settings`.

- [ ] **Step 3: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_memory_search_tool.py -v
```

Expected: FAIL。

- [ ] **Step 4: 在 memory_search 工具中二次过滤 + 区分语义**

修改 `sebastian/capabilities/tools/memory_search/__init__.py:72-92`，在组装 items 前过滤 valid_from，并用更明确的字段：

```python
    now = datetime.now(UTC)

    def _is_current(record: Any) -> bool:
        valid_from = getattr(record, "valid_from", None)
        valid_until = getattr(record, "valid_until", None)
        if valid_from is not None and valid_from > now:
            return False
        if valid_until is not None and valid_until <= now:
            return False
        return True

    items: list[dict[str, Any]] = []
    for record in profile_records:
        if not _is_current(record):
            continue
        items.append(
            {
                "kind": record.kind,
                "content": record.content,
                "source": record.source,
                "confidence": record.confidence if record.confidence is not None else 1.0,
                "citation_type": "current_truth",
                "is_current": True,
            }
        )
    for record in episode_records:
        citation_type = (
            "current_summary" if record.kind == "summary" else "historical_evidence"
        )
        items.append(
            {
                "kind": record.kind,
                "content": record.content,
                "source": record.source,
                "confidence": record.confidence if record.confidence is not None else 1.0,
                "citation_type": citation_type,
                "is_current": citation_type == "current_summary",
            }
        )
```

同文件顶部确保 `from datetime import UTC, datetime` 已导入。

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/unit/memory/ -k "memory_search or search_tool" -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add sebastian/capabilities/tools/memory_search/__init__.py tests/unit/memory/test_memory_search_tool.py
git commit -m "fix(memory): memory_search 工具严格区分 current truth 与历史证据"
```

---

### Task 5: Assembler 标题对齐 spec 措辞（GAP #13）

**Files:**
- Modify: `sebastian/memory/retrieval.py:125-143`
- Test: `tests/unit/memory/test_retrieval.py`

**背景：** spec `retrieval.md §6` 规定 4 段装配的命名为 `What I know about the user` / `Relevant current context` / `Relevant past episodes` / `Important relationships`。当前实现用 `Current facts about user` / `Current context` / `Historical evidence (may be outdated)`，语义等价但字面不同。对齐原文避免未来 prompt 调优基于错误命名。

- [ ] **Step 1: 补一个会失败的测试**

```python
def test_assemble_section_titles_match_spec_wording(self) -> None:
    """Assembler 输出段标题必须匹配 spec retrieval.md §6 原文。"""
    from sebastian.memory.retrieval import MemorySectionAssembler, RetrievalPlan

    class FakeRec:
        def __init__(self, kind: str, content: str) -> None:
            self.kind = kind
            self.content = content
            self.status = "active"
            self.confidence = 0.9
            self.policy_tags: list[str] = []
            self.valid_from = None
            self.valid_until = None
            self.subject_id = "owner"
            self.source_entity_id = None
            self.target_entity_id = None
            self.predicate = "related_to"

    assembler = MemorySectionAssembler()
    out = assembler.assemble(
        profile_records=[FakeRec("fact", "likes tea")],
        context_records=[FakeRec("fact", "working on X")],
        episode_records=[FakeRec("episode", "discussed Y")],
        relation_records=[FakeRec("relation", "alice related_to bob")],
        plan=RetrievalPlan(
            profile_lane=True,
            context_lane=True,
            episode_lane=True,
            relation_lane=True,
        ),
    )
    assert "## What I know about the user" in out
    assert "## Relevant current context" in out
    assert "## Relevant past episodes" in out
    assert "## Important relationships" in out
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler::test_assemble_section_titles_match_spec_wording -v
```

Expected: FAIL。

- [ ] **Step 3: 修改段标题**

`sebastian/memory/retrieval.py:125-143`：

```python
        if profiles:
            lines = "\n".join(f"- [{r.kind}] {r.content}" for r in profiles)
            sections.append(f"## What I know about the user\n{lines}")

        if contexts:
            lines = "\n".join(f"- {r.content}" for r in contexts)
            sections.append(f"## Relevant current context\n{lines}")

        if relations:
            lines = "\n".join(f"- {_render_relation(r)}" for r in relations)
            sections.append(f"## Important relationships\n{lines}")

        if episodes:
            lines = "\n".join(f"- {r.content}" for r in episodes)
            sections.append(f"## Relevant past episodes\n{lines}")
```

- [ ] **Step 4: 更新旧测试中对老标题的断言**

Grep 现有测试中出现的旧标题：

```bash
rg -n "Current facts about user|Current context|Historical evidence" tests/
```

将断言替换为新标题，否则其他测试会红。

- [ ] **Step 5: 运行全量 retrieval 测试**

```bash
pytest tests/unit/memory/test_retrieval.py -v
```

Expected: 全 PASS。

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/retrieval.py tests/unit/memory/test_retrieval.py
git commit -m "fix(memory): Assembler 段标题对齐 spec retrieval §6 原文"
```

---

### Task 6: Episode Lane 先 summary 再下钻 episode（GAP #2 🔴）

**Files:**
- Modify: `sebastian/memory/retrieval.py:164-219`
- Test: `tests/unit/memory/test_retrieval.py`

**背景：** spec `retrieval.md §4.3` 明确 Episode Lane 策略："默认先查 summary，需要细节时再下钻原始 episode"。当前 `retrieve_memory_section` 直接对 episode_memories_fts 混查 summary+episode，违反 spec 并浪费 token。

- [ ] **Step 1: 补 EpisodeMemoryStore.search_episodes_only 方法的失败测试**

在 `tests/unit/memory/test_episode_store.py` 追加（文件不存在则新建）：

```python
import pytest
from sebastian.memory.episode_store import EpisodeMemoryStore
from sebastian.memory.types import (
    MemoryArtifact,
    MemoryKind,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)
from datetime import UTC, datetime


@pytest.mark.asyncio
async def test_search_episodes_only_excludes_summaries(db_session) -> None:
    store = EpisodeMemoryStore(db_session)
    now = datetime.now(UTC)

    def _make(mid: str, kind: MemoryKind, content: str) -> MemoryArtifact:
        return MemoryArtifact(
            id=mid,
            kind=kind,
            scope=MemoryScope.USER,
            subject_id="owner",
            slot_id=None,
            cardinality=None,
            resolution_policy=None,
            content=content,
            structured_payload={},
            source=MemorySource.EXPLICIT,
            confidence=0.9,
            status=MemoryStatus.ACTIVE,
            valid_from=None,
            valid_until=None,
            recorded_at=now,
            last_accessed_at=None,
            access_count=0,
            provenance={},
            links=[],
            embedding_ref=None,
            dedupe_key=None,
            policy_tags=[],
        )

    await store.add_episode(_make("e1", MemoryKind.EPISODE, "讨论 东京 行程"))
    await store.add_summary(_make("s1", MemoryKind.SUMMARY, "东京 游记 摘要"))
    await db_session.commit()

    eps = await store.search_episodes_only(
        subject_id="owner", query="东京", limit=5
    )
    kinds = {r.kind for r in eps}
    assert "episode" in kinds
    assert "summary" not in kinds
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_episode_store.py::test_search_episodes_only_excludes_summaries -v
```

Expected: FAIL（方法不存在）。

- [ ] **Step 3: 在 EpisodeMemoryStore 增加 `search_episodes_only`**

`sebastian/memory/episode_store.py` 在 `search` 方法下方新增：

```python
    async def search_episodes_only(
        self,
        *,
        subject_id: str,
        query: str,
        limit: int = 8,
    ) -> list[EpisodeMemoryRecord]:
        """Same as :meth:`search` but excludes SUMMARY-kind records.

        Used by Episode Lane's detail-drill-down path.
        """
        records = await self.search(subject_id=subject_id, query=query, limit=limit * 2)
        filtered = [r for r in records if r.kind != MemoryKind.SUMMARY.value]
        return filtered[:limit]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_episode_store.py::test_search_episodes_only_excludes_summaries -v
```

Expected: PASS。

- [ ] **Step 5: 补 retrieve_memory_section 两段式集成测试**

在 `tests/unit/memory/test_retrieval.py` 追加：

```python
@pytest.mark.asyncio
async def test_episode_lane_prefers_summary_then_episodes(db_session) -> None:
    """Episode Lane 优先返回 summary，summary 不足时下钻 episode。"""
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.retrieval import RetrievalContext, retrieve_memory_section

    store = EpisodeMemoryStore(db_session)
    now = datetime.now(UTC)

    def _mk(mid: str, kind: MemoryKind, content: str) -> MemoryArtifact:
        return MemoryArtifact(
            id=mid, kind=kind, scope=MemoryScope.USER, subject_id="owner",
            slot_id=None, cardinality=None, resolution_policy=None,
            content=content, structured_payload={}, source=MemorySource.EXPLICIT,
            confidence=0.9, status=MemoryStatus.ACTIVE,
            valid_from=None, valid_until=None, recorded_at=now,
            last_accessed_at=None, access_count=0, provenance={}, links=[],
            embedding_ref=None, dedupe_key=None, policy_tags=[],
        )

    # 3 个 summary + 3 个 episode，limit=3 时应只返回 3 个 summary
    for i in range(3):
        await store.add_summary(_mk(f"s{i}", MemoryKind.SUMMARY, f"东京 摘要 {i}"))
    for i in range(3):
        await store.add_episode(_mk(f"e{i}", MemoryKind.EPISODE, f"讨论 东京 详情 {i}"))
    await db_session.commit()

    ctx = RetrievalContext(
        subject_id="owner", session_id="sX", agent_type="t",
        user_message="上次 我们 讨论 东京 什么",
    )
    out = await retrieve_memory_section(ctx, db_session=db_session)
    # 当 summary 足够时不应出现 episode 详情
    assert "摘要" in out
    assert "详情" not in out
```

- [ ] **Step 6: 改造 retrieve_memory_section 中的 Episode Lane**

修改 `sebastian/memory/retrieval.py:193-199`：

```python
    episode_records: list[Any] = []
    if plan.episode_lane:
        # spec retrieval.md §4.3: 先查 summary，不足时下钻 episode
        summary_records = await episode_store.search_summaries(
            subject_id=context.subject_id,
            limit=plan.episode_limit,
        )
        if len(summary_records) >= plan.episode_limit:
            episode_records = summary_records
        else:
            remaining = plan.episode_limit - len(summary_records)
            detail_records = await episode_store.search_episodes_only(
                subject_id=context.subject_id,
                query=context.user_message,
                limit=remaining,
            )
            episode_records = [*summary_records, *detail_records]
```

> **注意：** `search_summaries` 已存在（episode_store.py:107）。仅未被 retrieval 复用。

- [ ] **Step 7: 运行集成测试确认通过**

```bash
pytest tests/unit/memory/test_retrieval.py::test_episode_lane_prefers_summary_then_episodes -v
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add sebastian/memory/retrieval.py sebastian/memory/episode_store.py tests/unit/memory/
git commit -m "fix(memory): Episode Lane 先 summary 再下钻 episode 满足 spec §4.3"
```

---

### Task 7: decision_log 增加 `input_source` 字段（GAP #12）

**Files:**
- Modify: `sebastian/store/models.py:198-215`（表结构）
- Modify: `sebastian/memory/decision_log.py:18-52`（Logger 接口）
- Modify: `sebastian/memory/consolidation.py`（Worker 传入来源）
- Modify: `sebastian/memory/types.py`（ResolveDecision 可选 input_source）
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py`（传入来源）
- Test: `tests/unit/memory/test_decision_log.py`

**背景：** spec `storage.md §6` 列出 9 项必需记录，第一项是"原始输入来源"。当前 decision_log 仅以 `candidate.evidence` 间接承载，不是独立字段，检索/审计麻烦。

- [ ] **Step 1: 补表结构测试的失败用例**

在 `tests/unit/memory/test_decision_log.py` 追加：

```python
@pytest.mark.asyncio
async def test_decision_log_persists_input_source(db_session) -> None:
    """decision_log 必须把 input_source 独立字段持久化。"""
    from sebastian.memory.decision_log import MemoryDecisionLogger
    from sebastian.memory.types import (
        CandidateArtifact, MemoryDecisionType, MemoryKind,
        MemoryScope, MemorySource, ResolveDecision,
    )
    from sqlalchemy import select
    from sebastian.store.models import MemoryDecisionLogRecord

    candidate = CandidateArtifact(
        kind=MemoryKind.FACT, content="test", structured_payload={},
        subject_hint=None, scope=MemoryScope.USER, slot_id=None,
        cardinality=None, resolution_policy=None, confidence=0.9,
        source=MemorySource.EXPLICIT, evidence=[], valid_from=None,
        valid_until=None, policy_tags=[], needs_review=False,
    )
    decision = ResolveDecision(
        decision=MemoryDecisionType.DISCARD, reason="test",
        old_memory_ids=[], new_memory=None, candidate=candidate,
        subject_id="owner", scope=MemoryScope.USER, slot_id=None,
    )
    logger = MemoryDecisionLogger(db_session)
    await logger.append(
        decision, worker="w1", model="m1", rule_version="v1",
        input_source={"type": "memory_save_tool", "session_id": "s1"},
    )
    await db_session.commit()
    rows = (await db_session.scalars(select(MemoryDecisionLogRecord))).all()
    assert len(rows) == 1
    assert rows[0].input_source == {"type": "memory_save_tool", "session_id": "s1"}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_decision_log.py::test_decision_log_persists_input_source -v
```

Expected: FAIL（列不存在）。

- [ ] **Step 3: 增加 `input_source` 列**

修改 `sebastian/store/models.py:198-215`：

```python
class MemoryDecisionLogRecord(Base):
    __tablename__ = "memory_decision_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    decision: Mapped[str] = mapped_column(String, index=True)
    subject_id: Mapped[str] = mapped_column(String, index=True)
    scope: Mapped[str] = mapped_column(String, index=True)
    slot_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    input_source: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    candidate: Mapped[dict[str, Any]] = mapped_column(JSON)
    conflicts: Mapped[list[str]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String)
    old_memory_ids: Mapped[list[str]] = mapped_column(JSON)
    new_memory_id: Mapped[str | None] = mapped_column(String, nullable=True)
    worker: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    rule_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
```

- [ ] **Step 4: 扩展 Logger API**

修改 `sebastian/memory/decision_log.py:18-52`：

```python
    async def append(
        self,
        decision: ResolveDecision,
        *,
        worker: str,
        model: str | None,
        rule_version: str,
        input_source: dict[str, Any] | None = None,
    ) -> MemoryDecisionLogRecord:
        session_id: str | None = None
        if decision.new_memory is not None:
            provenance = decision.new_memory.provenance or {}
            session_id_val = provenance.get("session_id")
            if isinstance(session_id_val, str):
                session_id = session_id_val
        if session_id is None and isinstance(input_source, dict):
            sid = input_source.get("session_id")
            if isinstance(sid, str):
                session_id = sid

        record = MemoryDecisionLogRecord(
            id=str(uuid4()),
            decision=decision.decision.value,
            subject_id=decision.subject_id,
            scope=decision.scope.value,
            slot_id=decision.slot_id,
            input_source=input_source,
            candidate=decision.candidate.model_dump(mode="json"),
            conflicts=list(decision.old_memory_ids),
            reason=decision.reason,
            old_memory_ids=list(decision.old_memory_ids),
            new_memory_id=decision.new_memory.id if decision.new_memory is not None else None,
            worker=worker,
            model=model,
            session_id=session_id,
            rule_version=rule_version,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        await self._session.flush()
        return record
```

- [ ] **Step 5: 迁移既有调用点**

```bash
rg -n "decision_logger.append\|decision_logger\\.append\|MemoryDecisionLogger" sebastian/
```

在 `consolidation.py` 的调用点显式传 `input_source={"type": "session_consolidation", "session_id": session_id, "agent_type": agent_type}`；`memory_save` 工具调用处传 `{"type": "memory_save_tool", "session_id": ...}`。

- [ ] **Step 6: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_decision_log.py -v
pytest tests/unit/memory/test_consolidation.py -v
```

Expected: PASS。

- [ ] **Step 7: 更新 CHANGELOG [Unreleased] Added 段**

在 `CHANGELOG.md` 的 `## [Unreleased]` → `### Added` 下追加：

```
- `memory_decision_log` 新增 `input_source` 字段记录原始输入来源，满足 spec storage §6 审计要求
```

- [ ] **Step 8: 提交**

```bash
git add sebastian/store/models.py sebastian/memory/decision_log.py sebastian/memory/consolidation.py sebastian/capabilities/tools/memory_save/ tests/unit/memory/ CHANGELOG.md
git commit -m "feat(memory): decision_log 增加 input_source 字段满足 spec §6 审计"
```

---

## Phase 2: Resolver/Policy 默认策略补齐（Task 8–9）

本阶段修复 artifact-model §10 默认策略表未落实的两条：summary 替换策略、relation(exclusive) 时间边界覆盖。

---

### Task 8: Resolver 对 summary 实现默认替换（GAP #5）

**Files:**
- Modify: `sebastian/memory/resolver.py:82-92`
- Modify: `sebastian/memory/episode_store.py`（增加 supersede_summary 能力）
- Modify: `sebastian/memory/write_router.py:43-45`
- Test: `tests/unit/memory/test_resolver.py`
- Test: `tests/unit/memory/test_episode_store.py`

**背景：** spec `artifact-model.md §10` 要求 summary "可替代默认摘要，但保留历史摘要"。当前 resolver 对 summary 一律 ADD，新 summary 不会 supersede 旧默认 summary，导致同一 subject 的默认摘要会无限增长。

**设计：** 引入"默认摘要"概念 = 同 subject + scope 且 `structured_payload.summary_kind == "default"` 的最近一条 active summary。新 default summary 写入时 supersede 旧 default summary，显式打标的阶段性摘要（例如 `summary_kind == "stage"`）走 append。

- [ ] **Step 1: 补 resolver 失败测试**

在 `tests/unit/memory/test_resolver.py` 追加：

```python
@pytest.mark.asyncio
async def test_resolver_supersedes_default_summary(db_session) -> None:
    """新的 default summary 应 SUPERSEDE 已有 default summary。"""
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.memory.resolver import resolve_candidate
    from sebastian.memory.slots import DEFAULT_SLOT_REGISTRY
    from sebastian.memory.types import (
        CandidateArtifact, MemoryArtifact, MemoryDecisionType, MemoryKind,
        MemoryScope, MemorySource, MemoryStatus,
    )
    from datetime import UTC, datetime

    # 预置一条旧 default summary
    old = MemoryArtifact(
        id="old-sum", kind=MemoryKind.SUMMARY, scope=MemoryScope.USER,
        subject_id="owner", slot_id=None, cardinality=None,
        resolution_policy=None, content="旧摘要",
        structured_payload={"summary_kind": "default"},
        source=MemorySource.SYSTEM_DERIVED, confidence=0.8,
        status=MemoryStatus.ACTIVE, valid_from=None, valid_until=None,
        recorded_at=datetime.now(UTC), last_accessed_at=None, access_count=0,
        provenance={}, links=[], embedding_ref=None, dedupe_key=None, policy_tags=[],
    )
    episode_store = EpisodeMemoryStore(db_session)
    await episode_store.add_summary(old)
    await db_session.commit()

    new = CandidateArtifact(
        kind=MemoryKind.SUMMARY, content="新摘要",
        structured_payload={"summary_kind": "default"},
        subject_hint=None, scope=MemoryScope.USER, slot_id=None,
        cardinality=None, resolution_policy=None, confidence=0.8,
        source=MemorySource.SYSTEM_DERIVED, evidence=[],
        valid_from=None, valid_until=None, policy_tags=[], needs_review=False,
    )
    decision = await resolve_candidate(
        new, subject_id="owner",
        profile_store=ProfileMemoryStore(db_session),
        slot_registry=DEFAULT_SLOT_REGISTRY,
        episode_store=episode_store,
    )
    assert decision.decision == MemoryDecisionType.SUPERSEDE
    assert "old-sum" in decision.old_memory_ids


@pytest.mark.asyncio
async def test_resolver_stage_summary_is_appended(db_session) -> None:
    """非 default（如 stage）summary 永远 ADD，不 supersede。"""
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.memory.resolver import resolve_candidate
    from sebastian.memory.slots import DEFAULT_SLOT_REGISTRY
    from sebastian.memory.types import (
        CandidateArtifact, MemoryDecisionType, MemoryKind, MemoryScope, MemorySource,
    )

    candidate = CandidateArtifact(
        kind=MemoryKind.SUMMARY, content="阶段摘要",
        structured_payload={"summary_kind": "stage"},
        subject_hint=None, scope=MemoryScope.USER, slot_id=None,
        cardinality=None, resolution_policy=None, confidence=0.8,
        source=MemorySource.SYSTEM_DERIVED, evidence=[],
        valid_from=None, valid_until=None, policy_tags=[], needs_review=False,
    )
    decision = await resolve_candidate(
        candidate, subject_id="owner",
        profile_store=ProfileMemoryStore(db_session),
        slot_registry=DEFAULT_SLOT_REGISTRY,
        episode_store=EpisodeMemoryStore(db_session),
    )
    assert decision.decision == MemoryDecisionType.ADD
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_resolver.py -k "default_summary or stage_summary" -v
```

Expected: FAIL（`resolve_candidate` 签名无 episode_store 参数；逻辑未实现）。

- [ ] **Step 3: 为 EpisodeMemoryStore 增加 default summary 查询**

在 `sebastian/memory/episode_store.py` 增加：

```python
    async def get_active_default_summaries(
        self,
        *,
        subject_id: str,
        scope: str,
    ) -> list[EpisodeMemoryRecord]:
        """Return active summary records whose payload marks them as default."""
        statement = select(EpisodeMemoryRecord).where(
            EpisodeMemoryRecord.subject_id == subject_id,
            EpisodeMemoryRecord.scope == scope,
            EpisodeMemoryRecord.kind == MemoryKind.SUMMARY.value,
            EpisodeMemoryRecord.status == MemoryStatus.ACTIVE.value,
        )
        result = await self._session.scalars(statement)
        rows = list(result.all())
        return [
            r for r in rows
            if isinstance(r.structured_payload, dict)
            and r.structured_payload.get("summary_kind") == "default"
        ]

    async def supersede(
        self, old_ids: list[str], artifact: MemoryArtifact
    ) -> EpisodeMemoryRecord:
        """Mark old summaries as superseded and insert the new one."""
        now = datetime.now(UTC)
        if old_ids:
            await self._session.execute(
                update(EpisodeMemoryRecord)
                .where(EpisodeMemoryRecord.id.in_(old_ids))
                .values(status=MemoryStatus.SUPERSEDED.value, last_accessed_at=now)
            )
        return await self.add_summary(artifact)
```

- [ ] **Step 4: 更新 resolve_candidate 签名与逻辑**

修改 `sebastian/memory/resolver.py`：

```python
async def resolve_candidate(
    candidate: CandidateArtifact,
    *,
    subject_id: str,
    profile_store: ProfileMemoryStore,
    slot_registry: SlotRegistry,
    episode_store: EpisodeMemoryStore | None = None,
) -> ResolveDecision:
    # ... 原逻辑前半部分不变 ...

    # ----- 1. Episode → always ADD -----
    if candidate.kind == MemoryKind.EPISODE:
        return ResolveDecision(
            decision=MemoryDecisionType.ADD,
            reason="episodes are always appended",
            old_memory_ids=[],
            new_memory=_make_artifact(candidate, subject_id),
            candidate=candidate, subject_id=subject_id,
            scope=candidate.scope, slot_id=None,
        )

    # ----- 1b. Summary: default supersedes, others append -----
    if candidate.kind == MemoryKind.SUMMARY:
        summary_kind = (candidate.structured_payload or {}).get("summary_kind")
        if summary_kind == "default" and episode_store is not None:
            existing = await episode_store.get_active_default_summaries(
                subject_id=subject_id,
                scope=candidate.scope.value,
            )
            if existing:
                return ResolveDecision(
                    decision=MemoryDecisionType.SUPERSEDE,
                    reason=(
                        f"default summary replaces {len(existing)} "
                        f"existing default summary record(s)"
                    ),
                    old_memory_ids=[r.id for r in existing],
                    new_memory=_make_artifact(candidate, subject_id),
                    candidate=candidate, subject_id=subject_id,
                    scope=candidate.scope, slot_id=None,
                )
        return ResolveDecision(
            decision=MemoryDecisionType.ADD,
            reason="summary append (non-default or no existing default)",
            old_memory_ids=[],
            new_memory=_make_artifact(candidate, subject_id),
            candidate=candidate, subject_id=subject_id,
            scope=candidate.scope, slot_id=None,
        )

    # ... 其余 fact/preference 逻辑保持不变 ...
```

同时更新 `sebastian/memory/consolidation.py` 中调用 `resolve_candidate` 处，传入 `episode_store=episode_store`；`sebastian/capabilities/tools/memory_save/__init__.py` 同理。

- [ ] **Step 5: write_router 对 SUPERSEDE 的 summary 路由到 episode_store.supersede**

修改 `sebastian/memory/write_router.py:43-45`：

```python
    if kind == MemoryKind.SUMMARY:
        if decision.decision == MemoryDecisionType.SUPERSEDE:
            await episode_store.supersede(decision.old_memory_ids, artifact)
        else:
            await episode_store.add_summary(artifact)
        return
```

- [ ] **Step 6: 运行测试**

```bash
pytest tests/unit/memory/test_resolver.py tests/unit/memory/test_episode_store.py tests/unit/memory/test_write_router.py tests/unit/memory/test_consolidation.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add sebastian/memory/resolver.py sebastian/memory/episode_store.py sebastian/memory/write_router.py sebastian/memory/consolidation.py sebastian/capabilities/tools/memory_save/ tests/unit/memory/
git commit -m "feat(memory): summary 默认替换策略满足 spec §10 默认策略表"
```

---

### Task 9: relation(exclusive) 时间边界覆盖（GAP #6）

**Files:**
- Modify: `sebastian/memory/write_router.py:55-77`
- Modify: `sebastian/memory/entity_registry.py`（增加 close_exclusive_relations）
- Test: `tests/unit/memory/test_write_router.py`

**背景：** spec `artifact-model.md §10` 规定 `relation(exclusive)` 走 `time_bound` 策略：新关系写入时，旧关系不做 SUPERSEDE，而是设置 `valid_until = new.valid_from`，保留历史轨迹。当前 write_router 直接追加到 relation_candidates，旧记录无变化。

**判定 exclusive：** 关系 `structured_payload.exclusive == True` 或 `resolution_policy == "time_bound"`。

- [ ] **Step 1: 补失败测试**

`tests/unit/memory/test_write_router.py` 追加：

```python
@pytest.mark.asyncio
async def test_write_router_closes_existing_exclusive_relation(db_session) -> None:
    """写入新的 exclusive relation 时，旧同 predicate relation 应被设置 valid_until。"""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from sebastian.memory.entity_registry import EntityRegistry
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.memory.types import (
        MemoryArtifact, MemoryDecisionType, MemoryKind, MemoryScope,
        MemorySource, MemoryStatus, ResolveDecision, CandidateArtifact,
    )
    from sebastian.memory.write_router import persist_decision
    from sebastian.store.models import RelationCandidateRecord

    t0 = datetime.now(UTC) - timedelta(days=10)
    t1 = datetime.now(UTC)

    old_art = MemoryArtifact(
        id="rel-old", kind=MemoryKind.RELATION, scope=MemoryScope.USER,
        subject_id="owner", slot_id=None, cardinality=None,
        resolution_policy=None, content="owner works_at companyA",
        structured_payload={
            "predicate": "works_at", "source_entity_id": "owner",
            "target_entity_id": "companyA", "exclusive": True,
        },
        source=MemorySource.EXPLICIT, confidence=0.9,
        status=MemoryStatus.ACTIVE, valid_from=t0, valid_until=None,
        recorded_at=t0, last_accessed_at=None, access_count=0,
        provenance={}, links=[], embedding_ref=None, dedupe_key=None,
        policy_tags=[],
    )
    candidate = CandidateArtifact(
        kind=MemoryKind.RELATION, content="old",
        structured_payload=old_art.structured_payload,
        subject_hint=None, scope=MemoryScope.USER, slot_id=None,
        cardinality=None, resolution_policy=None, confidence=0.9,
        source=MemorySource.EXPLICIT, evidence=[], valid_from=t0,
        valid_until=None, policy_tags=[], needs_review=False,
    )
    old_decision = ResolveDecision(
        decision=MemoryDecisionType.ADD, reason="initial", old_memory_ids=[],
        new_memory=old_art, candidate=candidate, subject_id="owner",
        scope=MemoryScope.USER, slot_id=None,
    )
    await persist_decision(
        old_decision, session=db_session,
        profile_store=ProfileMemoryStore(db_session),
        episode_store=EpisodeMemoryStore(db_session),
        entity_registry=EntityRegistry(db_session),
    )
    await db_session.commit()

    new_art = old_art.model_copy(update={
        "id": "rel-new", "content": "owner works_at companyB",
        "structured_payload": {
            "predicate": "works_at", "source_entity_id": "owner",
            "target_entity_id": "companyB", "exclusive": True,
        },
        "valid_from": t1, "recorded_at": t1,
    })
    new_decision = old_decision.model_copy(update={
        "new_memory": new_art, "candidate": candidate.model_copy(update={
            "structured_payload": new_art.structured_payload,
            "valid_from": t1,
        }),
    })
    await persist_decision(
        new_decision, session=db_session,
        profile_store=ProfileMemoryStore(db_session),
        episode_store=EpisodeMemoryStore(db_session),
        entity_registry=EntityRegistry(db_session),
    )
    await db_session.commit()

    rows = (
        await db_session.scalars(select(RelationCandidateRecord))
    ).all()
    by_id = {r.id: r for r in rows}
    assert by_id["rel-old"].valid_until == t1
    assert by_id["rel-new"].valid_until is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_write_router.py::test_write_router_closes_existing_exclusive_relation -v
```

Expected: FAIL。

- [ ] **Step 3: EntityRegistry 增加 close_exclusive_relations**

在 `sebastian/memory/entity_registry.py` 增加：

```python
    async def close_exclusive_relations(
        self,
        *,
        subject_id: str,
        predicate: str,
        source_entity_id: str | None,
        valid_until: datetime,
    ) -> list[str]:
        """Close active exclusive relations sharing (subject, predicate, source).

        Sets ``valid_until`` for each matching row and returns their IDs so the
        caller can log decisions.
        """
        from sqlalchemy import select, update
        from sebastian.store.models import RelationCandidateRecord

        statement = select(RelationCandidateRecord).where(
            RelationCandidateRecord.subject_id == subject_id,
            RelationCandidateRecord.predicate == predicate,
            RelationCandidateRecord.source_entity_id == source_entity_id,
            RelationCandidateRecord.valid_until.is_(None),
            RelationCandidateRecord.status == "active",
        )
        rows = (await self._session.scalars(statement)).all()
        ids = [r.id for r in rows
               if isinstance(r.structured_payload, dict)
               and r.structured_payload.get("exclusive") is True]
        if not ids:
            return []
        await self._session.execute(
            update(RelationCandidateRecord)
            .where(RelationCandidateRecord.id.in_(ids))
            .values(valid_until=valid_until)
        )
        await self._session.flush()
        return ids
```

- [ ] **Step 4: write_router 写 relation 时调用 close_exclusive_relations**

修改 `sebastian/memory/write_router.py:55-77`：

```python
    if kind == MemoryKind.RELATION:
        from sebastian.store.models import RelationCandidateRecord

        payload = artifact.structured_payload or {}
        is_exclusive = bool(payload.get("exclusive"))
        if is_exclusive and artifact.valid_from is not None:
            await entity_registry.close_exclusive_relations(
                subject_id=artifact.subject_id,
                predicate=payload.get("predicate", ""),
                source_entity_id=payload.get("source_entity_id"),
                valid_until=artifact.valid_from,
            )

        session.add(
            RelationCandidateRecord(
                id=artifact.id or str(uuid4()),
                subject_id=artifact.subject_id,
                predicate=payload.get("predicate", ""),
                source_entity_id=payload.get("source_entity_id"),
                target_entity_id=payload.get("target_entity_id"),
                content=artifact.content,
                structured_payload=payload,
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
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/unit/memory/test_write_router.py tests/unit/memory/test_entity_registry.py -v
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/write_router.py sebastian/memory/entity_registry.py tests/unit/memory/
git commit -m "feat(memory): relation(exclusive) 时间边界覆盖满足 spec §10 默认策略"
```

---

## Phase 3: BaseAgent Hook 拆分（Task 11–12）

spec `overview.md §5.3` 要求 BaseAgent 至少暴露四个 hook：(1) turn 入口 retrieval planner；(2) prompt 组装 assembler；(3) session 转 idle 的 consolidation scheduler；(4) memory_* 工具入口。当前 planner + assembler 混在 `_memory_section` 一次调用，且 consolidation 完全依赖外部 EventBus。本阶段把 hook 语义拆清楚，便于未来扩展（例如用 planner 输出影响工具选择）。

---

### Task 11: 拆分 planner / assembler 为两个独立 hook（GAP #9a）

**Files:**
- Modify: `sebastian/memory/retrieval.py`（拆 `retrieve_memory_section` 为 `plan_memory_retrieval` + `fetch_and_assemble`）
- Modify: `sebastian/core/base_agent.py:236-275`（拆 `_memory_plan` + `_memory_section`）
- Test: `tests/unit/core/test_base_agent_memory.py`
- Test: `tests/unit/memory/test_retrieval.py`

**设计：**
- `plan_memory_retrieval(context) -> RetrievalPlan`：同步决定哪些 lane 启用、预算多少。不访问 DB，不调用 LLM。
- `fetch_and_assemble(context, plan, *, db_session) -> str`：按 plan 查 DB + Assembler 拼装。
- `retrieve_memory_section` 保留为两者的 thin wrapper，向后兼容。
- BaseAgent 在 turn 入口（`_stream_inner` 开始处）调用 `_memory_plan`，把 `RetrievalPlan` 存在 run-local 变量，随后在 `build_system_prompt` → `_memory_section` 消费该 plan。

- [ ] **Step 1: 补 retrieval.py 拆分后的失败测试**

在 `tests/unit/memory/test_retrieval.py` 追加：

```python
def test_plan_memory_retrieval_is_pure_and_db_free() -> None:
    """plan_memory_retrieval 不能访问 DB；纯计算。"""
    from sebastian.memory.retrieval import plan_memory_retrieval, RetrievalContext

    ctx = RetrievalContext(
        subject_id="owner", session_id="s1",
        agent_type="orchestrator", user_message="我 最近 在 忙 什么",
    )
    plan = plan_memory_retrieval(ctx)
    assert plan.profile_lane is True
    assert plan.context_lane is True


@pytest.mark.asyncio
async def test_fetch_and_assemble_uses_precomputed_plan(db_session) -> None:
    """fetch_and_assemble 接受外部 plan，不再自行 plan。"""
    from sebastian.memory.retrieval import (
        RetrievalContext, RetrievalPlan, fetch_and_assemble,
    )

    ctx = RetrievalContext(
        subject_id="owner", session_id="s1",
        agent_type="orchestrator", user_message="任意",
    )
    # 显式关闭 profile lane，即使输入触发它也不该启用
    plan = RetrievalPlan(profile_lane=False, context_lane=False,
                        episode_lane=False, relation_lane=False)
    out = await fetch_and_assemble(ctx, plan, db_session=db_session)
    assert out == ""
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/memory/test_retrieval.py -k "plan_memory_retrieval or fetch_and_assemble" -v
```

Expected: FAIL（函数不存在）。

- [ ] **Step 3: retrieval.py 拆分**

`sebastian/memory/retrieval.py` 在文件底部改写：

```python
def plan_memory_retrieval(context: RetrievalContext) -> RetrievalPlan:
    """Pure planner: decide lanes and budgets based on user_message intent.

    This is the "turn-entry retrieval planner" hook per spec overview §5.3.
    Safe to call outside of any DB session.
    """
    return MemoryRetrievalPlanner().plan(context)


async def fetch_and_assemble(
    context: RetrievalContext,
    plan: RetrievalPlan,
    *,
    db_session: AsyncSession,
) -> str:
    """Fetch lane results per *plan* and assemble the final memory section.

    This is the "system-prompt assembler" hook per spec overview §5.3.
    Accepts an externally computed plan so callers can split the planning
    step (turn entry) from the fetching/assembly step (prompt build).
    """
    from sebastian.memory.episode_store import EpisodeMemoryStore
    from sebastian.memory.profile_store import ProfileMemoryStore

    profile_store = ProfileMemoryStore(db_session)
    episode_store = EpisodeMemoryStore(db_session)

    profile_records: list[Any] = []
    if plan.profile_lane:
        profile_records = await profile_store.search_active(
            subject_id=context.subject_id, limit=plan.profile_limit,
        )

    context_records: list[Any] = []
    if plan.context_lane:
        context_records = await profile_store.search_recent_context(
            subject_id=context.subject_id, limit=plan.context_limit,
        )

    episode_records: list[Any] = []
    if plan.episode_lane:
        summary_records = await episode_store.search_summaries(
            subject_id=context.subject_id, limit=plan.episode_limit,
        )
        if len(summary_records) >= plan.episode_limit:
            episode_records = summary_records
        else:
            remaining = plan.episode_limit - len(summary_records)
            detail_records = await episode_store.search_episodes_only(
                subject_id=context.subject_id,
                query=context.user_message,
                limit=remaining,
            )
            episode_records = [*summary_records, *detail_records]

    relation_records: list[Any] = []
    if plan.relation_lane:
        from sebastian.memory.entity_registry import EntityRegistry
        relation_records = await EntityRegistry(db_session).list_relations(
            subject_id=context.subject_id, limit=plan.relation_limit,
        )

    return MemorySectionAssembler().assemble(
        profile_records=profile_records,
        context_records=context_records,
        episode_records=episode_records,
        relation_records=relation_records,
        plan=plan,
        context=context,
    )


async def retrieve_memory_section(
    context: RetrievalContext,
    *,
    db_session: AsyncSession,
) -> str:
    """Backwards-compatible convenience wrapper: plan + fetch + assemble."""
    plan = plan_memory_retrieval(context)
    return await fetch_and_assemble(context, plan, db_session=db_session)
```

> **注意：** 把 Task 6 的 Episode Lane 两段式逻辑合并到 `fetch_and_assemble` 中（上面已包含）。如果 Task 6 已单独实现，这里与其合流。

- [ ] **Step 4: BaseAgent 拆两个 hook**

`sebastian/core/base_agent.py:236-275` 修改为：

```python
    async def _memory_plan(
        self,
        session_id: str,
        agent_context: str,
        user_message: str,
    ) -> tuple[Any, Any] | None:
        """Turn-entry hook: produce a RetrievalPlan for the current turn.

        Returns (context, plan) or None when memory is disabled / unavailable.
        """
        if self._db_factory is None:
            return None
        try:
            import sebastian.gateway.state as state
            if not state.memory_settings.enabled:
                return None
        except (ImportError, AttributeError):
            return None
        from sebastian.memory.retrieval import RetrievalContext, plan_memory_retrieval
        from sebastian.memory.subject import resolve_subject
        from sebastian.memory.types import MemoryScope

        subject_id = await resolve_subject(
            MemoryScope.USER, session_id=session_id, agent_type=agent_context,
        )
        ctx = RetrievalContext(
            subject_id=subject_id, session_id=session_id,
            agent_type=agent_context, user_message=user_message,
        )
        return ctx, plan_memory_retrieval(ctx)

    async def _memory_section(
        self,
        session_id: str,
        agent_context: str,
        user_message: str,
        *,
        precomputed: tuple[Any, Any] | None = None,
    ) -> str:
        """Prompt-build hook: fetch per plan and assemble memory section."""
        if self._db_factory is None:
            return ""
        try:
            if precomputed is None:
                precomputed = await self._memory_plan(
                    session_id, agent_context, user_message
                )
            if precomputed is None:
                return ""
            ctx, plan = precomputed
            from sebastian.memory.retrieval import fetch_and_assemble
            async with self._db_factory() as session:
                return await fetch_and_assemble(ctx, plan, db_session=session)
        except Exception:
            logger.warning(
                "Memory section retrieval failed, continuing without memory context",
                exc_info=True,
            )
            return ""
```

- [ ] **Step 5: 保持既有 `_memory_section(...)` 调用点兼容**

`sebastian/core/base_agent.py:458` 处无需修改——`precomputed=None` 时 `_memory_section` 自动 fallback 走 plan+fetch。后续如需在 turn 入口缓存 plan 供工具选择使用，再独立迭代。

- [ ] **Step 6: 运行 base_agent memory 集成测试**

```bash
pytest tests/unit/core/test_base_agent_memory.py tests/unit/memory/test_retrieval.py -v
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add sebastian/memory/retrieval.py sebastian/core/base_agent.py tests/unit/
git commit -m "refactor(memory): 拆 planner/assembler 为两个独立 hook 满足 spec §5.3"
```

---

### Task 12: BaseAgent session-idle consolidation scheduler hook（GAP #9b）

**Files:**
- Modify: `sebastian/core/base_agent.py`（增加 `_consolidation_hook`）
- Test: `tests/unit/core/test_base_agent_memory.py`

**背景：** spec §5.3 要求 "turn 结束或 session 转 idle 时的 consolidation scheduler"。当前只靠外部 EventBus `SESSION_COMPLETED` 事件，BaseAgent 自身没有显式 hook 点。问题：若某路径忘了发事件，会漏沉淀。

**设计：** BaseAgent 在 `run()` 结束（正常/异常/取消）后调用 `_consolidation_hook(session_id, agent_type)`，默认实现 = 发 `SESSION_COMPLETED` event（与现有调度器合流）。订阅者依旧是 `MemoryConsolidationScheduler`。

> **注意：** 如果现有代码已经在某处（如 gateway/session_store）发布 `SESSION_COMPLETED`，此 hook 与之并行存在是安全的——调度器本身已有 `SessionConsolidationRecord(session_id, agent_type)` 幂等保护（consolidation.py:167-178）。

- [ ] **Step 1: 补失败测试**

在 `tests/unit/core/test_base_agent_memory.py` 追加：

```python
@pytest.mark.asyncio
async def test_base_agent_consolidation_hook_fires_on_run_completion(
    mem_factory,
) -> None:
    """BaseAgent.run 正常结束时应触发 _consolidation_hook。"""
    from unittest.mock import AsyncMock
    from sebastian.core.base_agent import BaseAgent

    agent = _make_test_agent(mem_factory)  # 复用现有 fixture helper
    agent._consolidation_hook = AsyncMock()
    try:
        await agent.run("hi", session_id="s1", agent_name="orchestrator")
    except Exception:
        pass
    agent._consolidation_hook.assert_awaited_once_with("s1", "orchestrator")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/unit/core/test_base_agent_memory.py::test_base_agent_consolidation_hook_fires_on_run_completion -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 `_consolidation_hook`**

在 `sebastian/core/base_agent.py` 加入（位置靠近 `_memory_section`）：

```python
    async def _consolidation_hook(self, session_id: str, agent_type: str) -> None:
        """Session-idle hook: publish SESSION_COMPLETED so consolidation scheduler picks up.

        Per spec overview §5.3 this is an explicit hook on BaseAgent. Default
        implementation delegates to the event bus; the scheduler's
        :class:`SessionConsolidationRecord` guard keeps idempotency even if a
        session is completed more than once.
        """
        if self._event_bus is None:
            return
        try:
            from sebastian.protocol.events.types import Event, EventType
            await self._event_bus.publish(
                Event(
                    type=EventType.SESSION_COMPLETED,
                    data={"session_id": session_id, "agent_type": agent_type},
                )
            )
        except Exception:
            logger.warning(
                "Consolidation hook publish failed", exc_info=True,
            )
```

然后在 `run()` 方法末尾（包含 try/finally）调用：

```python
        finally:
            await self._consolidation_hook(session_id, agent_type=self.agent_type)
```

> **说明：** `agent_type` 按当前实例属性读取；如 BaseAgent 没有 `agent_type` 字段需要改为 `agent_name` 参数值。根据实际类结构调整。

- [ ] **Step 4: 运行测试**

```bash
pytest tests/unit/core/ -v
pytest tests/unit/memory/test_consolidation.py -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add sebastian/core/base_agent.py tests/unit/
git commit -m "feat(core): BaseAgent 新增 session-idle consolidation hook 满足 spec §5.3"
```

---

## Phase 4: 后台 Worker 补齐（Task 13–14）

本阶段新增两个 Phase C 的后台 Worker：`CrossSessionConsolidationWorker` 与 `MemoryMaintenanceWorker`。这两个功能在原 roadmap 标注为 Phase C，当前仅 Session Consolidation 完成。实现范围按 spec §1.2 / §1.3 最小可用子集。

> **范围声明：** Cross-Session 偏好强化与 Maintenance 降权算法都有更深入的设计空间，本阶段只落 MVP：可扩展骨架 + 可验证行为 + 审计日志。若后续产品 pass 发现需要更强语义，再独立 spec 设计迭代。

---

### Task 13: CrossSessionConsolidationWorker MVP（GAP #7）

**Files:**
- Create: `sebastian/memory/cross_session.py`
- Modify: `sebastian/gateway/app.py`（注册定时触发）
- Test: `tests/unit/memory/test_cross_session.py`

**MVP 范围：**
1. **偏好强化**：扫描同 subject + scope + slot 下过去 N=30 天出现 ≥M=3 次但置信度都 < 0.7 的 preference，合并为 1 条高置信（取中位数 confidence + 0.1，上限 1.0）记录，老记录走 SUPERSEDE。
2. **长期主题聚合**：按 `structured_payload.topic` 分组 episode，若同 topic 最近 N 天 ≥3 次出现，生成一条 "default" summary（挂接 Task 8 的默认 summary 策略）。
3. **多来源证据合并**：同 slot 下多条 inferred fact 被显式 fact 覆盖后，显式 fact 的 provenance.evidence 合并 inferred 的原始证据（便于审计）。

**触发方式：** 定时任务（每 6 小时一次），非实时。

- [ ] **Step 1: 写 CrossSessionConsolidationWorker 骨架**

```python
# sebastian/memory/cross_session.py
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sebastian.memory.types import MemoryKind, MemoryScope, MemoryStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CrossSessionConsolidationWorker:
    """Phase C: Aggregate preferences / summaries / evidence across sessions.

    Three jobs per run:
    1. Strengthen preferences with repeated low-confidence occurrences.
    2. Generate default summaries for recurring episode topics.
    3. Merge evidence from superseded inferred facts into their successors.
    """

    _WORKER_ID = "cross_session_consolidation_worker"
    _RULE_VERSION = "phase_c_cross_v1"

    def __init__(
        self,
        *,
        db_factory: async_sessionmaker[AsyncSession],
        memory_settings_fn: Callable[[], bool],
        window_days: int = 30,
        min_occurrences: int = 3,
    ) -> None:
        self._db_factory = db_factory
        self._memory_settings_fn = memory_settings_fn
        self._window_days = window_days
        self._min_occurrences = min_occurrences

    async def run_once(self) -> None:
        if not self._memory_settings_fn():
            return
        async with self._db_factory() as session:
            await self._strengthen_preferences(session)
            await self._aggregate_topic_summaries(session)
            await self._merge_evidence(session)
            await session.commit()

    async def _strengthen_preferences(self, session: AsyncSession) -> None:
        """Promote repeatedly-observed low-confidence preferences to higher confidence."""
        from sebastian.store.models import ProfileMemoryRecord

        cutoff = datetime.now(UTC) - timedelta(days=self._window_days)
        rows = (await session.scalars(
            select(ProfileMemoryRecord).where(
                ProfileMemoryRecord.kind == MemoryKind.PREFERENCE.value,
                ProfileMemoryRecord.status == MemoryStatus.ACTIVE.value,
                ProfileMemoryRecord.created_at >= cutoff,
                ProfileMemoryRecord.confidence < 0.7,
            )
        )).all()
        groups: dict[tuple[str, str, str], list[Any]] = {}
        for r in rows:
            groups.setdefault((r.subject_id, r.scope, r.slot_id), []).append(r)
        for key, members in groups.items():
            if len(members) < self._min_occurrences:
                continue
            # Take the newest content, bump confidence median +0.1
            members.sort(key=lambda r: r.created_at, reverse=True)
            winner = members[0]
            losers = [r for r in members[1:] if r.id != winner.id]
            new_conf = min(1.0, sorted(
                [m.confidence for m in members]
            )[len(members) // 2] + 0.1)
            winner.confidence = new_conf
            for loser in losers:
                loser.status = MemoryStatus.SUPERSEDED.value
            # TODO(phase-c+): emit MemoryDecisionLog entries for audit

    async def _aggregate_topic_summaries(self, session: AsyncSession) -> None:
        """Generate default summary when a topic recurs across sessions."""
        from sebastian.memory.episode_store import EpisodeMemoryStore
        from sebastian.memory.resolver import _make_artifact
        from sebastian.memory.types import (
            CandidateArtifact, MemorySource,
        )
        from sebastian.store.models import EpisodeMemoryRecord

        cutoff = datetime.now(UTC) - timedelta(days=self._window_days)
        rows = (await session.scalars(
            select(EpisodeMemoryRecord).where(
                EpisodeMemoryRecord.kind == MemoryKind.EPISODE.value,
                EpisodeMemoryRecord.status == MemoryStatus.ACTIVE.value,
                EpisodeMemoryRecord.recorded_at >= cutoff,
            )
        )).all()

        topics: dict[tuple[str, str, str], list[Any]] = {}
        for r in rows:
            payload = r.structured_payload or {}
            topic = payload.get("topic")
            if not isinstance(topic, str):
                continue
            topics.setdefault((r.subject_id, r.scope, topic), []).append(r)

        store = EpisodeMemoryStore(session)
        for (subject_id, scope, topic), episodes in topics.items():
            if len(episodes) < self._min_occurrences:
                continue
            content = f"[topic={topic}] 近 {self._window_days} 天内出现 {len(episodes)} 次"
            candidate = CandidateArtifact(
                kind=MemoryKind.SUMMARY,
                content=content,
                structured_payload={"summary_kind": "default", "topic": topic},
                subject_hint=subject_id,
                scope=MemoryScope(scope),
                slot_id=None,
                cardinality=None,
                resolution_policy=None,
                confidence=0.85,
                source=MemorySource.SYSTEM_DERIVED,
                evidence=[{"episode_id": e.id} for e in episodes],
                valid_from=None,
                valid_until=None,
                policy_tags=[],
                needs_review=False,
            )
            artifact = _make_artifact(candidate, subject_id)
            # SUPERSEDE via new default-summary policy (Task 8)
            existing = await store.get_active_default_summaries(
                subject_id=subject_id, scope=scope,
            )
            existing_same_topic = [
                e for e in existing
                if isinstance(e.structured_payload, dict)
                and e.structured_payload.get("topic") == topic
            ]
            if existing_same_topic:
                await store.supersede([e.id for e in existing_same_topic], artifact)
            else:
                await store.add_summary(artifact)

    async def _merge_evidence(self, session: AsyncSession) -> None:
        """Copy evidence from superseded inferred facts into their successors."""
        from sebastian.store.models import MemoryDecisionLogRecord, ProfileMemoryRecord

        # Find SUPERSEDE entries where all superseded originals were inferred
        rows = (await session.scalars(
            select(MemoryDecisionLogRecord).where(
                MemoryDecisionLogRecord.decision == "SUPERSEDE",
            )
        )).all()
        for log in rows:
            if not log.new_memory_id or not log.old_memory_ids:
                continue
            new_row = await session.get(ProfileMemoryRecord, log.new_memory_id)
            if new_row is None:
                continue
            old_rows = (await session.scalars(
                select(ProfileMemoryRecord).where(
                    ProfileMemoryRecord.id.in_(log.old_memory_ids),
                )
            )).all()
            extra: list[Any] = []
            for old in old_rows:
                prov = old.provenance or {}
                extra.extend(prov.get("evidence") or [])
            if not extra:
                continue
            prov = dict(new_row.provenance or {})
            existing_ev = list(prov.get("evidence") or [])
            prov["evidence"] = existing_ev + [
                e for e in extra if e not in existing_ev
            ]
            new_row.provenance = prov
```

- [ ] **Step 2: 写测试**

```python
# tests/unit/memory/test_cross_session.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sebastian.memory.cross_session import CrossSessionConsolidationWorker
from sebastian.memory.types import (
    MemoryArtifact, MemoryKind, MemoryScope, MemorySource, MemoryStatus,
)


def _base_artifact(**overrides: object) -> MemoryArtifact:
    base = dict(
        id="x", kind=MemoryKind.PREFERENCE, scope=MemoryScope.USER,
        subject_id="owner", slot_id="user.preference.response_style",
        cardinality=None, resolution_policy=None, content="preference", structured_payload={},
        source=MemorySource.INFERRED, confidence=0.5, status=MemoryStatus.ACTIVE,
        valid_from=None, valid_until=None,
        recorded_at=datetime.now(UTC), last_accessed_at=None, access_count=0,
        provenance={}, links=[], embedding_ref=None, dedupe_key=None, policy_tags=[],
    )
    base.update(overrides)
    return MemoryArtifact(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cross_session_strengthens_repeated_low_conf_preferences(
    db_factory, memory_enabled_flag_fn,
) -> None:
    """相同 subject+slot 下 ≥3 条低置信 preference 应被强化。"""
    from sebastian.memory.profile_store import ProfileMemoryStore
    from sebastian.store.models import ProfileMemoryRecord
    from sqlalchemy import select

    async with db_factory() as session:
        store = ProfileMemoryStore(session)
        for i in range(3):
            await store.add(_base_artifact(id=f"p{i}", content=f"pref-{i}", confidence=0.5))
        await session.commit()

    worker = CrossSessionConsolidationWorker(
        db_factory=db_factory,
        memory_settings_fn=memory_enabled_flag_fn,
        window_days=30, min_occurrences=3,
    )
    await worker.run_once()

    async with db_factory() as session:
        rows = (await session.scalars(select(ProfileMemoryRecord))).all()
        active = [r for r in rows if r.status == "active"]
        superseded = [r for r in rows if r.status == "superseded"]
        assert len(active) == 1
        assert active[0].confidence > 0.55  # bumped
        assert len(superseded) == 2
```

- [ ] **Step 3: 运行测试确认失败后实现通过**

```bash
pytest tests/unit/memory/test_cross_session.py -v
```

Expected: 初次 FAIL（fixture 或实现细节），调整后 PASS。

- [ ] **Step 4: 在 gateway 注册定时触发**

在 `sebastian/gateway/app.py` 的 lifespan startup（`MemoryConsolidationScheduler` 初始化之后）增加：

```python
    from sebastian.memory.cross_session import CrossSessionConsolidationWorker
    cross_worker = CrossSessionConsolidationWorker(
        db_factory=state.db_factory,
        memory_settings_fn=lambda: state.memory_settings.enabled,
    )
    state.cross_session_task = asyncio.create_task(
        _run_periodic(cross_worker.run_once, interval_seconds=6 * 3600),
        name="cross_session_consolidation",
    )
```

`_run_periodic` 辅助放在同文件或 `sebastian/gateway/periodic.py`：

```python
async def _run_periodic(coro_fn: Callable[[], Awaitable[None]], *, interval_seconds: int) -> None:
    while True:
        try:
            await coro_fn()
        except Exception:
            logger.exception("periodic task failed")
        await asyncio.sleep(interval_seconds)
```

在 shutdown 处 cancel：

```python
    if getattr(state, "cross_session_task", None) is not None:
        state.cross_session_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state.cross_session_task
```

- [ ] **Step 5: 运行相关测试**

```bash
pytest tests/unit/memory/test_cross_session.py tests/integration/ -k gateway -v
```

- [ ] **Step 6: 更新 CHANGELOG**

`### Added`：

```
- 新增 `CrossSessionConsolidationWorker`：每 6 小时一次，做偏好强化、主题 default summary 聚合、跨记忆证据合并，落实 spec consolidation §1.2
```

- [ ] **Step 7: 提交**

```bash
git add sebastian/memory/cross_session.py sebastian/gateway/app.py tests/unit/memory/ CHANGELOG.md
git commit -m "feat(memory): 新增 CrossSessionConsolidationWorker MVP 满足 spec §1.2"
```

---

### Task 14: MemoryMaintenanceWorker MVP（GAP #8）

**Files:**
- Create: `sebastian/memory/maintenance.py`
- Modify: `sebastian/gateway/app.py`
- Test: `tests/unit/memory/test_maintenance.py`

**MVP 范围：**
1. **过期扫描**：扫 `ProfileMemoryRecord` 和 `EpisodeMemoryRecord` 中 `status=active` 且 `valid_until <= now` 的记录，标记为 EXPIRED。（补足 consolidator EXPIRE 以外的漏网）
2. **重复压缩**：同 subject+slot+scope 且 `content` 完全一致且 `status=active` 的记录，保留 confidence 最高的，其余 status=SUPERSEDED。
3. **索引修复**：扫 `episode_memories` 表中 id 未在 `episode_memories_fts` 出现的记录，补插 FTS 索引行。
4. **降权** 和 "摘要替换" 均由前述 Task 8 和 Cross-Session Worker 承担，Maintenance 不重复。

**触发方式：** 定时任务（每 24 小时一次）。

- [ ] **Step 1: 写 maintenance worker 骨架**

```python
# sebastian/memory/maintenance.py
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sebastian.memory.types import MemoryStatus

logger = logging.getLogger(__name__)


class MemoryMaintenanceWorker:
    """Phase C maintenance: expire, dedupe, FTS index repair.

    Non-destructive — only flips statuses and re-inserts missing FTS rows.
    """

    _WORKER_ID = "memory_maintenance_worker"
    _RULE_VERSION = "phase_c_maint_v1"

    def __init__(
        self,
        *,
        db_factory: async_sessionmaker[AsyncSession],
        memory_settings_fn: Callable[[], bool],
    ) -> None:
        self._db_factory = db_factory
        self._memory_settings_fn = memory_settings_fn

    async def run_once(self) -> None:
        if not self._memory_settings_fn():
            return
        async with self._db_factory() as session:
            expired = await self._expire_overdue(session)
            deduped = await self._dedupe_exact(session)
            repaired = await self._repair_fts_index(session)
            await session.commit()
            logger.info(
                "maintenance: expired=%d deduped=%d fts_repaired=%d",
                expired, deduped, repaired,
            )

    async def _expire_overdue(self, session: AsyncSession) -> int:
        from sebastian.store.models import EpisodeMemoryRecord, ProfileMemoryRecord

        now = datetime.now(UTC)
        p_res = await session.execute(
            update(ProfileMemoryRecord)
            .where(
                ProfileMemoryRecord.status == MemoryStatus.ACTIVE.value,
                ProfileMemoryRecord.valid_until.isnot(None),
                ProfileMemoryRecord.valid_until <= now,
            )
            .values(status=MemoryStatus.EXPIRED.value, updated_at=now)
        )
        e_res = await session.execute(
            update(EpisodeMemoryRecord)
            .where(
                EpisodeMemoryRecord.status == MemoryStatus.ACTIVE.value,
                # EpisodeMemoryRecord has no valid_until column → noop here
            )
            .values(status=MemoryStatus.ACTIVE.value)  # no-op guard
        )
        return (p_res.rowcount or 0)

    async def _dedupe_exact(self, session: AsyncSession) -> int:
        from sebastian.store.models import ProfileMemoryRecord

        rows = (await session.scalars(
            select(ProfileMemoryRecord).where(
                ProfileMemoryRecord.status == MemoryStatus.ACTIVE.value,
            )
        )).all()
        # group by (subject_id, scope, slot_id, content)
        buckets: dict[tuple[str, str, str, str], list[Any]] = {}
        for r in rows:
            buckets.setdefault(
                (r.subject_id, r.scope, r.slot_id, r.content), []
            ).append(r)
        count = 0
        now = datetime.now(UTC)
        for members in buckets.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (r.confidence, r.created_at), reverse=True)
            loser_ids = [m.id for m in members[1:]]
            await session.execute(
                update(ProfileMemoryRecord)
                .where(ProfileMemoryRecord.id.in_(loser_ids))
                .values(status=MemoryStatus.SUPERSEDED.value, updated_at=now)
            )
            count += len(loser_ids)
        return count

    async def _repair_fts_index(self, session: AsyncSession) -> int:
        """Re-insert episode_memories rows missing from the FTS virtual table."""
        from sebastian.store.models import EpisodeMemoryRecord

        # Find missing FTS rows via LEFT JOIN-like query
        rows = (await session.scalars(
            select(EpisodeMemoryRecord).where(
                EpisodeMemoryRecord.id.notin_(
                    select(text("memory_id")).select_from(
                        text("episode_memories_fts")
                    )
                ),
            )
        )).all()
        for r in rows:
            await session.execute(
                text(
                    "INSERT INTO episode_memories_fts(memory_id, content_segmented) "
                    "VALUES (:mid, :seg)"
                ),
                {"mid": r.id, "seg": r.content_segmented},
            )
        return len(rows)
```

- [ ] **Step 2: 写测试**

```python
# tests/unit/memory/test_maintenance.py
import pytest
from datetime import UTC, datetime, timedelta

from sebastian.memory.maintenance import MemoryMaintenanceWorker


@pytest.mark.asyncio
async def test_maintenance_expires_overdue_profile_records(
    db_factory, memory_enabled_flag_fn, make_profile,
) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    await make_profile(id="p-old", valid_until=past)
    await make_profile(id="p-live", valid_until=None)

    worker = MemoryMaintenanceWorker(
        db_factory=db_factory, memory_settings_fn=memory_enabled_flag_fn,
    )
    await worker.run_once()

    async with db_factory() as session:
        from sebastian.store.models import ProfileMemoryRecord
        old = await session.get(ProfileMemoryRecord, "p-old")
        live = await session.get(ProfileMemoryRecord, "p-live")
        assert old.status == "expired"
        assert live.status == "active"


@pytest.mark.asyncio
async def test_maintenance_dedupes_exact_content(
    db_factory, memory_enabled_flag_fn, make_profile,
) -> None:
    await make_profile(id="p-a", content="dup", slot_id="s1", confidence=0.5)
    await make_profile(id="p-b", content="dup", slot_id="s1", confidence=0.9)
    await make_profile(id="p-c", content="dup", slot_id="s1", confidence=0.7)

    worker = MemoryMaintenanceWorker(
        db_factory=db_factory, memory_settings_fn=memory_enabled_flag_fn,
    )
    await worker.run_once()

    async with db_factory() as session:
        from sebastian.store.models import ProfileMemoryRecord
        from sqlalchemy import select
        rows = (await session.scalars(select(ProfileMemoryRecord))).all()
        active = [r for r in rows if r.status == "active"]
        assert len(active) == 1
        assert active[0].id == "p-b"  # highest confidence wins


@pytest.mark.asyncio
async def test_maintenance_repairs_missing_fts_rows(
    db_factory, memory_enabled_flag_fn, make_episode,
) -> None:
    from sqlalchemy import text

    await make_episode(id="e-orphan", content="迷路 的 记忆")

    # Manually delete the FTS row to simulate corruption.
    async with db_factory() as session:
        await session.execute(
            text("DELETE FROM episode_memories_fts WHERE memory_id=:mid"),
            {"mid": "e-orphan"},
        )
        await session.commit()

    worker = MemoryMaintenanceWorker(
        db_factory=db_factory, memory_settings_fn=memory_enabled_flag_fn,
    )
    await worker.run_once()

    async with db_factory() as session:
        row = await session.execute(
            text(
                "SELECT memory_id FROM episode_memories_fts "
                "WHERE memory_id=:mid"
            ),
            {"mid": "e-orphan"},
        )
        assert row.first() is not None
```

> **fixture 说明：** `make_profile` / `make_episode` 若不存在需要在 `tests/unit/memory/conftest.py` 增加——参考现有 fixture 风格。

- [ ] **Step 3: 运行测试**

```bash
pytest tests/unit/memory/test_maintenance.py -v
```

Expected: 调好 fixture 后 PASS。

- [ ] **Step 4: gateway 注册定时触发**

`sebastian/gateway/app.py` lifespan startup：

```python
    from sebastian.memory.maintenance import MemoryMaintenanceWorker
    maint_worker = MemoryMaintenanceWorker(
        db_factory=state.db_factory,
        memory_settings_fn=lambda: state.memory_settings.enabled,
    )
    state.maintenance_task = asyncio.create_task(
        _run_periodic(maint_worker.run_once, interval_seconds=24 * 3600),
        name="memory_maintenance",
    )
```

shutdown 同 Task 13 方式 cancel。

- [ ] **Step 5: 更新 CHANGELOG**

`### Added`：

```
- 新增 `MemoryMaintenanceWorker`：每 24 小时一次，做过期扫描、重复压缩、FTS 索引修复，落实 spec consolidation §1.3
```

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/maintenance.py sebastian/gateway/app.py tests/unit/memory/ CHANGELOG.md
git commit -m "feat(memory): 新增 MemoryMaintenanceWorker MVP 满足 spec §1.3"
```

---

## 整体验证（所有 Task 完成后）

- [ ] **Step V1: 全量 lint**

```bash
ruff check sebastian/ tests/
ruff format --check sebastian/ tests/
```

Expected: 0 error。

- [ ] **Step V2: 全量类型检查**

```bash
mypy sebastian/
```

Expected: 0 error。

- [ ] **Step V3: 全量测试**

```bash
pytest tests/ -v
```

Expected: 全 PASS。

- [ ] **Step V4: 对照 spec 做回归审查**

再次对照 `docs/architecture/spec/memory/` 7 份 spec，用 2026-04-19 审查报告中同样的 GAP 清单，确认每项都可以 OK。

- [ ] **Step V5: 创建 PR**

```bash
gh pr create --base main --title "fix(memory): 补齐 spec 审查 13 项 GAP" --body "$(cat <<'EOF'
## Summary

- 修复 2026-04-19 memory spec 合规审查发现的 12 个 GAP（GAP #4 temperature 暂不修，保持 provider 默认值）
- 分 4 个阶段渐进修复，每阶段独立可 merge
- 对齐 `docs/architecture/spec/memory/` 7 份 spec 的条款

## GAP 清单

- #1 retrieval Assembler 增补 valid_from 过滤
- #2 Episode Lane summary 优先再下钻 episode
- #3 ExtractorInput 补 task 字段
- #4 ~~LLMProvider temperature~~ **deferred**（先观察默认参数效果）
- #5 summary 默认替换策略
- #6 relation(exclusive) 时间边界覆盖
- #7 CrossSessionConsolidationWorker
- #8 MemoryMaintenanceWorker
- #9 BaseAgent hook 拆分（planner/assembler/consolidation）
- #10 Assembler 增补 status/subject_id 安全网
- #11 memory_search current truth 明确语义
- #12 decision_log 增补 input_source
- #13 Assembler 标题对齐 spec 原文

## Test plan

- [ ] 全量 `pytest tests/` PASS
- [ ] `ruff check` 0 error
- [ ] `mypy sebastian/` 0 error
- [ ] 手动跑 gateway，Settings → Memory 页面无报错
- [ ] Android App 端 memory_save / memory_search 工具正常
EOF
)"
```

---

*计划结束。*
