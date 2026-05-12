# Runtime Context And Skill-First Tool Choice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Sebastian LLM turn receive authoritative current local date/time and prefer local Skills over browser tools for reusable domain tasks.

**Architecture:** Add a small dynamic Runtime Context section in `BaseAgent` and append it when building the per-turn `effective_system_prompt`, immediately before resident memory, dynamic memory, and todos. The section is generated fresh once for each user/agent turn inside `_stream_inner()`, using the server process local timezone from `datetime.now().astimezone()`. Strengthen the existing Bash-gated Skill Management bootstrap so reusable domain tasks search local Skills first, while browser tools are treated as a last-resort interaction surface unless the user explicitly asks for a browser. No new time tool, database setting, user preference, or provider-specific behavior is introduced.

**Tech Stack:** Python 3.12, standard-library `datetime` / `zoneinfo` behavior through local timezone, pytest, Sebastian `BaseAgent` prompt construction, local `sebastian skills` CLI guidance.

---

## Scope

Implement:

- Automatic runtime time injection.
- Skill-first local discovery guidance for reusable domain tasks.

Do not add a `current_time` tool. Existing Bash is enough for explicit shell-based time checks, and adding a tool would increase the model's choice surface without solving the "always knows now" problem.

Do not add browser gating logic, tool permission changes, or a new routing subsystem. This is a prompt policy refinement, not a tool registry change.

## Current Worktree Note

Before executing this plan, preserve unrelated existing uncommitted changes:

- `README.md`
- `README.zh-CN.md`
- `docs/architecture/diagrams/system-overview.html`

Do not revert or stage those files unless the user explicitly asks.

## File Structure

- Modify `sebastian/core/base_agent.py`
  - Add a focused `_runtime_context_section()` method.
  - Import `datetime`.
  - Append the generated runtime section inside `_stream_inner()` when composing `effective_system_prompt`.
  - Strengthen `_skill_management_section()` so local Skill search is the preferred first step for reusable domain tasks and browser tools are explicitly last resort.
- Modify `tests/unit/core/test_base_agent.py`
  - Add tests proving the runtime section is injected into the LLM prompt and generated per turn, not frozen at agent initialization.
- Modify `tests/unit/core/test_prompt_builder.py`
  - Add prompt tests for Skill-first discovery and browser-last guidance.
- Modify `sebastian/capabilities/skills/skill_manager/SKILL.md`
  - Extend the built-in Skill management instructions with a "when solving tasks" policy: local Skill usage instructions are authoritative, registry metadata is not, and browser tools should not replace local Skill discovery.
- Modify `CHANGELOG.md`
  - Add an `[Unreleased]` entry for user-visible runtime prompt and tool-choice behavior.
- Modify `docs/architecture/spec/core/system-prompt.md`
  - Document the new Runtime Context section, its order, and why it is generated per turn.
  - Document the Skill-first / browser-last tool choice policy in the Skill Management bootstrap.
- Modify `sebastian/capabilities/skills/README.md`
  - Clarify that `skill_manager` is the detailed management flow, while `BaseAgent._skill_management_section()` is the always-injected discovery bootstrap for Bash-capable agents.
- Modify `sebastian/core/README.md`
  - Update the modification navigation / prompt injection note so future agents find the runtime time behavior quickly.
- Run graphify rebuild after code/docs edits:
  - `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`

## Design Rules

- Runtime context is authoritative for current time only.
- The section must be generated fresh for every LLM turn.
- The section must not be stored in session history.
- The section must not depend on external network, LLM provider metadata, user message parsing, or a new settings field.
- Use server local timezone for this iteration. Future per-user timezone preference can replace the formatter without changing prompt assembly.
- Keep wording short to reduce prompt cost.
- Skill discovery applies to reusable domain tasks: weather, travel, calendar, email, documents, spreadsheets, finance, code, repositories, browser automation, and similar repeatable workflows.
- Do not force Skill search for simple chat, direct answers from current context, or one-off file operations already covered by the current task context.
- Browser tools are lowest priority. Use them when the user explicitly asks for browser interaction, when the task inherently requires page/UI interaction, or when no suitable local Skill / normal structured tool path exists.

Suggested section format:

```text
## Runtime Context

Current date: Tuesday, 2026-05-12
Current time: 2026-05-12 21:34:56 CST +08:00
Timezone: CST
UTC offset: +08:00

Treat this section as authoritative for current date and time. Do not infer the current date or time from model training data.
```

## Task 1: Add Failing Runtime Context Tests

**Files:**
- Modify: `tests/unit/core/test_base_agent.py`

- [x] **Step 1: Add imports needed by the tests**

At the top of `tests/unit/core/test_base_agent.py`, add:

```python
from datetime import datetime
from datetime import timezone
```

- [x] **Step 2: Add a test for prompt injection**

Add this test near `test_run_streaming_uses_prompt_and_tool_snapshots_before_async_waits()`:

```python
@pytest.mark.asyncio
async def test_run_streaming_injects_runtime_time_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.core.base_agent import BaseAgent
    from sebastian.core.stream_events import TurnDone
    from sebastian.core.types import Session
    from sebastian.store.session_store import SessionStore

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 12, 13, 14, 15, tzinfo=timezone.utc)

        def astimezone(self, tz=None):
            return self

    class TestAgent(BaseAgent):
        name = "sebastian"
        allowed_tools: list[str] | None = []

    import sebastian.core.base_agent as base_agent_module

    monkeypatch.setattr(base_agent_module, "datetime", FixedDatetime)

    store = SessionStore(tmp_path / "sessions")
    await store.create_session(Session(id="time-session", agent_type="sebastian", title="t"))
    agent = TestAgent(MagicMock(), store)
    agent.system_prompt = "base prompt"
    captured: dict[str, str] = {}

    async def fake_stream(system_prompt, messages, **kwargs):
        captured["system_prompt"] = system_prompt
        yield TurnDone(full_text="done")

    agent._loop.stream = fake_stream  # type: ignore[attr-defined]

    await agent.run_streaming("what time is it?", "time-session")

    prompt = captured["system_prompt"]
    assert "base prompt" in prompt
    assert "## Runtime Context" in prompt
    assert "Current date: Tuesday, 2026-05-12" in prompt
    assert "Current time: 2026-05-12 13:14:15 UTC +00:00" in prompt
    assert "Timezone: UTC" in prompt
    assert "UTC offset: +00:00" in prompt
    assert "Do not infer the current date or time from model training data." in prompt
```

- [x] **Step 3: Add a test that the section is dynamic per turn**

Add this test below the previous one:

```python
@pytest.mark.asyncio
async def test_runtime_time_context_is_generated_per_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sebastian.core.base_agent import BaseAgent
    from sebastian.core.stream_events import TurnDone
    from sebastian.core.types import Session
    from sebastian.store.session_store import SessionStore

    class TickingDatetime(datetime):
        calls = 0

        @classmethod
        def now(cls, tz=None):
            cls.calls += 1
            return cls(2026, 5, 12, 13, 14, 14 + cls.calls, tzinfo=timezone.utc)

        def astimezone(self, tz=None):
            return self

    class TestAgent(BaseAgent):
        name = "sebastian"
        allowed_tools: list[str] | None = []

    import sebastian.core.base_agent as base_agent_module

    monkeypatch.setattr(base_agent_module, "datetime", TickingDatetime)

    store = SessionStore(tmp_path / "sessions")
    await store.create_session(Session(id="dynamic-time", agent_type="sebastian", title="t"))
    agent = TestAgent(MagicMock(), store)
    prompts: list[str] = []

    async def fake_stream(system_prompt, messages, **kwargs):
        prompts.append(system_prompt)
        yield TurnDone(full_text="done")

    agent._loop.stream = fake_stream  # type: ignore[attr-defined]

    await agent.run_streaming("first", "dynamic-time")
    await agent.run_streaming("second", "dynamic-time")

    assert "Current time: 2026-05-12 13:14:15 UTC +00:00" in prompts[0]
    assert "Current time: 2026-05-12 13:14:16 UTC +00:00" in prompts[1]
```

- [x] **Step 4: Update existing prompt snapshot assertion**

In `tests/unit/core/test_base_agent.py`, update the existing
`test_run_streaming_uses_prompt_and_tool_snapshots_before_async_waits()` assertion that currently expects the full prompt to equal `"old prompt"`.

Replace:

```python
    assert captured["system_prompt"] == "old prompt"
```

with:

```python
    prompt = str(captured["system_prompt"])
    assert prompt.startswith("old prompt")
    assert "new prompt" not in prompt
    assert "## Runtime Context" in prompt
```

This preserves the original behavior under test: `run_streaming()` must keep the old base prompt snapshot even if async setup mutates `agent.system_prompt`. The test now also accepts the new per-turn runtime section appended after that snapshot.

- [x] **Step 5: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/core/test_base_agent.py::test_run_streaming_injects_runtime_time_context tests/unit/core/test_base_agent.py::test_runtime_time_context_is_generated_per_turn tests/unit/core/test_base_agent.py::test_run_streaming_uses_prompt_and_tool_snapshots_before_async_waits -q
```

Expected: FAIL because `BaseAgent` does not yet include `## Runtime Context`.

## Task 2: Implement Runtime Context Injection

**Files:**
- Modify: `sebastian/core/base_agent.py`
- Test: `tests/unit/core/test_base_agent.py`

- [x] **Step 1: Import `datetime`**

In `sebastian/core/base_agent.py`, add the standard-library import with the existing imports:

```python
from datetime import datetime
```

- [x] **Step 2: Add `_runtime_context_section()`**

Add this method near the other prompt section methods, after `_agents_section()` and before `_knowledge_dir()`:

```python
    def _runtime_context_section(self) -> str:
        now = datetime.now().astimezone()
        timezone_name = now.tzname() or "local"
        raw_offset = now.strftime("%z")
        utc_offset = f"{raw_offset[:3]}:{raw_offset[3:]}" if raw_offset else "unknown"
        return "\n".join(
            [
                "## Runtime Context",
                "",
                f"Current date: {now.strftime('%A, %Y-%m-%d')}",
                f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} "
                f"{timezone_name} {utc_offset}",
                f"Timezone: {timezone_name}",
                f"UTC offset: {utc_offset}",
                "",
                "Treat this section as authoritative for current date and time. "
                "Do not infer the current date or time from model training data.",
            ]
        )
```

Do not include this method in `build_system_prompt()`. `build_system_prompt()` is static after init/rebuild and would freeze time.

- [x] **Step 3: Append runtime context per turn**

In `_stream_inner()`, replace:

```python
        sections = [system_prompt_snapshot]
```

with:

```python
        runtime_context_section = self._runtime_context_section()
        sections = [system_prompt_snapshot, runtime_context_section]
```

Keep resident memory, dynamic memory, and todos after this:

```python
        if resident.content:
            sections.append(resident.content)
        if memory_section:
            sections.append(memory_section)
        if todo_section:
            sections.append(todo_section)
```

This order makes runtime facts available before memory and todos without changing the persisted base prompt.

- [x] **Step 4: Run the targeted tests**

Run:

```bash
pytest tests/unit/core/test_base_agent.py::test_run_streaming_injects_runtime_time_context tests/unit/core/test_base_agent.py::test_runtime_time_context_is_generated_per_turn -q
```

Expected: PASS.

- [x] **Step 5: Run the BaseAgent regression slice**

Run:

```bash
pytest tests/unit/core/test_base_agent.py -q
```

Expected: PASS.

## Task 3: Strengthen Skill-First Tool Choice Prompt

**Files:**
- Modify: `sebastian/core/base_agent.py`
- Modify: `tests/unit/core/test_prompt_builder.py`
- Modify: `sebastian/capabilities/skills/skill_manager/SKILL.md`

- [x] **Step 1: Write failing prompt tests**

In `tests/unit/core/test_prompt_builder.py`, update `test_system_prompt_includes_skill_management_bootstrap()` with concept-level assertions that avoid depending on a single long sentence:

```python
    assert "reusable domain tasks" in system_prompt
    assert "search local Skills" in system_prompt
    assert "before using browser tools" in system_prompt
    assert "weather" in system_prompt
    assert "天气 weather forecast meteorology" in system_prompt
    assert "Browser tools" in system_prompt
    assert "lowest-priority option" in system_prompt
    assert "explicitly asks for browser interaction" in system_prompt
```

Add one separate test so the policy is not accidentally hidden behind generic wording:

```python
@pytest.mark.asyncio
async def test_skill_management_bootstrap_puts_browser_after_local_skills(
    tmp_path: Path,
) -> None:
    system_prompt = _build_prompt(tmp_path, ["Bash"])

    skill_index = system_prompt.index("search local Skills")
    browser_index = system_prompt.index("Browser tools")

    assert skill_index < browser_index
    assert "If local search returns plausible candidates" in system_prompt
    assert "continue with normal structured tools before browser tools" in system_prompt
```

- [x] **Step 2: Run prompt tests to verify they fail**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py::test_system_prompt_includes_skill_management_bootstrap tests/unit/core/test_prompt_builder.py::test_skill_management_bootstrap_puts_browser_after_local_skills -q
```

Expected: FAIL because the current bootstrap does not explicitly demote browser tools or include weather examples.

- [x] **Step 3: Update `BaseAgent._skill_management_section()`**

In `sebastian/core/base_agent.py`, revise the middle of `_skill_management_section()` to keep the existing CLI command list but strengthen the policy text.

Replace the existing block:

```python
                "When Bash is available, search local Skills before generic tools for "
                "reusable domain tasks. This includes travel, flights, hotels, calendar, "
                "meetings, email, documents, spreadsheets, code, repositories, browser "
                "automation, and other repeatable workflows.",
```

with:

```python
                "When Bash is available, search local Skills before generic tools for "
                "reusable domain tasks. For reusable domain tasks, search local Skills "
                "before using browser tools. This includes weather, travel, flights, "
                "hotels, calendar, meetings, email, documents, spreadsheets, finance, "
                "code, repositories, browser automation, and other repeatable workflows.",
```

After the existing examples, add:

```python
                "Weather examples:",
                '- `sebastian skills search "天气 weather forecast meteorology"`',
```

Replace:

```python
                "If no plausible Skill is found, continue with normal tools.",
```

with:

```python
                "If no plausible Skill is found, continue with normal structured tools "
                "before browser tools.",
                "Browser tools are the lowest-priority option. Use browser tools when "
                "the user explicitly asks for browser interaction, when the task is "
                "inherently about operating a web page, or when local Skills and normal "
                "structured tools cannot solve the task.",
```

Keep the `install`, `update`, and `remove` mutation warning unchanged.

- [x] **Step 4: Extend `skill_manager/SKILL.md`**

In `sebastian/capabilities/skills/skill_manager/SKILL.md`, add a short "Task-solving policy" section after the command reference and before `Rules:`:

```markdown
Task-solving policy:

- For reusable domain tasks, search local installed Skills before using browser tools.
- Use local `show --body` output as the authoritative instructions for using an installed Skill.
- Do not use registry search or inspect output as a substitute for local usage instructions.
- Browser tools are the lowest-priority option. Use them only when the user explicitly asks for browser interaction, when the task is inherently about operating a web page, or when local Skills and normal structured tools cannot solve the task.
- For weather-like requests, prefer a local Skill search such as `sebastian skills search "天气 weather forecast meteorology"` before opening a website.
```

- [x] **Step 5: Run prompt tests to verify they pass**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py::test_system_prompt_includes_skill_management_bootstrap tests/unit/core/test_prompt_builder.py::test_skill_management_bootstrap_puts_browser_after_local_skills -q
```

Expected: PASS.

- [x] **Step 6: Run the full prompt builder slice**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py -q
```

Expected: PASS.

## Task 4: Document Prompt Assembly And Skill-First Behavior

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture/spec/core/system-prompt.md`
- Modify: `sebastian/core/README.md`
- Modify: `sebastian/capabilities/skills/README.md`

- [x] **Step 1: Update changelog**

In `CHANGELOG.md`, add an `[Unreleased]` entry under `### Changed`:

```markdown
- Agent prompts now receive current runtime date/time every turn and prefer local Skill discovery before browser tools for reusable domain tasks.
```

If `### Changed` does not exist in `[Unreleased]`, create it in the documented category order.

- [x] **Step 2: Update system prompt spec frontmatter**

In `docs/architecture/spec/core/system-prompt.md`, bump:

```yaml
version: "1.7"
last_updated: 2026-05-12
status: implemented
```

- [x] **Step 3: Document Runtime Context in section 3**

In `docs/architecture/spec/core/system-prompt.md`, update the prompt construction description so it distinguishes:

- Static base prompt from `build_system_prompt()`.
- Dynamic per-turn sections added in `_stream_inner()`.

Add this text after the `build_system_prompt()` snippet:

```markdown
`build_system_prompt()` only produces the static base prompt. Each LLM turn then builds an
`effective_system_prompt` in `BaseAgent._stream_inner()` by appending dynamic sections:

1. `## Runtime Context` — current server-local date/time, generated fresh per turn.
2. Resident memory snapshot.
3. Dynamic memory retrieval.
4. Session todos.

Runtime Context is intentionally not persisted in session history and not included in
`build_system_prompt()`, because doing so would freeze time at process startup or soul rebuild.
```

- [x] **Step 4: Add section responsibility row**

In the section responsibility table, add:

```markdown
| `_runtime_context_section()` | 每轮动态运行时事实，当前包含服务器本地日期、时间、时区，并声明训练数据不可作为当前时间依据 |
```

- [x] **Step 5: Document Skill-first / browser-last policy**

In `docs/architecture/spec/core/system-prompt.md`, update the Skill Management Bootstrap section to say:

```markdown
For Bash-capable agents, the bootstrap also defines capability selection order for reusable
domain tasks:

1. Search local installed Skills with keyword-style queries.
2. If a plausible Skill exists, read it with `sebastian skills show <name-or-slug> --body`.
3. If no plausible Skill exists, continue with normal structured tools.
4. Use browser tools last, unless the user explicitly asks for browser interaction or the task inherently requires operating a web page.

Weather-like requests are included in this rule; a query such as
`sebastian skills search "天气 weather forecast meteorology"` should be tried before opening a website.
```

- [x] **Step 6: Update core README navigation**

In `sebastian/core/README.md`, update the existing memory-only prompt navigation row to:

```markdown
| 每轮 system prompt 的动态上下文注入（`_runtime_context_section` 注入当前时间；`_resident_memory_section` 注入常驻快照、`_memory_section` 注入动态检索；注入顺序：base → runtime → resident → dynamic → todos） | [base_agent.py](base_agent.py) |
```

- [x] **Step 7: Update skills README**

In `sebastian/capabilities/skills/README.md`, update the `skill_manager` paragraph to clarify:

```markdown
`BaseAgent._skill_management_section()` 是 Bash-capable Agent 每轮默认可见的短 bootstrap，
负责让普通可复用领域任务先查本地 Skill，并把 browser 工具放在最低优先级。内置
`skill_manager` Skill 则负责更完整的 Skill 管理流程，包括 list/show/read/search/inspect/install/update/remove。
```

- [x] **Step 8: Review docs for ambiguity**

Run:

```bash
grep -R "build_system_prompt" -n docs/architecture/spec/core sebastian/core/README.md
grep -R "Browser tools are the lowest-priority\\|browser tools" -n docs/architecture/spec/core/system-prompt.md sebastian/capabilities/skills/README.md sebastian/capabilities/skills/skill_manager/SKILL.md
```

Expected:

- Any `build_system_prompt()` references still describe it as static base prompt construction, not the source of current time.
- Browser guidance consistently says browser tools are last resort after local Skills and normal structured tools.

## Task 5: Verification And Graphify Refresh

**Files:**
- No source file edits expected unless verification exposes a bug.

- [x] **Step 1: Run focused tests**

Run:

```bash
pytest tests/unit/core/test_base_agent.py -q
```

Expected: PASS.

- [x] **Step 2: Run adjacent prompt tests**

Run:

```bash
pytest tests/unit/core/test_prompt_builder.py tests/unit/core/test_base_agent_memory.py tests/unit/test_base_agent_thinking_injection.py -q
```

Expected: PASS.

- [x] **Step 3: Run formatter/linter slice**

Run:

```bash
ruff check sebastian/core/base_agent.py tests/unit/core/test_base_agent.py tests/unit/core/test_prompt_builder.py
ruff format --check sebastian/core/base_agent.py tests/unit/core/test_base_agent.py tests/unit/core/test_prompt_builder.py
```

Expected: PASS.

- [x] **Step 4: Run backend type check**

Run:

```bash
mypy sebastian/
```

Expected: PASS.

- [x] **Step 5: Rebuild graphify code graph**

Run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: command exits successfully and updates graphify outputs if needed.

- [x] **Step 6: Inspect final diff**

Run:

```bash
git diff -- CHANGELOG.md sebastian/core/base_agent.py tests/unit/core/test_base_agent.py tests/unit/core/test_prompt_builder.py sebastian/capabilities/skills/skill_manager/SKILL.md docs/architecture/spec/core/system-prompt.md sebastian/core/README.md sebastian/capabilities/skills/README.md docs/superpowers/plans/2026-05-12-runtime-time-context.md
```

Expected:

- Runtime context is dynamic and not persisted to message history.
- No `current_time` tool exists.
- Local Skill search is explicitly preferred for reusable domain tasks.
- Browser tools are explicitly last resort unless user intent requires browser interaction.
- Docs match the implemented prompt order.
- Existing unrelated dirty files remain untouched.

## Task 6: Commit

**Files:**
- Stage only files changed by this work.

- [x] **Step 1: Check status**

Run:

```bash
git status --short
```

Expected: includes only these task-owned files plus any unrelated pre-existing dirty files:

- `sebastian/core/base_agent.py`
- `tests/unit/core/test_base_agent.py`
- `tests/unit/core/test_prompt_builder.py`
- `sebastian/capabilities/skills/skill_manager/SKILL.md`
- `CHANGELOG.md`
- `docs/architecture/spec/core/system-prompt.md`
- `sebastian/core/README.md`
- `sebastian/capabilities/skills/README.md`
- `docs/superpowers/plans/2026-05-12-runtime-time-context.md`
- possible graphify output files from the rebuild

- [x] **Step 2: Stage task-owned files explicitly**

Run:

```bash
git add CHANGELOG.md sebastian/core/base_agent.py tests/unit/core/test_base_agent.py tests/unit/core/test_prompt_builder.py sebastian/capabilities/skills/skill_manager/SKILL.md docs/architecture/spec/core/system-prompt.md sebastian/core/README.md sebastian/capabilities/skills/README.md docs/superpowers/plans/2026-05-12-runtime-time-context.md
```

If graphify outputs changed, stage only those changed graphify files after reviewing them:

```bash
git add graphify-out/GRAPH_REPORT.md graphify-out/graph.json
```

Do not use `git add .`.

- [x] **Step 3: Commit**

Run:

```bash
git commit -m "feat(core): 优化运行时上下文与技能优先策略" -m "Co-Authored-By: gpt 5.5 <noreply@openai.com>"
```

Expected: commit succeeds with only the task-owned changes.
