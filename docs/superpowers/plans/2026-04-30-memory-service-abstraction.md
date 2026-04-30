# Memory Service 顶层抽象 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Sebastian memory 模块新增行为不变的 `MemoryService` 顶层 facade，让 BaseAgent、memory tools 和 consolidation 通过稳定 service 边界访问记忆能力。

**Architecture:** P0 只新增 `sebastian/memory/contracts/` 和 `sebastian/memory/services/`，现有 `retrieval.py`、`pipeline.py`、store 文件保持原位。新 service 先薄封装现有函数，外部调用方逐步切到 facade；不改 schema、不改 prompt 格式、不引入图检索。

**Tech Stack:** Python 3.12、Pydantic、SQLAlchemy async session、pytest、pytest-asyncio、FastAPI gateway lifespan。

---

## File Structure

Create:

- `sebastian/memory/contracts/__init__.py`：导出 service 边界 contract。
- `sebastian/memory/contracts/retrieval.py`：`PromptMemoryRequest`、`PromptMemoryResult`、`ExplicitMemorySearchRequest`、`ExplicitMemorySearchResult`。
- `sebastian/memory/contracts/writing.py`：`MemoryWriteRequest`、`MemoryWriteResult`。
- `sebastian/memory/services/__init__.py`：导出 `MemoryService`、`MemoryRetrievalService`、`MemoryWriteService`。
- `sebastian/memory/services/retrieval.py`：包住现有 prompt retrieval 和 explicit memory search 逻辑。
- `sebastian/memory/services/writing.py`：包住现有 `process_candidates()`，支持 service-owned transaction 和 caller-owned transaction。
- `sebastian/memory/services/memory_service.py`：组合 retrieval/write service，处理 memory enabled、错误降级、snapshot dirty。
- `tests/unit/memory/test_memory_services.py`：service 层单元测试。

Modify:

- `sebastian/gateway/state.py`：新增 `memory_service` runtime singleton。
- `sebastian/gateway/app.py`：gateway lifespan 创建 `MemoryService`。
- `sebastian/core/base_agent.py`：`_memory_section()` 改走 `state.memory_service.retrieve_for_prompt()`。
- `sebastian/capabilities/tools/memory_search/__init__.py`：工具改走 `state.memory_service.search()`，保留 ToolResult 输出。
- `sebastian/capabilities/tools/memory_save/__init__.py`：写入候选改走 `state.memory_service.write_candidates()`，保留 extractor 和用户输出。
- `sebastian/memory/consolidation.py`：consolidation candidate writes 改走 caller-owned write helper，不改变事务边界。
- `tests/unit/capabilities/test_memory_tools.py`：调整/新增 service 调用覆盖。
- `tests/unit/memory/test_retrieval.py` 或新 service 测试：覆盖 prompt retrieval adapter。
- `tests/integration/memory/test_session_consolidation_proposes_slots.py`：更新 monkeypatch 目标或补 service helper 断言。
- `sebastian/memory/README.md`：同步 service 边界。
- `docs/architecture/spec/memory/INDEX.md`、`overview.md`、`retrieval.md`、`write-pipeline.md`：同步 P0 service facade 状态。

Do not modify:

- DB models / migrations.
- `MemoryArtifact` / `CandidateArtifact` schema.
- Prompt section text.
- `memory_search` output item fields.

---

### Task 1: Add Contract Models

**Files:**
- Create: `sebastian/memory/contracts/__init__.py`
- Create: `sebastian/memory/contracts/retrieval.py`
- Create: `sebastian/memory/contracts/writing.py`
- Test: `tests/unit/memory/test_memory_services.py`

- [ ] **Step 1: Write contract import tests**

Add tests that import all new contract classes and instantiate minimal requests:

```python
from sebastian.memory.contracts.retrieval import PromptMemoryRequest


def test_prompt_memory_request_defaults_dedupe_sets() -> None:
    request = PromptMemoryRequest(
        session_id="sess-1",
        agent_type="sebastian",
        user_message="我喜欢什么",
        subject_id="user:owner",
    )
    assert request.resident_record_ids == set()
    assert request.resident_dedupe_keys == set()
    assert request.resident_canonical_bullets == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/memory/test_memory_services.py::test_prompt_memory_request_defaults_dedupe_sets -v`

Expected: FAIL because `sebastian.memory.contracts` does not exist.

- [ ] **Step 3: Implement retrieval contracts**

Create `retrieval.py` with:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PromptMemoryRequest(BaseModel):
    session_id: str
    agent_type: str
    user_message: str
    subject_id: str
    resident_record_ids: set[str] = Field(default_factory=set)
    resident_dedupe_keys: set[str] = Field(default_factory=set)
    resident_canonical_bullets: set[str] = Field(default_factory=set)


class PromptMemoryResult(BaseModel):
    section: str


class ExplicitMemorySearchRequest(BaseModel):
    query: str
    session_id: str
    agent_type: str
    subject_id: str
    limit: int = 5


class ExplicitMemorySearchResult(BaseModel):
    items: list[dict[str, Any]]
```

- [ ] **Step 4: Implement writing contracts**

Create `writing.py` with `MemoryWriteRequest` and `MemoryWriteResult`. Reuse existing memory types:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from sebastian.memory.types import CandidateArtifact, ProposedSlot, ResolveDecision, MemoryDecisionType


class MemoryWriteRequest(BaseModel):
    candidates: list[CandidateArtifact]
    proposed_slots: list[ProposedSlot] = Field(default_factory=list)
    session_id: str
    agent_type: str
    worker_id: str
    model_name: str | None = None
    rule_version: str
    input_source: dict[str, Any]
    proposed_by: Literal["extractor", "consolidator"] = "extractor"


@dataclass
class MemoryWriteResult:
    decisions: list[ResolveDecision] = field(default_factory=list)
    proposed_slots_registered: list[str] = field(default_factory=list)
    proposed_slots_rejected: list[dict[str, Any]] = field(default_factory=list)

    @property
    def saved_count(self) -> int:
        return sum(
            1
            for decision in self.decisions
            if decision.decision != MemoryDecisionType.DISCARD
            and decision.new_memory is not None
        )

    @property
    def discarded_count(self) -> int:
        return sum(1 for decision in self.decisions if decision.decision == MemoryDecisionType.DISCARD)
```

- [ ] **Step 5: Export contracts**

Update `contracts/__init__.py` to export all contract classes.

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/memory/test_memory_services.py -v`

Expected: PASS for contract tests.

- [ ] **Step 7: Commit**

```bash
git add sebastian/memory/contracts/__init__.py sebastian/memory/contracts/retrieval.py sebastian/memory/contracts/writing.py tests/unit/memory/test_memory_services.py
git commit -m "feat(memory): 新增 memory service contracts"
```

---

### Task 2: Add MemoryRetrievalService

**Files:**
- Create: `sebastian/memory/services/__init__.py`
- Create: `sebastian/memory/services/retrieval.py`
- Modify: `tests/unit/memory/test_memory_services.py`

- [ ] **Step 1: Write failing prompt retrieval service test**

Patch `sebastian.memory.services.retrieval.retrieve_memory_section` and assert the service builds `RetrievalContext` correctly.

```python
@pytest.mark.asyncio
async def test_retrieval_service_delegates_prompt_retrieval(db_session, monkeypatch) -> None:
    captured = {}

    async def fake_retrieve(context, *, db_session):
        captured["context"] = context
        return "## Memory\n- [fact] hello"

    monkeypatch.setattr("sebastian.memory.services.retrieval.retrieve_memory_section", fake_retrieve)

    service = MemoryRetrievalService()
    result = await service.retrieve_for_prompt(
        PromptMemoryRequest(
            session_id="sess-1",
            agent_type="sebastian",
            user_message="hello",
            subject_id="user:owner",
        ),
        db_session=db_session,
    )

    assert result.section == "## Memory\n- [fact] hello"
    assert captured["context"].access_purpose == "context_injection"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/memory/test_memory_services.py::test_retrieval_service_delegates_prompt_retrieval -v`

Expected: FAIL because service does not exist.

- [ ] **Step 3: Implement prompt retrieval adapter**

`MemoryRetrievalService.retrieve_for_prompt()` should build existing `RetrievalContext` and call `retrieve_memory_section()`.

- [ ] **Step 4: Implement explicit search logic behind service**

Implement `MemoryRetrievalService.search()` by porting the lane fetch/search logic from `_do_search()` in `sebastian/capabilities/tools/memory_search/__init__.py`, returning `ExplicitMemorySearchResult(items=items)`.

Do not modify the tool in this task. The tool-side switch happens later in Task 7.

Keep these exact behaviors:

- all four lanes forced active;
- `effective_limit = max(requested_limit, active_lane_count)`;
- `_keep_record(... access_purpose="tool_search")`;
- cross-lane dedupe by record id;
- same item dictionaries.

- [ ] **Step 5: Run service tests**

Run: `pytest tests/unit/memory/test_memory_services.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/memory/services/__init__.py sebastian/memory/services/retrieval.py tests/unit/memory/test_memory_services.py
git commit -m "feat(memory): 新增 memory retrieval service"
```

---

### Task 3: Add MemoryWriteService

**Files:**
- Create: `sebastian/memory/services/writing.py`
- Modify: `tests/unit/memory/test_memory_services.py`

- [ ] **Step 1: Write caller-owned transaction test**

Test that `write_candidates_in_session()` delegates to `process_candidates()` and does not call `commit()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/memory/test_memory_services.py::test_write_service_caller_owned_does_not_commit -v`

Expected: FAIL because `MemoryWriteService` does not exist.

- [ ] **Step 3: Implement `write_candidates_in_session()`**

The helper should accept caller-provided `db_session`, stores, logger, registry, and handler. It calls existing `process_candidates()` and converts `PipelineResult` into `MemoryWriteResult`.

- [ ] **Step 4: Implement service-owned `write_candidates()`**

This method opens `db_factory()`, creates the existing stores, calls `write_candidates_in_session()`, and commits. It should not know about extractor logic.

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/memory/test_memory_services.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/memory/services/writing.py tests/unit/memory/test_memory_services.py
git commit -m "feat(memory): 新增 memory write service"
```

---

### Task 4: Add MemoryService Composition Root

**Files:**
- Create: `sebastian/memory/services/memory_service.py`
- Modify: `sebastian/memory/services/__init__.py`
- Modify: `tests/unit/memory/test_memory_services.py`

- [ ] **Step 1: Write disabled-memory test**

Test that `retrieve_for_prompt()` returns empty section when `memory_settings_fn()` is false and does not call retrieval service.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/memory/test_memory_services.py::test_memory_service_disabled_returns_empty_prompt -v`

Expected: FAIL because `MemoryService` does not exist.

- [ ] **Step 3: Implement MemoryService**

`MemoryService` should:

- hold `db_factory`, `retrieval`, `writing`, optional `resident_snapshot_refresher`, optional `memory_settings_fn`;
- use `memory_settings_fn: Callable[[], bool] | None`, not `MemoryRuntimeSettings`, to avoid a `memory -> gateway` import cycle;
- default to `MemoryRetrievalService()` and `MemoryWriteService(db_factory=db_factory)` when child services are not injected;
- open DB sessions in `MemoryService.retrieve_for_prompt()` and `MemoryService.search()`, then pass `db_session` into `MemoryRetrievalService`;
- return empty prompt result when disabled;
- catch prompt retrieval exceptions and return `PromptMemoryResult(section="")`;
- delegate explicit search and writes;
- expose a top-level `write_candidates_in_session()` method for caller-owned consolidation transactions, instead of requiring callers to access `memory_service.writing`;
- after service-owned successful write, mark resident snapshot dirty if `saved_count > 0`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/memory/test_memory_services.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/memory/services/__init__.py sebastian/memory/services/memory_service.py tests/unit/memory/test_memory_services.py
git commit -m "feat(memory): 新增 memory service facade"
```

---

### Task 5: Wire Gateway State

**Files:**
- Modify: `sebastian/gateway/state.py`
- Modify: `sebastian/gateway/app.py`
- Test: existing gateway lifespan tests if present, otherwise unit import/build checks.

- [ ] **Step 1: Add state typing**

In `state.py`, add TYPE_CHECKING import for `MemoryService` and runtime variable:

```python
memory_service: MemoryService | None = None
```

- [ ] **Step 2: Initialize MemoryService in lifespan**

In `gateway/app.py`, after resident snapshot refresher is created and before tools need runtime service calls, instantiate:

```python
from sebastian.memory.services import MemoryService

state.memory_service = MemoryService(
    db_factory=db_factory,
    resident_snapshot_refresher=resident_refresher,
    memory_settings_fn=lambda: state.memory_settings.enabled,
)
```

- [ ] **Step 3: Run focused tests**

Run: `pytest tests/unit/memory/test_memory_services.py -v`

Expected: PASS.

- [ ] **Step 4: Run import check**

Run: `python -m compileall sebastian/gateway/state.py sebastian/gateway/app.py sebastian/memory/services sebastian/memory/contracts`

Expected: no compile errors.

- [ ] **Step 5: Commit**

```bash
git add sebastian/gateway/state.py sebastian/gateway/app.py
git commit -m "feat(memory): 在 gateway 初始化 memory service"
```

---

### Task 6: Migrate BaseAgent Prompt Retrieval

**Files:**
- Modify: `sebastian/core/base_agent.py`
- Test: existing BaseAgent / memory retrieval tests.

- [ ] **Step 1: Write or update test**

Add a test that patches `state.memory_service.retrieve_for_prompt()` and asserts `_memory_section()` uses it. Preserve fail-closed behavior when service is absent.

- [ ] **Step 2: Run test to verify it fails**

Run the focused test.

Expected: FAIL because `_memory_section()` still imports `retrieve_memory_section()` directly.

- [ ] **Step 3: Update `_memory_section()`**

Keep existing guards:

- depth guard;
- `_db_factory is None`;
- `resolve_subject()`.

Remove the direct `state.memory_settings.enabled` guard inside `BaseAgent._memory_section()`; in current code this is the check near line 269. The enabled check is now owned by `MemoryService`.

Do not remove the enabled guard in `_resident_memory_section()` near line 236. Resident snapshot reading remains separate in P0 and still needs its own fail-closed guard.

Then build `PromptMemoryRequest` and call `state.memory_service.retrieve_for_prompt()`.

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/unit/memory/test_retrieval.py -v
pytest tests/unit/memory/test_memory_services.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/core/base_agent.py tests/unit/memory/test_memory_services.py
git commit -m "refactor(memory): BaseAgent 通过 memory service 注入记忆"
```

---

### Task 7: Migrate memory_search Tool

**Files:**
- Modify: `sebastian/capabilities/tools/memory_search/__init__.py`
- Modify: `tests/unit/capabilities/test_memory_tools.py`

- [ ] **Step 1: Write service delegation test**

Patch `state.memory_service.search()` and assert `memory_search()` returns the same `ToolResult` shape with `output={"items": ...}` and `display=render_memory_search_display(items)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/capabilities/test_memory_tools.py -k memory_search -v`

Expected: relevant new test FAILS because tool still calls inline `_do_search`.

- [ ] **Step 3: Simplify tool**

Keep tool-level:

- trace start/done/error;
- memory enabled error;
- storage unavailable error;
- `get_tool_context()`;
- `resolve_subject()`;
- `ToolResult` formatting.

Move lane fetch/search internals fully to `MemoryRetrievalService.search()`.

- [ ] **Step 4: Run memory tool tests**

Run: `pytest tests/unit/capabilities/test_memory_tools.py -k memory_search -v`

Expected: PASS.

- [ ] **Step 5: Run integration search test**

Run: `pytest tests/integration/test_memory_supersede_chain.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/capabilities/tools/memory_search/__init__.py tests/unit/capabilities/test_memory_tools.py
git commit -m "refactor(memory): memory_search 走 service 检索"
```

---

### Task 8: Migrate memory_save Tool

**Files:**
- Modify: `sebastian/capabilities/tools/memory_save/__init__.py`
- Modify: `tests/unit/capabilities/test_memory_tools.py`

- [ ] **Step 1: Write service delegation test**

Patch `state.memory_service.write_candidates()` and assert `_do_save()` converts returned `MemoryWriteResult` into the existing `MemorySaveResult` summary.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/capabilities/test_memory_tools.py -k memory_save -v`

Expected: new service delegation test FAILS.

- [ ] **Step 3: Update `_do_save()`**

Keep extractor and slot precheck logic in the tool for P0. Replace direct `process_candidates()` and manual commit/snapshot mutation with:

```python
write_result = await state.memory_service.write_candidates(MemoryWriteRequest(...))
```

The service-owned path handles commit and dirty marking.

- [ ] **Step 4: Run memory save tests**

Run: `pytest tests/unit/capabilities/test_memory_tools.py -k memory_save -v`

Expected: PASS.

- [ ] **Step 5: Run supersede integration**

Run: `pytest tests/integration/test_memory_supersede_chain.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sebastian/capabilities/tools/memory_save/__init__.py tests/unit/capabilities/test_memory_tools.py
git commit -m "refactor(memory): memory_save 走 service 写入"
```

---

### Task 9: Migrate Session Consolidation Candidate Writes

**Files:**
- Modify: `sebastian/memory/consolidation.py`
- Modify: `tests/integration/memory/test_session_consolidation_proposes_slots.py`

- [ ] **Step 1: Update tests to observe service helper**

Existing tests monkeypatch `process_candidates()`. Change or add tests to patch the caller-owned `MemoryService.write_candidates_in_session()` path and assert `slot_proposal_handler` is passed.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/memory/test_session_consolidation_proposes_slots.py -v`

Expected: new/updated service helper assertion FAILS.

- [ ] **Step 3: Update worker**

Inside the existing transaction, replace direct `process_candidates()` with the top-level `MemoryService.write_candidates_in_session()` helper.

Do not move EXPIRE handling in this task.

Do not let the helper commit.

Do not migrate consolidation's `DEFAULT_RETRIEVAL_PLANNER` / `EntityRegistry` initialization in this task; P0 only migrates candidate writes.

- [ ] **Step 4: Run consolidation tests**

Run:

```bash
pytest tests/integration/memory/test_session_consolidation_proposes_slots.py -v
pytest tests/unit/memory/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sebastian/memory/consolidation.py tests/integration/memory/test_session_consolidation_proposes_slots.py
git commit -m "refactor(memory): consolidation 通过 service 写入候选记忆"
```

---

### Task 10: Documentation Updates

**Files:**
- Modify: `sebastian/memory/README.md`
- Modify: `docs/architecture/spec/memory/INDEX.md`
- Modify: `docs/architecture/spec/memory/overview.md`
- Modify: `docs/architecture/spec/memory/retrieval.md`
- Modify: `docs/architecture/spec/memory/write-pipeline.md`

- [ ] **Step 1: Update memory README**

Add a section describing:

- `contracts/` as service boundary models;
- `services/` as facade over existing retrieval/write internals;
- P0 keeps existing files in place.

- [ ] **Step 2: Update architecture memory specs**

Document implementation state:

- `MemoryService` is now top-level access boundary.
- `retrieve_memory_section()` and `process_candidates()` remain P0 internals.
- Graph-routed retrieval remains future work.

- [ ] **Step 3: Run Python compile check on modified memory package**

Run: `python -m compileall sebastian/memory`

Expected: no compile errors.

- [ ] **Step 4: Commit**

```bash
git add sebastian/memory/README.md docs/architecture/spec/memory/INDEX.md docs/architecture/spec/memory/overview.md docs/architecture/spec/memory/retrieval.md docs/architecture/spec/memory/write-pipeline.md
git commit -m "docs(memory): 记录 memory service facade 边界"
```

---

### Task 11: Final Verification

**Files:**
- No code edits unless verification reveals failures.

- [ ] **Step 1: Run focused memory suite**

Run:

```bash
pytest tests/unit/memory tests/unit/capabilities/test_memory_tools.py tests/integration/memory/test_session_consolidation_proposes_slots.py tests/integration/test_memory_supersede_chain.py -v
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched Python files**

Run:

```bash
ruff check sebastian/memory sebastian/core/base_agent.py sebastian/capabilities/tools/memory_search sebastian/capabilities/tools/memory_save sebastian/gateway/app.py sebastian/gateway/state.py tests/unit/memory/test_memory_services.py tests/unit/capabilities/test_memory_tools.py tests/integration/memory/test_session_consolidation_proposes_slots.py
```

Expected: PASS.

- [ ] **Step 3: Run graphify rebuild**

Because code files changed, run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: command exits 0.

- [ ] **Step 4: Review git diff**

Run: `git diff --stat`

Expected: changes are limited to memory service abstraction, tools, BaseAgent, gateway wiring, tests, docs, and graphify output.

- [ ] **Step 5: Commit verification/doc cleanup if needed**

Only commit if Step 1-4 required follow-up edits:

```bash
git add <specific files>
git commit -m "test(memory): 验证 memory service facade"
```
