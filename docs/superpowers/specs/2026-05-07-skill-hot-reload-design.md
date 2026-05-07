---
version: "1.0"
last_updated: 2026-05-07
status: planned
---

# Skill Hot Reload on New Session Design

## Background

Sebastian already supports skill extension directories:

- Built-in skills: `sebastian/capabilities/skills/`
- User skills: `<data_dir>/extensions/skills/`

At gateway startup, `load_skills()` scans these directories and registers each `SKILL.md`
as a `skill__<name>` capability. This lets users add instruction-based skills without
modifying core code.

The current limitation is lifecycle: skill specs are loaded only at process startup, and
each agent builds `system_prompt` only once during initialization. A user can update a
skill script and have `Bash` execute the latest file, but adding/removing a skill or
editing `SKILL.md` requires restarting Sebastian before the model sees the new skill
instructions.

This matters for script-backed skills such as `flight_search`, where the desired extension
model is:

```text
<data_dir>/extensions/skills/flight_search/
├── SKILL.md
└── scripts/
    └── search_flights.py
```

The skill should be installable and updatable from the user data directory without shipping
a new Sebastian version or growing the internal native tool list.

## Goals

1. Load newly added, changed, or deleted skills without restarting the gateway.
2. Avoid adding a model-visible management tool such as `reload_skills`.
3. Avoid scanning skill directories on every turn.
4. Reload only at a stable lifecycle boundary: before the first turn of a new session.
5. Rebuild only the current agent's prompt when skill specs change.
6. Keep tool specs and the `## Available Skills` prompt section consistent within a turn.
7. Preserve script-backed skill behavior: scripts are executed fresh by `Bash` and do not
   need skill registry reload when their contents change.

## Non-Goals

- No background file watcher.
- No every-turn scan.
- No new model-visible native tool for skill refresh.
- No native `search_flights` tool in core.
- No immediate refresh for existing sessions.
- No fingerprinting of arbitrary files under a skill directory, including `scripts/*.py`.
- No App settings UI or management API for manual refresh in this phase.

## Design Summary

Add an internal `SkillHotReloader` service. It fingerprints all discovered `SKILL.md` files,
reloads skills only when the fingerprint changes, and is invoked before the first LLM turn
of each new agent/session pair.

When a change is detected:

1. Reload skill specs from built-in and user extension directories.
2. Replace the registry's current skill specs atomically.
3. Rebuild only the current agent's `system_prompt`.
4. Continue the turn using the updated prompt and callable skill specs.

The reloader is not exposed to the model. It is runtime infrastructure, not a tool.

## Components

### `SkillHotReloader`

Responsibility: detect `SKILL.md` changes and refresh registry skill specs.

State:

- `builtin_dir: Path`
- `extra_dirs: list[Path]`
- `registry: CapabilityRegistry`
- `_fingerprint: SkillFingerprint | None`
- `_lock: asyncio.Lock`

Public method:

```python
async def maybe_reload(self) -> bool:
    """Return True if skill specs changed and registry was replaced."""
```

Fingerprint input:

- Each discovered `SKILL.md` relative path
- `stat().st_mtime_ns`
- `stat().st_size`

This is intentionally narrow. Editing `scripts/search_flights.py` does not trigger reload;
the script is executed fresh each time by `Bash`.

The first call after startup establishes the fingerprint. Since startup already loads skills,
the first call should normally return `False` unless files changed after startup.

### `CapabilityRegistry.replace_skill_specs()`

Current `register_skill_specs()` appends or overwrites skill entries, but it does not remove
deleted skills. Hot reload needs replacement semantics.

Add:

```python
def replace_skill_specs(self, specs: list[dict[str, Any]]) -> None:
    """Replace all currently registered skill specs with the provided set."""
```

Behavior:

1. Remove all entries whose names are in `_skill_names`.
2. Clear `_skill_names`.
3. Register the new specs using the same skill function behavior as existing registration.

This keeps deleted skills from lingering in the registry.

### Current-Agent Prompt Rebuild

`BaseAgent` currently builds `self.system_prompt` in `__init__`. Add a rebuild hook:

```python
def rebuild_system_prompt(self) -> None:
    self.system_prompt = self.build_system_prompt(self._gate)
```

`Sebastian` already has a specialized `rebuild_system_prompt()` because its prompt includes
the agent registry. It should keep that override:

```python
def rebuild_system_prompt(self) -> None:
    self.system_prompt = self.build_system_prompt(self._gate, self._agent_registry)
```

Only the current agent instance is rebuilt after a skill reload. Other already-created
agents keep their prompt until their own lifecycle path triggers a rebuild.

### New-Session Trigger

Invoke skill hot reload before the first LLM turn of a new agent/session pair.

The trigger should live in `BaseAgent.run_streaming()` after the worker session is resolved
and before memory/todo prompt assembly. That location has access to:

- `session_id`
- current `agent_context`
- current agent instance
- session metadata

Preferred first-turn detection:

- Use persisted session/timeline state if a reliable exchange count or first-turn marker is
  already available.
- If no reliable persisted marker exists, use an in-memory set keyed by
  `(agent_context, session_id)` as the initial implementation.

The in-memory fallback is acceptable because the reloader's fingerprint check is cheap and
idempotent. After process restart, an old session may be treated as unseen once, but reload
still happens only if `SKILL.md` files changed.

Pseudo-flow:

```python
worker_session = await session_store.get_session_for_agent_type(session_id, agent_context)

if self._should_check_skills_for_new_session(worker_session, session_id, agent_context):
    changed = await state.skill_hot_reloader.maybe_reload()
    if changed:
        self.rebuild_system_prompt()
```

The call must complete before the provider request starts.

## Data Flow

```text
User installs or edits SKILL.md
        │
        ▼
User starts a new conversation/session
        │
        ▼
BaseAgent.run_streaming resolves worker session
        │
        ▼
SkillHotReloader fingerprints SKILL.md files
        │
        ├── unchanged → continue with existing prompt
        │
        └── changed
              │
              ▼
        load_skills()
              │
              ▼
        CapabilityRegistry.replace_skill_specs()
              │
              ▼
        current_agent.rebuild_system_prompt()
              │
              ▼
        AgentLoop.stream() fetches callable specs from registry
```

The prompt's `## Available Skills` section and the LLM tool specs are therefore derived from
the same registry state for that turn.

## Concurrency

Multiple new sessions can start at nearly the same time. `SkillHotReloader.maybe_reload()`
uses an async lock so only one scan/reload can mutate the registry at a time.

Inside the lock:

1. Compute latest fingerprint.
2. Compare with cached fingerprint.
3. If unchanged, return `False`.
4. If changed, load and replace skill specs, update cached fingerprint, return `True`.

Readers should not observe a partially updated skill registry because replacement happens
inside one synchronous registry method.

## Error Handling

If reload fails:

- Do not clear existing skill specs.
- Log a warning with enough path/error detail for debugging.
- Continue the current turn using the last known good registry and prompt.

Invalid individual skills should follow existing `load_skills()` behavior. This spec does
not add validation beyond the current loader rules.

## Testing

Unit coverage:

- `SkillHotReloader` returns `False` when fingerprint is unchanged.
- Adding a `SKILL.md` returns `True` and registers the new skill.
- Editing `SKILL.md` returns `True` and updates the skill description/instructions.
- Deleting a skill returns `True` and removes the old skill from registry specs.
- Editing a script file under `scripts/` does not trigger reload.
- Concurrent `maybe_reload()` calls do not produce duplicate or partial registry state.
- `CapabilityRegistry.replace_skill_specs()` removes deleted skills and preserves non-skill MCP/native entries.

Agent-level coverage:

- New session first turn invokes hot reload check.
- Existing session subsequent turn does not invoke hot reload check.
- When reload changes specs, only the current agent's prompt is rebuilt.
- Sebastian's prompt rebuild keeps its sub-agent section.

## Future Work

- Add an App settings refresh button or management API when a skill marketplace exists.
- Add content hashing if `mtime_ns + size` proves unreliable on target filesystems.
- Add persisted first-turn detection if the current session model exposes a stable exchange
  count.
- Add skill installation UX that places skill directories under `<data_dir>/extensions/skills/`.
