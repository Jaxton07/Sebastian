# Memory Spec Audit Targeted Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 memory spec 审查中会影响当前记忆正确性、LLM 结构化协议、prompt 注入安全边界和审计可读性的 GAP。

**Architecture:** 本轮只做三类变更：检索过滤正确性、LLM input schema 契约、Episode Lane summary-first。summary 替换、exclusive relation、cross-session consolidation、maintenance worker 作为独立设计任务另开计划，避免在当前 candidate 层上做语义不完整的补丁。

**Tech Stack:** Python 3.12、Pydantic v2、SQLAlchemy async、SQLite/FTS5、jieba、pytest、ruff、mypy。

---

## Scope Decisions

### 本轮纳入

- `valid_from` / `valid_until` / `status` / `subject_id` 的 current truth 过滤闭环。
- `ExtractorInput.task` 契约字段。
- Episode Lane 的 query-aware summary-first 检索。
- `memory_search` 的 current/historical citation 语义。
- `memory_decision_log.input_source` 审计字段。
- README / spec / CHANGELOG 中明确本轮取舍，避免后续 agent 误把 deferred 项当成已实现。

### 本轮不纳入

- 不做 LLM temperature provider 接口。当前使用 provider 默认参数，等真实效果再决定是否改 provider 抽象。
- 不做 BaseAgent hook 拆分。当前 `_memory_section()` 已是 BaseAgent retrieval hook；本轮修 pipeline 行为，不为字面拆方法制造 churn。
- 不把每个 turn 完成伪装成 `SESSION_COMPLETED`。这会导致过早沉淀或过早写入 `SessionConsolidationRecord`，风险高。
- 不改 Assembler 四段标题。当前标题已表达 current/historical 语义，文案差异不影响正确性。
- 不实现 summary 默认替换。需要先定义 default summary 的唯一键、scope、topic/session 边界。
- 不实现 relation(exclusive)。需要先定义 exclusive 判定来源、predicate registry、source/target 冲突范围和审计方式。
- 不新增 CrossSessionConsolidationWorker / MemoryMaintenanceWorker。两者需要单独 spec，不在本轮拼半成品定时任务。

---

## Task 1: 补齐 current truth 过滤闭环

**Files:**
- Modify: `sebastian/memory/profile_store.py`
- Modify: `sebastian/memory/retrieval.py`
- Test: `tests/unit/memory/test_profile_store.py`
- Test: `tests/unit/memory/test_retrieval.py`
- Test: `tests/unit/core/test_base_agent_memory.py`

**Intent:** spec 要求 current truth 仅来自 active 且时间有效的记忆。当前实现已过滤 `valid_until`，但 `valid_from` 未来值仍可能被查询和注入。Assembler 也缺 status/subject 二次安全网。

- [ ] **Step 1: 写 profile store 的 failing tests**

在 `tests/unit/memory/test_profile_store.py` 增加测试：

- `search_active` 不返回 `valid_from > now` 的 active record。
- `get_active_by_slot` 不返回 `valid_from > now` 的 active record。
- `search_recent_context` 不返回 `valid_from > now` 的 active record。

运行：

```bash
pytest tests/unit/memory/test_profile_store.py -k "valid_from" -v
```

Expected: 新测试失败，说明未来才生效的 profile 仍被返回。

- [ ] **Step 2: 实现 profile store 的 `valid_from` 过滤**

在 `ProfileMemoryStore.get_active_by_slot()`、`search_active()`、`search_recent_context()` 的 SQL 条件中加入：

```python
or_(
    ProfileMemoryRecord.valid_from.is_(None),
    ProfileMemoryRecord.valid_from <= now,
)
```

保留现有 `valid_until is None OR valid_until > now`。

- [ ] **Step 3: 写 assembler 的 failing tests**

在 `tests/unit/memory/test_retrieval.py` 的 `TestMemorySectionAssembler` 中增加测试：

- `valid_from > now` 的 fake record 不注入。
- `status != "active"` 的 fake record 不注入。
- `subject_id != context.subject_id` 的 fake record 不注入。

运行：

```bash
pytest tests/unit/memory/test_retrieval.py::TestMemorySectionAssembler -v
```

Expected: 新测试失败。

- [ ] **Step 4: 实现 assembler 二次过滤**

在 `MemorySectionAssembler._keep()` 增加：

```python
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

valid_from = getattr(record, "valid_from", None)
if valid_from is not None:
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=UTC)
    if valid_from > now:
        return False
```

不要发明 `RetrievalContext.scope` 字段；当前 subject 已承载主要隔离边界。

- [ ] **Step 5: 验证**

```bash
pytest tests/unit/memory/test_profile_store.py tests/unit/memory/test_retrieval.py tests/unit/core/test_base_agent_memory.py -q
ruff check sebastian/memory/profile_store.py sebastian/memory/retrieval.py tests/unit/memory/test_profile_store.py tests/unit/memory/test_retrieval.py
```

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/profile_store.py sebastian/memory/retrieval.py tests/unit/memory/test_profile_store.py tests/unit/memory/test_retrieval.py
git commit -m "fix(memory): 补齐 current truth 生效时间过滤" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 2: ExtractorInput 补 `task` 契约字段

**Files:**
- Modify: `sebastian/memory/extraction.py`
- Test: `tests/unit/memory/test_extraction.py`
- Test: `tests/unit/memory/test_consolidation.py`

**Intent:** spec `implementation.md §6` 明确 `ExtractorInput` 包含 `task: Literal["extract_memory_artifacts"]`。当前 `ConsolidatorInput` 有 task，`ExtractorInput` 没有，LLM schema 契约不一致。

- [ ] **Step 1: 写 failing tests**

在 `tests/unit/memory/test_extraction.py` 增加：

- 默认构造 `ExtractorInput(...)` 时 `input.task == "extract_memory_artifacts"`。
- 显式传非法 task 会被 Pydantic 拒绝。
- fake provider 捕获的 user message JSON 中包含 `"task": "extract_memory_artifacts"`。

运行：

```bash
pytest tests/unit/memory/test_extraction.py -k "task" -v
```

Expected: 新测试失败。

- [ ] **Step 2: 实现**

在 `sebastian/memory/extraction.py`：

```python
from typing import TYPE_CHECKING, Any, Literal

class ExtractorInput(BaseModel):
    task: Literal["extract_memory_artifacts"] = "extract_memory_artifacts"
    subject_context: dict[str, Any]
    conversation_window: list[dict[str, Any]]
    known_slots: list[dict[str, Any]]
```

- [ ] **Step 3: 验证**

```bash
pytest tests/unit/memory/test_extraction.py tests/unit/memory/test_consolidation.py -q
mypy sebastian/memory/extraction.py
ruff check sebastian/memory/extraction.py tests/unit/memory/test_extraction.py
```

- [ ] **Step 4: 提交**

```bash
git add sebastian/memory/extraction.py tests/unit/memory/test_extraction.py tests/unit/memory/test_consolidation.py
git commit -m "fix(memory): ExtractorInput 补 task 契约字段" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 3: Episode Lane 实现 query-aware summary-first

**Files:**
- Modify: `sebastian/memory/episode_store.py`
- Modify: `sebastian/memory/retrieval.py`
- Test: `tests/unit/memory/test_episode_store.py`
- Test: `tests/unit/memory/test_retrieval.py`

**Intent:** spec `retrieval.md §4.3` 要求 Episode Lane 默认先查 summary，不足或需要细节时再查原始 episode。当前 `episode_store.search()` 混查 summary/episode。

- [ ] **Step 1: 写 episode store 的 failing tests**

在 `tests/unit/memory/test_episode_store.py` 增加：

- `search_summaries_by_query(subject_id, query, limit)` 只返回 `kind == "summary"`，并且按 query 匹配。
- `search_episodes_only(subject_id, query, limit)` 只返回 `kind == "episode"`。

运行：

```bash
pytest tests/unit/memory/test_episode_store.py -k "summaries_by_query or episodes_only" -v
```

Expected: 新方法不存在，测试失败。

- [ ] **Step 2: 抽公共 FTS 查询逻辑**

在 `EpisodeMemoryStore` 内新增私有方法：

```python
async def _search_by_kind(
    self,
    *,
    subject_id: str,
    query: str,
    kinds: set[MemoryKind],
    limit: int,
) -> list[EpisodeMemoryRecord]:
    ...
```

实现要求：

- 复用现有 `terms_for_query()`、`_build_match_query()`、`match_counts` 排名逻辑。
- SQL 查询增加：
  - `EpisodeMemoryRecord.subject_id == subject_id`
  - `EpisodeMemoryRecord.status == "active"`
  - `EpisodeMemoryRecord.kind.in_([kind.value for kind in kinds])`
- 排序仍按匹配次数排名，再按 `recorded_at` 新到旧。

再让：

- `search()` 调 `_search_by_kind(kinds={SUMMARY, EPISODE})`。
- `search_summaries_by_query()` 调 `_search_by_kind(kinds={SUMMARY})`。
- `search_episodes_only()` 调 `_search_by_kind(kinds={EPISODE})`。

- [ ] **Step 3: 写 retrieval 的 failing tests**

在 `tests/unit/memory/test_retrieval.py` 增加：

- 当 query 匹配的 summary 数量 >= `episode_limit`，Episode Lane 只注入 summary，不注入 episode detail。
- 当 query 匹配的 summary 数量不足时，用 episode detail 补齐 remaining budget。
- 不相关的 summary 不应因为最近而进入结果。

运行：

```bash
pytest tests/unit/memory/test_retrieval.py -k "episode_lane" -v
```

Expected: 新测试失败。

- [ ] **Step 4: 改造 `retrieve_memory_section()` 的 episode lane**

逻辑：

```python
summary_records = await episode_store.search_summaries_by_query(
    subject_id=context.subject_id,
    query=context.user_message,
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

不要用 `search_summaries()` 替代 query-aware summary 搜索。

- [ ] **Step 5: 验证**

```bash
pytest tests/unit/memory/test_episode_store.py tests/unit/memory/test_retrieval.py -q
ruff check sebastian/memory/episode_store.py sebastian/memory/retrieval.py tests/unit/memory/test_episode_store.py tests/unit/memory/test_retrieval.py
```

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/episode_store.py sebastian/memory/retrieval.py tests/unit/memory/test_episode_store.py tests/unit/memory/test_retrieval.py
git commit -m "fix(memory): Episode Lane 先查相关摘要再下钻经历" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 4: memory_search 明确 current/historical citation 语义

**Files:**
- Modify: `sebastian/capabilities/tools/memory_search/__init__.py`
- Test: `tests/unit/capabilities/test_memory_tools.py`

**Intent:** spec 要求区分 current truth 和 historical evidence。当前工具只返回 `is_current: bool`，语义偏粗。本轮增加 `citation_type`，保留 `is_current` 兼容现有调用方。

- [ ] **Step 1: 写 failing tests**

在 `tests/unit/capabilities/test_memory_tools.py` 增加或更新：

- profile item 输出：
  - `citation_type == "current_truth"`
  - `is_current is True`
- summary item 输出：
  - `citation_type == "historical_summary"`
  - `is_current is False`
- episode item 输出：
  - `citation_type == "historical_evidence"`
  - `is_current is False`

运行：

```bash
pytest tests/unit/capabilities/test_memory_tools.py -k "memory_search" -v
```

Expected: 新断言失败。

- [ ] **Step 2: 实现**

在 `memory_search` 组装 items 时：

```python
for record in profile_records:
    items.append({
        ...,
        "citation_type": "current_truth",
        "is_current": True,
    })

for record in episode_records:
    citation_type = (
        "historical_summary"
        if record.kind == "summary"
        else "historical_evidence"
    )
    items.append({
        ...,
        "citation_type": citation_type,
        "is_current": False,
    })
```

不要把 summary 标记为 current。summary 默认是历史证据的压缩，不是 current truth。

- [ ] **Step 3: 验证**

```bash
pytest tests/unit/capabilities/test_memory_tools.py -q
ruff check sebastian/capabilities/tools/memory_search/__init__.py tests/unit/capabilities/test_memory_tools.py
```

- [ ] **Step 4: 提交**

```bash
git add sebastian/capabilities/tools/memory_search/__init__.py tests/unit/capabilities/test_memory_tools.py
git commit -m "fix(memory): memory_search 明确引用语义类型" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 5: decision_log 增加 input_source

**Files:**
- Modify: `sebastian/store/models.py`
- Modify: `sebastian/memory/decision_log.py`
- Modify: `sebastian/memory/consolidation.py`
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py`
- Test: `tests/unit/memory/test_decision_log.py`
- Test: `tests/unit/capabilities/test_memory_tools.py`
- Test: `tests/integration/test_memory_consolidation.py`

**Intent:** spec `storage.md §6` 要求记录原始输入来源。该字段属于 log record，不应污染 resolver 的纯决策对象。

- [ ] **Step 1: 写 failing tests**

测试内容：

- `MemoryDecisionLogger.append(..., input_source={...})` 能持久化到 `MemoryDecisionLogRecord.input_source`。
- DISCARD 且 `new_memory is None` 时，`session_id` 能从 `input_source.session_id` 写入。
- `memory_save` 写出的 decision log 有 `input_source.type == "memory_save_tool"`。
- `SessionConsolidationWorker` 写出的 summary/artifact/expire log 有 `input_source.type == "session_consolidation"`。

运行：

```bash
pytest tests/unit/memory/test_decision_log.py tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py -q
```

Expected: 新测试失败。

- [ ] **Step 2: 增加 DB model 字段**

在 `MemoryDecisionLogRecord` 增加 nullable JSON 字段：

```python
input_source: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
```

不新增 migration；当前项目测试和本地开发使用 `Base.metadata.create_all()`。

- [ ] **Step 3: 扩展 logger API**

`MemoryDecisionLogger.append()` 增加 keyword-only 参数：

```python
input_source: dict[str, Any] | None = None
```

写入 record 时传 `input_source=input_source`。

`session_id` 解析顺序：

1. `decision.new_memory.provenance["session_id"]`
2. `input_source["session_id"]`
3. `None`

保留 `conflicts=list(decision.old_memory_ids)`。

- [ ] **Step 4: 更新调用点**

`memory_save`：

```python
input_source={
    "type": "memory_save_tool",
    "session_id": <tool context session_id if available>,
}
```

`SessionConsolidationWorker`：

```python
input_source={
    "type": "session_consolidation",
    "session_id": session_id,
    "agent_type": agent_type,
}
```

所有 `decision_logger.append()` 调用点都显式传入 input_source；测试 helpers 可以保留默认 None。

- [ ] **Step 5: 验证**

```bash
pytest tests/unit/memory/test_decision_log.py tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py -q
ruff check sebastian/store/models.py sebastian/memory/decision_log.py sebastian/memory/consolidation.py sebastian/capabilities/tools/memory_save/__init__.py
```

- [ ] **Step 6: 提交**

```bash
git add sebastian/store/models.py sebastian/memory/decision_log.py sebastian/memory/consolidation.py sebastian/capabilities/tools/memory_save/__init__.py tests/unit/memory/test_decision_log.py tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py
git commit -m "feat(memory): decision_log 记录原始输入来源" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 6: 文档同步与 deferred 项说明

**Files:**
- Modify: `sebastian/memory/README.md`
- Modify: `docs/architecture/spec/memory/consolidation.md`
- Modify: `docs/architecture/spec/memory/implementation.md`
- Modify: `CHANGELOG.md`

**Intent:** 当前 spec/README 需要明确哪些已经实现、哪些是有意 deferred，避免后续审查反复把设计态能力当作当前 bug。

- [ ] **Step 1: 更新 memory README**

补充：

- current truth 过滤包含 `valid_from/valid_until/status/subject`。
- `ExtractorInput.task` 已对齐 spec。
- Episode Lane 采用 query-aware summary-first。
- `memory_search` 输出 `citation_type`。
- `memory_decision_log.input_source` 记录原始输入来源。
- cross-session consolidation / full maintenance / exclusive relation / summary replacement 仍需单独设计。

- [ ] **Step 2: 更新 implementation spec**

在 §11 结构化输出要求附近说明：

- schema validation 已实现。
- low temperature 暂不通过 provider 抽象暴露；本轮使用 provider 默认值，待实测后另行设计。

- [ ] **Step 3: 更新 consolidation spec**

明确：

- Session Consolidation: implemented。
- Cross-Session Consolidation: planned。
- Memory Maintenance: partial / planned。

- [ ] **Step 4: 更新 CHANGELOG**

在 `[Unreleased]` 下新增：

- Fixed: current truth 生效时间过滤、Episode Lane summary-first、ExtractorInput task、decision_log input_source。
- Changed: memory_search citation_type。

- [ ] **Step 5: 验证**

```bash
ruff check sebastian/memory tests/unit/memory tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py
mypy sebastian/memory
pytest tests/unit/memory tests/unit/capabilities/test_memory_tools.py tests/unit/core/test_base_agent_memory.py tests/integration/test_memory_consolidation.py tests/integration/test_memory_consolidation_lifecycle.py tests/integration/test_memory_catchup_sweep.py tests/integration/test_memory_supersede_chain.py -q
```

- [ ] **Step 6: 提交**

```bash
git add sebastian/memory/README.md docs/architecture/spec/memory/consolidation.md docs/architecture/spec/memory/implementation.md CHANGELOG.md
git commit -m "docs(memory): 记录 spec audit 修复边界" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Final Verification

所有 task 完成后运行：

```bash
pytest tests/unit/memory tests/unit/capabilities/test_memory_tools.py tests/unit/core/test_base_agent_memory.py tests/integration/test_memory_consolidation.py tests/integration/test_memory_consolidation_lifecycle.py tests/integration/test_memory_catchup_sweep.py tests/integration/test_memory_supersede_chain.py -q
ruff check sebastian/memory tests/unit/memory tests/unit/core/test_base_agent_memory.py tests/unit/capabilities/test_memory_tools.py tests/integration/test_memory_consolidation.py
mypy sebastian/memory
```

Expected:

- memory 相关测试全部通过。
- ruff 0 error。
- mypy 0 error。

---

## Follow-Up Plans Required

以下内容不应混入本轮修复，需单独设计：

1. **Summary replacement policy**
   - 定义 default summary 的唯一键。
   - 定义 subject/session/topic/time-window 边界。
   - 定义 supersede 与历史保留策略。

2. **Relation exclusive/time_bound policy**
   - 定义 exclusive predicate registry。
   - 定义 source/target 冲突范围。
   - 定义 candidate 与 confirmed relation 的关系。
   - 定义 decision_log 如何记录旧关系 close-window。

3. **Cross-session consolidation**
   - 定义触发时机、幂等 key、decision log、失败重试。
   - 不允许直接修改 confidence/status 而不写审计。

4. **Memory maintenance**
   - 定义过期扫描、重复压缩、索引修复各自的审计与恢复策略。
   - 不把 no-op worker 当作 spec 完成。
