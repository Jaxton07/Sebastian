# Sebastian Phase 1 Remaining — File Storage + Session-Centric API + App Supervision

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Sebastian backend from SQLite-centric Task storage to file-based Session-centric storage, rebuild Gateway routes around Sessions, and update the Android App with the SubAgent supervision panel.

**Architecture:** Three sequential mainlines — A (backend file store), B (gateway routes), C (mobile app) — each building on the previous. Session is the first-class entity; Task is a child of Session. All session data lives under `data/sessions/{agent}/{session_id}/` as JSON/JSONL files with a top-level `index.json` for fast listing. SQLite is retained only for Approvals and Users. The dual-path execution model (non-blocking conversation + async tasks) is preserved unchanged.

**Tech Stack:** Python 3.12+, aiofiles, FastAPI, Pydantic v2, React Native, Zustand, React Query, TypeScript

---

## File Map

### New files (backend)
```
sebastian/store/session_store.py     ← SessionStore: all file I/O for sessions, messages, tasks, checkpoints
sebastian/store/index_store.py       ← IndexStore: read/write data/sessions/index.json
sebastian/gateway/routes/sessions.py ← new session-centric routes
tests/unit/test_session_store.py
tests/integration/test_gateway_sessions.py
```

### Modified files (backend)
```
sebastian/core/types.py              ← add Session, SessionStatus; add session_id to Task; remove checkpoints list from Task
sebastian/store/models.py            ← remove TurnRecord, TaskRecord, CheckpointRecord (keep ApprovalRecord, UserRecord)
sebastian/store/database.py          ← no change needed
sebastian/store/task_store.py        ← delete (replaced by session_store.py)
sebastian/memory/episodic_memory.py  ← replace SQLite with file-based reads from session_store
sebastian/core/base_agent.py         ← swap EpisodicMemory calls to SessionStore
sebastian/orchestrator/sebas.py      ← pass session_store instead of session_factory where applicable; add intervene()
sebastian/core/task_manager.py       ← swap TaskStore → SessionStore; accept session_id
sebastian/gateway/state.py           ← add session_store singleton
sebastian/gateway/app.py             ← wire session_store; add sessions router; remove tasks router
sebastian/gateway/routes/turns.py    ← keep POST /turns (Sebastian main entry); remove GET /turns/{id}
sebastian/gateway/routes/tasks.py    ← delete
sebastian/protocol/events/types.py  ← add USER_INTERVENED event
sebastian/config/__init__.py         ← add sessions_dir property
```

### New files (mobile)
```
ui/mobile/src/api/sessions.ts           ← getSessions, getSession, getAgentSessions, sendTurnToSession
ui/mobile/src/components/subagents/SessionList.tsx
ui/mobile/src/components/subagents/SessionDetailView.tsx
ui/mobile/app/(tabs)/subagents/session/[id].tsx   ← session detail screen
```

### Modified files (mobile)
```
ui/mobile/src/types.ts                  ← extend SessionMeta (agent, status, active_task_count, updated_at)
ui/mobile/src/api/turns.ts             ← remove getSessions/getMessages (moved to sessions.ts)
ui/mobile/src/store/session.ts         ← add agent field to SessionMeta
ui/mobile/app/(tabs)/subagents/index.tsx ← replace agent output view with session list
ui/mobile/src/store/approval.ts        ← wire to real approvals API
ui/mobile/app/_layout.tsx              ← add approval modal to root layout
```

---

## Mainline A — Backend File Storage

### Task 1: Add Session and SessionStatus types; add session_id to Task

**Files:**
- Modify: `sebastian/core/types.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_core_types.py  (append to existing file)
def test_session_defaults() -> None:
    from sebastian.core.types import Session, SessionStatus
    s = Session(agent="sebastian", title="Test")
    assert s.status == SessionStatus.ACTIVE
    assert s.agent == "sebastian"
    assert "/" not in s.id  # id must be filesystem-safe


def test_task_has_session_id() -> None:
    from sebastian.core.types import Task
    t = Task(goal="do something", session_id="abc")
    assert t.session_id == "abc"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_core_types.py -v
```
Expected: `ImportError` or `AttributeError` — Session/SessionStatus not defined yet.

- [ ] **Step 3: Add Session, SessionStatus to types.py**

Open `sebastian/core/types.py`. Add after the `TaskStatus` class:

```python
class SessionStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    ARCHIVED = "archived"
```

Add after the `Task` class:

```python
class Session(BaseModel):
    id: str = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
            + "_"
            + uuid.uuid4().hex[:6]
        )
    )
    agent: str                          # "sebastian" or subagent name
    title: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_count: int = 0
    active_task_count: int = 0
```

In the `Task` class, add `session_id` field and remove `checkpoints` field:

```python
class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str                      # owning session
    goal: str
    plan: TaskPlan | None = None
    status: TaskStatus = TaskStatus.CREATED
    assigned_agent: str = "sebastian"
    parent_task_id: str | None = None
    resource_budget: ResourceBudget = Field(default_factory=ResourceBudget)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    # checkpoints stored separately in task_<id>.jsonl — not inlined here
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_core_types.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sebastian/core/types.py tests/unit/test_core_types.py
git commit -m "feat(core): add Session/SessionStatus types; add session_id to Task"
```

---

### Task 2: Add sessions_dir to config

**Files:**
- Modify: `sebastian/config/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_config.py  (append)
def test_sessions_dir_derived_from_data_dir() -> None:
    from sebastian.config import settings
    from pathlib import Path
    assert settings.sessions_dir == Path(settings.sebastian_data_dir) / "sessions"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_config.py::test_sessions_dir_derived_from_data_dir -v
```
Expected: `AttributeError`.

- [ ] **Step 3: Add sessions_dir property**

In `sebastian/config/__init__.py`, add inside the `Settings` class after the `database_url` property:

```python
@property
def sessions_dir(self) -> Path:
    return Path(self.sebastian_data_dir) / "sessions"
```

Also update `ensure_data_dir`:

```python
def ensure_data_dir() -> None:
    """Create the data directory and sessions subdirectory. Call once at startup."""
    data = Path(settings.sebastian_data_dir)
    data.mkdir(parents=True, exist_ok=True)
    (data / "sessions").mkdir(exist_ok=True)
    (data / "sessions" / "sebastian").mkdir(exist_ok=True)
    (data / "sessions" / "subagents").mkdir(exist_ok=True)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_config.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sebastian/config/__init__.py tests/unit/test_config.py
git commit -m "feat(config): add sessions_dir property and ensure sessions subdirs"
```

---

### Task 3: Implement IndexStore

**Files:**
- Create: `sebastian/store/index_store.py`
- Create: `tests/unit/test_index_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_index_store.py
from __future__ import annotations
import json
import pytest
from pathlib import Path
from sebastian.store.index_store import IndexStore
from sebastian.core.types import Session


@pytest.fixture
def tmp_sessions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions"
    d.mkdir()
    return d


@pytest.mark.asyncio
async def test_upsert_and_list(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    s = Session(agent="sebastian", title="Hello")
    await store.upsert(s)
    sessions = await store.list_all()
    assert len(sessions) == 1
    assert sessions[0]["id"] == s.id
    assert sessions[0]["agent"] == "sebastian"


@pytest.mark.asyncio
async def test_upsert_updates_existing(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    s = Session(agent="sebastian", title="Original")
    await store.upsert(s)
    s.title = "Updated"
    await store.upsert(s)
    sessions = await store.list_all()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Updated"


@pytest.mark.asyncio
async def test_list_by_agent(tmp_sessions_dir: Path) -> None:
    store = IndexStore(tmp_sessions_dir)
    s1 = Session(agent="sebastian", title="Chat 1")
    s2 = Session(agent="stock", title="Stock 1")
    await store.upsert(s1)
    await store.upsert(s2)
    results = await store.list_by_agent("stock")
    assert len(results) == 1
    assert results[0]["agent"] == "stock"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_index_store.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement IndexStore**

Create `sebastian/store/index_store.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles

from sebastian.core.types import Session

INDEX_FILE = "index.json"
_LOCK = asyncio.Lock()


class IndexStore:
    """Reads and writes data/sessions/index.json.
    All mutations are serialised through an asyncio lock to prevent races.
    """

    def __init__(self, sessions_dir: Path) -> None:
        self._path = sessions_dir / INDEX_FILE

    async def _read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        async with aiofiles.open(self._path) as f:
            raw = await f.read()
        data = json.loads(raw)
        return data.get("sessions", [])

    async def _write(self, sessions: list[dict[str, Any]]) -> None:
        payload = json.dumps({"version": 1, "sessions": sessions}, default=str)
        async with aiofiles.open(self._path, "w") as f:
            await f.write(payload)

    async def upsert(self, session: Session) -> None:
        async with _LOCK:
            sessions = await self._read()
            entry = {
                "id": session.id,
                "agent": session.agent,
                "title": session.title,
                "status": session.status.value,
                "updated_at": session.updated_at.isoformat(),
                "task_count": session.task_count,
                "active_task_count": session.active_task_count,
            }
            sessions = [s for s in sessions if s["id"] != session.id]
            sessions.insert(0, entry)
            await self._write(sessions)

    async def list_all(self) -> list[dict[str, Any]]:
        return await self._read()

    async def list_by_agent(self, agent: str) -> list[dict[str, Any]]:
        return [s for s in await self._read() if s["agent"] == agent]

    async def remove(self, session_id: str) -> None:
        async with _LOCK:
            sessions = await self._read()
            sessions = [s for s in sessions if s["id"] != session_id]
            await self._write(sessions)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_index_store.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sebastian/store/index_store.py tests/unit/test_index_store.py
git commit -m "feat(store): implement IndexStore for data/sessions/index.json"
```

---

### Task 4: Implement SessionStore

**Files:**
- Create: `sebastian/store/session_store.py`
- Create: `tests/unit/test_session_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_session_store.py
from __future__ import annotations
import pytest
from pathlib import Path
from sebastian.store.session_store import SessionStore
from sebastian.core.types import Session, Task, TaskStatus, Checkpoint


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    return SessionStore(sessions_dir)


@pytest.mark.asyncio
async def test_create_and_get_session(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Hello world")
    await store.create_session(s)
    loaded = await store.get_session(s.id)
    assert loaded is not None
    assert loaded.title == "Hello world"
    assert loaded.agent == "sebastian"


@pytest.mark.asyncio
async def test_append_and_get_messages(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Test")
    await store.create_session(s)
    await store.append_message(s.id, "user", "Hello")
    await store.append_message(s.id, "assistant", "Hi there")
    msgs = await store.get_messages(s.id)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_create_and_get_task(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Task test")
    await store.create_session(s)
    t = Task(session_id=s.id, goal="Research stocks")
    await store.create_task(t)
    loaded = await store.get_task(s.id, t.id)
    assert loaded is not None
    assert loaded.goal == "Research stocks"
    assert loaded.session_id == s.id


@pytest.mark.asyncio
async def test_update_task_status(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Status test")
    await store.create_session(s)
    t = Task(session_id=s.id, goal="Do thing")
    await store.create_task(t)
    await store.update_task_status(s.id, t.id, TaskStatus.RUNNING)
    loaded = await store.get_task(s.id, t.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_append_checkpoint(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Checkpoint test")
    await store.create_session(s)
    t = Task(session_id=s.id, goal="Step task")
    await store.create_task(t)
    cp = Checkpoint(task_id=t.id, step=1, data={"result": "ok"})
    await store.append_checkpoint(s.id, cp)
    cps = await store.get_checkpoints(s.id, t.id)
    assert len(cps) == 1
    assert cps[0].step == 1


@pytest.mark.asyncio
async def test_list_tasks(store: SessionStore) -> None:
    s = Session(agent="sebastian", title="Multi task")
    await store.create_session(s)
    t1 = Task(session_id=s.id, goal="Task A")
    t2 = Task(session_id=s.id, goal="Task B")
    await store.create_task(t1)
    await store.create_task(t2)
    tasks = await store.list_tasks(s.id)
    assert len(tasks) == 2
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_session_store.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement SessionStore**

Create `sebastian/store/session_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles

from sebastian.core.types import (
    Checkpoint,
    ResourceBudget,
    Session,
    SessionStatus,
    Task,
    TaskPlan,
    TaskStatus,
)


def _session_dir(sessions_dir: Path, session: Session) -> Path:
    """Return the directory for a session, creating it if needed."""
    if session.agent == "sebastian":
        d = sessions_dir / "sebastian" / session.id
    else:
        d = sessions_dir / "subagents" / session.agent / session.id
    d.mkdir(parents=True, exist_ok=True)
    (d / "tasks").mkdir(exist_ok=True)
    return d


def _session_dir_by_id(sessions_dir: Path, session_id: str, agent: str) -> Path:
    if agent == "sebastian":
        return sessions_dir / "sebastian" / session_id
    return sessions_dir / "subagents" / agent / session_id


class SessionStore:
    """File-based storage for Sessions, messages, Tasks and checkpoints.

    Directory layout per session:
        data/sessions/{agent}/{session_id}/
            meta.json
            messages.jsonl       (append-only)
            tasks/
                {task_id}.json   (task meta + status)
                {task_id}.jsonl  (checkpoint stream, append-only)
    """

    def __init__(self, sessions_dir: Path) -> None:
        self._dir = sessions_dir

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    async def create_session(self, session: Session) -> Session:
        d = _session_dir(self._dir, session)
        meta_path = d / "meta.json"
        async with aiofiles.open(meta_path, "w") as f:
            await f.write(session.model_dump_json())
        return session

    async def get_session(self, session_id: str, agent: str = "sebastian") -> Session | None:
        d = _session_dir_by_id(self._dir, session_id, agent)
        meta_path = d / "meta.json"
        if not meta_path.exists():
            return None
        async with aiofiles.open(meta_path) as f:
            raw = await f.read()
        data = json.loads(raw)
        return Session(**data)

    async def update_session(self, session: Session) -> None:
        d = _session_dir_by_id(self._dir, session.id, session.agent)
        meta_path = d / "meta.json"
        async with aiofiles.open(meta_path, "w") as f:
            await f.write(session.model_dump_json())

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def append_message(self, session_id: str, role: str, content: str, agent: str = "sebastian") -> None:
        d = _session_dir_by_id(self._dir, session_id, agent)
        msg = json.dumps({
            "role": role,
            "content": content,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        async with aiofiles.open(d / "messages.jsonl", "a") as f:
            await f.write(msg + "\n")

    async def get_messages(self, session_id: str, agent: str = "sebastian", limit: int = 50) -> list[dict[str, Any]]:
        d = _session_dir_by_id(self._dir, session_id, agent)
        path = d / "messages.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path) as f:
            lines = await f.readlines()
        msgs = [json.loads(l) for l in lines if l.strip()]
        return msgs[-limit:]

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def create_task(self, task: Task) -> Task:
        d = _session_dir_by_id(self._dir, task.session_id, task.assigned_agent)
        tasks_dir = d / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        async with aiofiles.open(tasks_dir / f"{task.id}.json", "w") as f:
            await f.write(task.model_dump_json())
        return task

    async def get_task(self, session_id: str, task_id: str, agent: str = "sebastian") -> Task | None:
        d = _session_dir_by_id(self._dir, session_id, agent)
        path = d / "tasks" / f"{task_id}.json"
        if not path.exists():
            return None
        async with aiofiles.open(path) as f:
            raw = await f.read()
        return _task_from_dict(json.loads(raw))

    async def list_tasks(self, session_id: str, agent: str = "sebastian") -> list[Task]:
        d = _session_dir_by_id(self._dir, session_id, agent)
        tasks_dir = d / "tasks"
        if not tasks_dir.exists():
            return []
        tasks = []
        for p in sorted(tasks_dir.glob("*.json")):
            async with aiofiles.open(p) as f:
                raw = await f.read()
            tasks.append(_task_from_dict(json.loads(raw)))
        return tasks

    async def update_task_status(self, session_id: str, task_id: str, status: TaskStatus, agent: str = "sebastian") -> None:
        task = await self.get_task(session_id, task_id, agent)
        if task is None:
            return
        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.now(timezone.utc)
        d = _session_dir_by_id(self._dir, session_id, agent)
        async with aiofiles.open(d / "tasks" / f"{task_id}.json", "w") as f:
            await f.write(task.model_dump_json())

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    async def append_checkpoint(self, session_id: str, checkpoint: Checkpoint, agent: str = "sebastian") -> None:
        d = _session_dir_by_id(self._dir, session_id, agent)
        path = d / "tasks" / f"{checkpoint.task_id}.jsonl"
        line = json.dumps(checkpoint.model_dump(mode="json"))
        async with aiofiles.open(path, "a") as f:
            await f.write(line + "\n")

    async def get_checkpoints(self, session_id: str, task_id: str, agent: str = "sebastian") -> list[Checkpoint]:
        d = _session_dir_by_id(self._dir, session_id, agent)
        path = d / "tasks" / f"{task_id}.jsonl"
        if not path.exists():
            return []
        async with aiofiles.open(path) as f:
            lines = await f.readlines()
        return [Checkpoint(**json.loads(l)) for l in lines if l.strip()]


def _task_from_dict(data: dict[str, Any]) -> Task:
    return Task(
        id=data["id"],
        session_id=data["session_id"],
        goal=data["goal"],
        status=TaskStatus(data["status"]),
        assigned_agent=data.get("assigned_agent", "sebastian"),
        parent_task_id=data.get("parent_task_id"),
        plan=TaskPlan(**data["plan"]) if data.get("plan") else None,
        resource_budget=ResourceBudget(**data.get("resource_budget", {})),
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
        completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_session_store.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add sebastian/store/session_store.py tests/unit/test_session_store.py
git commit -m "feat(store): implement file-based SessionStore"
```

---

### Task 5: Wire TaskManager to SessionStore; drop SQLite task/turn storage

**Files:**
- Modify: `sebastian/core/task_manager.py`
- Modify: `sebastian/core/base_agent.py`
- Modify: `sebastian/memory/episodic_memory.py`
- Modify: `sebastian/store/models.py`

- [ ] **Step 1: Update TaskManager**

Replace the entire content of `sebastian/core/task_manager.py`:

```python
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

from sebastian.core.types import Task, TaskStatus
from sebastian.protocol.events.bus import EventBus
from sebastian.protocol.events.types import Event, EventType
from sebastian.store.session_store import SessionStore

logger = logging.getLogger(__name__)

TaskFn = Callable[[Task], Awaitable[None]]


class TaskManager:
    """Submits tasks for async background execution. Persists to SessionStore."""

    def __init__(self, session_store: SessionStore, event_bus: EventBus) -> None:
        self._store = session_store
        self._bus = event_bus
        self._running: dict[str, asyncio.Task] = {}

    async def submit(self, task: Task, fn: TaskFn) -> None:
        await self._store.create_task(task)
        await self._bus.publish(Event(
            type=EventType.TASK_CREATED,
            data={"task_id": task.id, "session_id": task.session_id, "goal": task.goal, "assigned_agent": task.assigned_agent},
        ))

        async def _run() -> None:
            await self._store.update_task_status(task.session_id, task.id, TaskStatus.RUNNING, task.assigned_agent)
            await self._bus.publish(Event(type=EventType.TASK_STARTED, data={"task_id": task.id}))
            try:
                await fn(task)
                await self._store.update_task_status(task.session_id, task.id, TaskStatus.COMPLETED, task.assigned_agent)
                await self._bus.publish(Event(type=EventType.TASK_COMPLETED, data={"task_id": task.id}))
            except asyncio.CancelledError:
                await self._store.update_task_status(task.session_id, task.id, TaskStatus.CANCELLED, task.assigned_agent)
                await self._bus.publish(Event(type=EventType.TASK_CANCELLED, data={"task_id": task.id}))
            except Exception as exc:
                logger.exception("Task %s failed", task.id)
                await self._store.update_task_status(task.session_id, task.id, TaskStatus.FAILED, task.assigned_agent)
                await self._bus.publish(Event(type=EventType.TASK_FAILED, data={"task_id": task.id, "error": str(exc)}))
            finally:
                self._running.pop(task.id, None)

        self._running[task.id] = asyncio.create_task(_run())

    async def cancel(self, task_id: str) -> bool:
        t = self._running.get(task_id)
        if t is None:
            return False
        t.cancel()
        return True

    def is_running(self, task_id: str) -> bool:
        return task_id in self._running
```

- [ ] **Step 2: Update EpisodicMemory to read from SessionStore**

Replace entire `sebastian/memory/episodic_memory.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sebastian.store.session_store import SessionStore


@dataclass
class TurnEntry:
    role: str
    content: str
    ts: str


class EpisodicMemory:
    """Conversation history backed by file-based SessionStore."""

    def __init__(self, session_store: SessionStore) -> None:
        self._store = session_store

    async def add_turn(self, session_id: str, role: str, content: str, agent: str = "sebastian") -> TurnEntry:
        await self._store.append_message(session_id, role, content, agent)
        from datetime import timezone
        return TurnEntry(role=role, content=content, ts=datetime.now(timezone.utc).isoformat())

    async def get_turns(self, session_id: str, agent: str = "sebastian", limit: int = 50) -> list[TurnEntry]:
        msgs = await self._store.get_messages(session_id, agent, limit)
        return [TurnEntry(role=m["role"], content=m["content"], ts=m.get("ts", "")) for m in msgs]
```

- [ ] **Step 3: Update BaseAgent to use SessionStore + EpisodicMemory**

In `sebastian/core/base_agent.py`, change the `__init__` signature and `run` method:

```python
from __future__ import annotations
import logging
from abc import ABC
from typing import Any

import anthropic

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.agent_loop import AgentLoop
from sebastian.memory.episodic_memory import EpisodicMemory
from sebastian.memory.working_memory import WorkingMemory
from sebastian.store.session_store import SessionStore

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = (
    "You are Sebastian, a personal AI butler. You are helpful, precise, and action-oriented. "
    "You have access to tools and will use them when needed. "
    "Think step by step, act efficiently, and always confirm important actions before executing."
)


class BaseAgent(ABC):
    name: str = "base_agent"
    system_prompt: str = BASE_SYSTEM_PROMPT

    def __init__(
        self,
        registry: CapabilityRegistry,
        session_store: SessionStore,
        model: str | None = None,
    ) -> None:
        self._registry = registry
        self._session_store = session_store
        self._episodic = EpisodicMemory(session_store)
        self.working_memory = WorkingMemory()

        from sebastian.config import settings
        resolved_model = model or settings.sebastian_model
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._loop = AgentLoop(self._client, registry, resolved_model)

    async def run(self, user_message: str, session_id: str, task_id: str | None = None) -> str:
        turns = await self._episodic.get_turns(session_id, agent=self.name)
        messages: list[dict[str, Any]] = [{"role": t.role, "content": t.content} for t in turns]
        messages.append({"role": "user", "content": user_message})

        response = await self._loop.run(
            system_prompt=self.system_prompt,
            messages=messages,
            task_id=task_id,
        )

        await self._episodic.add_turn(session_id, "user", user_message, agent=self.name)
        await self._episodic.add_turn(session_id, "assistant", response, agent=self.name)
        return response
```

- [ ] **Step 4: Remove TurnRecord, TaskRecord, CheckpointRecord from models.py**

In `sebastian/store/models.py`, delete `TurnRecord`, `TaskRecord`, `CheckpointRecord`. Keep only `ApprovalRecord` and `UserRecord`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sebastian.store.database import Base  # noqa: F401


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, index=True, default="")
    tool_name: Mapped[str] = mapped_column(String(100))
    tool_input: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 5: Run all existing tests to find and fix any import breakage**

```bash
pytest tests/unit/ -v 2>&1 | head -60
```

Fix any import errors from the removed SQLAlchemy session dependency in tests. The `conftest.py` `db_session` fixture is still valid (used by approval tests). Remove the `db_session` fixture usage from `test_task_store.py` — that file tests the old TaskStore, which no longer exists. Delete it:

```bash
rm tests/unit/test_task_store.py
```

- [ ] **Step 6: Run tests again**

```bash
pytest tests/unit/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add sebastian/core/task_manager.py sebastian/core/base_agent.py \
        sebastian/memory/episodic_memory.py sebastian/store/models.py
git rm tests/unit/test_task_store.py
git commit -m "refactor(store): wire TaskManager+BaseAgent to SessionStore; drop SQLite turn/task storage"
```

---

### Task 6: Update Sebastian orchestrator; add USER_INTERVENED event

**Files:**
- Modify: `sebastian/orchestrator/sebas.py`
- Modify: `sebastian/gateway/state.py`
- Modify: `sebastian/protocol/events/types.py`

- [ ] **Step 1: Add USER_INTERVENED to EventType**

In `sebastian/protocol/events/types.py`, add inside the `EventType` class after `USER_INTERRUPTED`:

```python
USER_INTERVENED = "user.intervened"   # user sent correction directly to a SubAgent
```

- [ ] **Step 2: Update Sebastian to use SessionStore**

Replace `sebastian/orchestrator/sebas.py`:

```python
from __future__ import annotations
import logging
from datetime import timezone, datetime
from typing import Any

from sebastian.capabilities.registry import CapabilityRegistry
from sebastian.core.base_agent import BaseAgent
from sebastian.core.task_manager import TaskManager
from sebastian.core.types import Session, Task
from sebastian.orchestrator.conversation import ConversationManager
from sebastian.protocol.events.bus import EventBus
from sebastian.protocol.events.types import Event, EventType
from sebastian.store.index_store import IndexStore
from sebastian.store.session_store import SessionStore

logger = logging.getLogger(__name__)

SEBASTIAN_SYSTEM_PROMPT = """You are Sebastian — an elegant, capable personal AI butler.
Your purpose: receive instructions, plan effectively, and execute precisely.
You have access to tools. Use them to fulfill requests completely.
For complex multi-step tasks, break them down and execute step by step.
When you encounter a decision that requires the user's input, ask clearly and concisely.
You never fabricate results — if a tool fails, say so and suggest alternatives."""


class Sebastian(BaseAgent):
    name = "sebastian"
    system_prompt = SEBASTIAN_SYSTEM_PROMPT

    def __init__(
        self,
        registry: CapabilityRegistry,
        session_store: SessionStore,
        index_store: IndexStore,
        task_manager: TaskManager,
        conversation: ConversationManager,
        event_bus: EventBus,
    ) -> None:
        super().__init__(registry, session_store)
        self._index = index_store
        self._task_manager = task_manager
        self._conversation = conversation
        self._event_bus = event_bus

    async def chat(self, user_message: str, session_id: str) -> str:
        """Handle a conversational turn with Sebastian."""
        await self._event_bus.publish(Event(
            type=EventType.TURN_RECEIVED,
            data={"session_id": session_id, "message": user_message[:200]},
        ))
        response = await self.run(user_message, session_id)
        await self._event_bus.publish(Event(
            type=EventType.TURN_RESPONSE,
            data={"session_id": session_id, "response": response[:200]},
        ))
        return response

    async def get_or_create_session(self, session_id: str | None, first_message: str) -> Session:
        """Return existing session or create a new one; upsert into index."""
        if session_id:
            existing = await self._session_store.get_session(session_id, agent="sebastian")
            if existing:
                existing.updated_at = datetime.now(timezone.utc)
                await self._session_store.update_session(existing)
                await self._index.upsert(existing)
                return existing
        session = Session(agent="sebastian", title=first_message[:40])
        await self._session_store.create_session(session)
        await self._index.upsert(session)
        return session

    async def intervene(self, agent_name: str, session_id: str, message: str) -> str:
        """User directly sends a correction to a SubAgent session. Notifies Sebastian silently."""
        response = await self.run(message, session_id)  # placeholder: routes to agent in Phase 2
        await self._event_bus.publish(Event(
            type=EventType.USER_INTERVENED,
            data={"agent": agent_name, "session_id": session_id, "message": message[:200]},
        ))
        return response

    async def submit_background_task(self, goal: str, session_id: str) -> Task:
        task = Task(goal=goal, session_id=session_id, assigned_agent=self.name)

        async def execute(t: Task) -> None:
            await self.run(t.goal, session_id=session_id, task_id=t.id)

        await self._task_manager.submit(task, execute)
        return task
```

- [ ] **Step 3: Update gateway state**

Replace `sebastian/gateway/state.py`:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.gateway.sse import SSEManager
    from sebastian.protocol.events.bus import EventBus
    from sebastian.orchestrator.conversation import ConversationManager
    from sebastian.store.session_store import SessionStore
    from sebastian.store.index_store import IndexStore
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

sebastian: "Sebastian"
sse_manager: "SSEManager"
event_bus: "EventBus"
conversation: "ConversationManager"
session_store: "SessionStore"
index_store: "IndexStore"
db_factory: "async_sessionmaker[AsyncSession]"   # SQLite, approvals/users only
```

- [ ] **Step 4: Update gateway lifespan in app.py**

In `sebastian/gateway/app.py`, replace the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import sebastian.gateway.state as state
    from sebastian.capabilities.registry import registry
    from sebastian.capabilities.tools._loader import load_tools
    from sebastian.capabilities.mcps._loader import load_mcps, connect_all
    from sebastian.core.task_manager import TaskManager
    from sebastian.gateway.sse import SSEManager
    from sebastian.orchestrator.conversation import ConversationManager
    from sebastian.orchestrator.sebas import Sebastian
    from sebastian.protocol.events.bus import bus
    from sebastian.store.database import get_session_factory, init_db
    from sebastian.store.session_store import SessionStore
    from sebastian.store.index_store import IndexStore
    from sebastian.config import ensure_data_dir, settings

    ensure_data_dir()
    await init_db()

    db_factory = get_session_factory()
    session_store = SessionStore(settings.sessions_dir)
    index_store = IndexStore(settings.sessions_dir)

    load_tools()
    mcp_clients = load_mcps()
    if mcp_clients:
        await connect_all(mcp_clients, registry)

    event_bus = bus
    conversation = ConversationManager(event_bus)
    task_manager = TaskManager(session_store, event_bus)
    sse_mgr = SSEManager(event_bus)
    sebastian_agent = Sebastian(
        registry=registry,
        session_store=session_store,
        index_store=index_store,
        task_manager=task_manager,
        conversation=conversation,
        event_bus=event_bus,
    )

    state.sebastian = sebastian_agent
    state.sse_manager = sse_mgr
    state.event_bus = event_bus
    state.conversation = conversation
    state.session_store = session_store
    state.index_store = index_store
    state.db_factory = db_factory

    logger.info("Sebastian gateway started")
    yield
    logger.info("Sebastian gateway shutdown")
```

Also update `create_app` to replace tasks router with sessions router (written in Task 7):

```python
def create_app() -> FastAPI:
    from sebastian.gateway.routes import agents, approvals, stream, turns, sessions

    app = FastAPI(title="Sebastian Gateway", version="0.1.0", lifespan=lifespan)
    app.include_router(turns.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(stream.router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")
    return app
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/ -v
```
Expected: all pass. Fix any import errors if test files still reference removed items.

- [ ] **Step 6: Commit**

```bash
git add sebastian/protocol/events/types.py sebastian/orchestrator/sebas.py \
        sebastian/gateway/state.py sebastian/gateway/app.py
git commit -m "feat(orchestrator): wire Sebastian to SessionStore+IndexStore; add USER_INTERVENED event"
```

---

## Mainline B — Gateway Routes

### Task 7: Implement session-centric routes; update turns route

**Files:**
- Create: `sebastian/gateway/routes/sessions.py`
- Modify: `sebastian/gateway/routes/turns.py`
- Delete: `sebastian/gateway/routes/tasks.py`

- [ ] **Step 1: Create sessions router**

Create `sebastian/gateway/routes/sessions.py`:

```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions(_auth: dict = Depends(require_auth)) -> dict:
    """Return the global session index."""
    import sebastian.gateway.state as state
    sessions = await state.index_store.list_all()
    return {"sessions": sessions}


@router.get("/agents/{agent}/sessions")
async def list_agent_sessions(agent: str, _auth: dict = Depends(require_auth)) -> dict:
    """Return sessions for a specific agent (Sebastian or a SubAgent)."""
    import sebastian.gateway.state as state
    sessions = await state.index_store.list_by_agent(agent)
    return {"agent": agent, "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, agent: str = "sebastian", _auth: dict = Depends(require_auth)) -> dict:
    """Return session meta + last 50 messages."""
    import sebastian.gateway.state as state
    session = await state.session_store.get_session(session_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await state.session_store.get_messages(session_id, agent, limit=50)
    return {"session": session.model_dump(mode="json"), "messages": messages}


class SendTurnBody(BaseModel):
    content: str


@router.post("/sessions/{session_id}/turns")
async def send_turn_to_session(
    session_id: str,
    body: SendTurnBody,
    agent: str = "sebastian",
    _auth: dict = Depends(require_auth),
) -> dict:
    """Send a message (or correction) to any session. Used for SubAgent supervision."""
    import sebastian.gateway.state as state
    from datetime import datetime, timezone

    session = await state.session_store.get_session(session_id, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if agent == "sebastian":
        response = await state.sebastian.chat(body.content, session_id)
    else:
        response = await state.sebastian.intervene(agent, session_id, body.content)

    session.updated_at = datetime.now(timezone.utc)
    await state.session_store.update_session(session)
    await state.index_store.upsert(session)

    return {
        "session_id": session_id,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sessions/{session_id}/tasks")
async def list_session_tasks(
    session_id: str,
    agent: str = "sebastian",
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    tasks = await state.session_store.list_tasks(session_id, agent)
    return {"tasks": [t.model_dump(mode="json") for t in tasks]}


@router.post("/sessions/{session_id}/tasks/{task_id}/pause")
async def pause_task(
    session_id: str,
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "paused": cancelled}


@router.delete("/sessions/{session_id}/tasks/{task_id}")
async def cancel_task(
    session_id: str,
    task_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    cancelled = await state.sebastian._task_manager.cancel(task_id)
    return {"task_id": task_id, "cancelled": cancelled}
```

- [ ] **Step 2: Simplify turns.py — keep POST /turns as Sebastian main entry**

Replace `sebastian/gateway/routes/turns.py`:

```python
from __future__ import annotations
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sebastian.gateway.auth import create_access_token, require_auth, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(tags=["turns"])


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SendTurnRequest(BaseModel):
    content: str
    session_id: str | None = None


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    from sebastian.config import settings
    stored_hash = settings.sebastian_owner_password_hash
    if not stored_hash or not verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_access_token({"sub": settings.sebastian_owner_name, "role": "owner"})
    return TokenResponse(access_token=token)


@router.post("/turns")
async def send_turn(
    body: SendTurnRequest,
    _auth: dict = Depends(require_auth),
) -> dict:
    """Send a message to Sebastian. Creates a new session if session_id is None."""
    import sebastian.gateway.state as state
    session = await state.sebastian.get_or_create_session(body.session_id, body.content)
    response = await state.sebastian.chat(body.content, session.id)
    return {
        "session_id": session.id,
        "response": response,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 3: Delete tasks.py**

```bash
git rm sebastian/gateway/routes/tasks.py
```

- [ ] **Step 4: Write integration test**

Create `tests/integration/test_gateway_sessions.py`:

```python
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_state(tmp_path):
    """Patch gateway state with file-based stores backed by tmp_path."""
    from pathlib import Path
    from sebastian.store.session_store import SessionStore
    from sebastian.store.index_store import IndexStore

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "sebastian").mkdir()
    (sessions_dir / "subagents").mkdir()

    store = SessionStore(sessions_dir)
    idx = IndexStore(sessions_dir)

    sebastian_mock = MagicMock()
    sebastian_mock.chat = AsyncMock(return_value="Hello!")
    sebastian_mock.get_or_create_session = AsyncMock()

    from sebastian.core.types import Session
    fake_session = Session(agent="sebastian", title="Test")
    sebastian_mock.get_or_create_session.return_value = fake_session

    with patch("sebastian.gateway.routes.turns.sebastian", sebastian_mock), \
         patch("sebastian.gateway.routes.sessions.state") as mock_s:
        mock_s.index_store = idx
        mock_s.session_store = store
        mock_s.sebastian = sebastian_mock
        yield {"session": fake_session, "store": store, "index": idx}


@pytest.mark.asyncio
async def test_list_sessions_empty() -> None:
    from sebastian.gateway.app import create_app
    import sebastian.gateway.state as state
    from pathlib import Path
    from sebastian.store.session_store import SessionStore
    from sebastian.store.index_store import IndexStore
    from unittest.mock import patch, AsyncMock, MagicMock

    tmp = Path("/tmp/test_sessions_empty")
    tmp.mkdir(parents=True, exist_ok=True)
    idx = IndexStore(tmp)

    with patch.object(state, "index_store", idx), \
         patch("sebastian.gateway.app.lifespan", return_value=AsyncMock().__aenter__()):
        app = create_app()
        with patch("sebastian.gateway.routes.sessions.state", state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # unauthenticated → 401
                resp = await client.get("/api/v1/sessions")
                assert resp.status_code == 401
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -v -k "not test_gateway_turns and not test_gateway_tasks" 2>&1 | tail -20
```
Expected: all pass. The old gateway tests for turns/tasks will be updated in the next step.

- [ ] **Step 6: Update old integration tests**

In `tests/integration/test_gateway_turns.py`, update the `send_turn` call to use `content` instead of `message`:

```python
# Find all occurrences of "message": and change to "content":
# e.g. json={"message": "Hello"} → json={"content": "Hello"}
```

Delete `tests/integration/test_gateway_tasks.py` since the tasks routes are now under sessions:

```bash
git rm tests/integration/test_gateway_tasks.py
```

- [ ] **Step 7: Commit**

```bash
git add sebastian/gateway/routes/sessions.py sebastian/gateway/routes/turns.py \
        tests/integration/test_gateway_sessions.py tests/integration/test_gateway_turns.py
git rm sebastian/gateway/routes/tasks.py tests/integration/test_gateway_tasks.py
git commit -m "feat(gateway): session-centric routes; POST /turns creates session; drop /tasks routes"
```

---

## Mainline C — Mobile App

### Task 8: Extend SessionMeta type; add sessions API module

**Files:**
- Modify: `ui/mobile/src/types.ts`
- Create: `ui/mobile/src/api/sessions.ts`
- Modify: `ui/mobile/src/api/turns.ts`

- [ ] **Step 1: Update SessionMeta in types.ts**

In `ui/mobile/src/types.ts`, replace the `SessionMeta` interface:

```typescript
export interface SessionMeta {
  id: string;
  agent: string;
  title: string;
  status: 'active' | 'idle' | 'archived';
  updated_at: string;
  task_count: number;
  active_task_count: number;
}
```

Also add `TaskDetail` for session detail view:

```typescript
export interface TaskDetail {
  id: string;
  session_id: string;
  goal: string;
  status: TaskStatus;
  assigned_agent: string;
  created_at: string;
  completed_at: string | null;
}
```

- [ ] **Step 2: Create sessions.ts API module**

Create `ui/mobile/src/api/sessions.ts`:

```typescript
import { apiClient } from './client';
import type { SessionMeta, Message, TaskDetail } from '../types';

export interface SessionDetail {
  session: SessionMeta;
  messages: Message[];
}

export async function getSessions(): Promise<SessionMeta[]> {
  const { data } = await apiClient.get<{ sessions: SessionMeta[] }>('/api/v1/sessions');
  return data.sessions;
}

export async function getAgentSessions(agent: string): Promise<SessionMeta[]> {
  const { data } = await apiClient.get<{ sessions: SessionMeta[] }>(`/api/v1/agents/${agent}/sessions`);
  return data.sessions;
}

export async function getSessionDetail(sessionId: string, agent = 'sebastian'): Promise<SessionDetail> {
  const { data } = await apiClient.get<SessionDetail>(`/api/v1/sessions/${sessionId}`, {
    params: { agent },
  });
  return data;
}

export async function sendTurnToSession(
  sessionId: string,
  content: string,
  agent = 'sebastian',
): Promise<{ sessionId: string; response: string }> {
  const { data } = await apiClient.post<{ session_id: string; response: string }>(
    `/api/v1/sessions/${sessionId}/turns`,
    { content },
    { params: { agent } },
  );
  return { sessionId: data.session_id, response: data.response };
}

export async function getSessionTasks(sessionId: string, agent = 'sebastian'): Promise<TaskDetail[]> {
  const { data } = await apiClient.get<{ tasks: TaskDetail[] }>(
    `/api/v1/sessions/${sessionId}/tasks`,
    { params: { agent } },
  );
  return data.tasks;
}
```

- [ ] **Step 3: Simplify turns.ts — remove getSessions/getMessages (moved to sessions.ts)**

Replace `ui/mobile/src/api/turns.ts`:

```typescript
import { apiClient } from './client';

export async function sendTurn(
  sessionId: string | null,
  content: string,
): Promise<{ sessionId: string }> {
  const { data } = await apiClient.post<{ session_id: string }>('/api/v1/turns', {
    session_id: sessionId,
    content,
  });
  return { sessionId: data.session_id };
}

export async function cancelTurn(sessionId: string): Promise<void> {
  await apiClient.post(`/api/v1/sessions/${sessionId}/cancel`);
}
```

- [ ] **Step 4: Update useSessions hook to use new API**

In `ui/mobile/src/hooks/useSessions.ts`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { getSessions } from '../api/sessions';
import { useSettingsStore } from '../store/settings';

export function useSessions() {
  const jwtToken = useSettingsStore((s) => s.jwtToken);
  return useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    enabled: !!jwtToken,
  });
}
```

- [ ] **Step 5: Update session store to include agent field**

In `ui/mobile/src/store/session.ts`, update `persistSession` and the `SessionMeta` usage to pass `agent`:

```typescript
persistSession: (meta) =>
  set((state) => {
    const filtered = state.sessionIndex.filter((s) => s.id !== meta.id);
    const updated = [meta, ...filtered].slice(0, MAX_SESSIONS);
    return { sessionIndex: updated, currentSessionId: meta.id, draftSession: false };
  }),
```

And update the `persistSession` call in `chat/index.tsx` to pass the full meta from the API response:

In `ui/mobile/app/(tabs)/chat/index.tsx`, update `handleSend`:

```typescript
async function handleSend(text: string) {
  try {
    const { sessionId } = await sendTurn(currentSessionId, text);
    if (!currentSessionId) {
      persistSession({
        id: sessionId,
        agent: 'sebastian',
        title: text.slice(0, 40),
        status: 'active',
        updated_at: new Date().toISOString(),
        task_count: 0,
        active_task_count: 0,
      });
    }
    queryClient.invalidateQueries({ queryKey: ['messages', sessionId] });
  } catch {
    Alert.alert('发送失败，请重试');
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add ui/mobile/src/types.ts ui/mobile/src/api/sessions.ts \
        ui/mobile/src/api/turns.ts ui/mobile/src/hooks/useSessions.ts \
        ui/mobile/src/store/session.ts ui/mobile/app/\(tabs\)/chat/index.tsx
git commit -m "feat(mobile): extend SessionMeta; add sessions API module; update turns API"
```

---

### Task 9: Rebuild SubAgents page as supervision panel

**Files:**
- Create: `ui/mobile/src/components/subagents/SessionList.tsx`
- Modify: `ui/mobile/app/(tabs)/subagents/index.tsx`

- [ ] **Step 1: Create SessionList component**

Create `ui/mobile/src/components/subagents/SessionList.tsx`:

```typescript
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import type { SessionMeta } from '../../types';

interface Props {
  sessions: SessionMeta[];
  onSelect: (session: SessionMeta) => void;
}

function StatusDot({ status }: { status: SessionMeta['status'] }) {
  const color = status === 'active' ? '#34C759' : status === 'idle' ? '#999' : '#ccc';
  return <View style={[styles.dot, { backgroundColor: color }]} />;
}

export function SessionList({ sessions, onSelect }: Props) {
  if (sessions.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>暂无进行中的会话</Text>
      </View>
    );
  }
  return (
    <FlatList
      data={sessions}
      keyExtractor={(s) => s.id}
      renderItem={({ item }) => (
        <TouchableOpacity style={styles.row} onPress={() => onSelect(item)}>
          <StatusDot status={item.status} />
          <View style={styles.info}>
            <Text style={styles.title} numberOfLines={1}>{item.title}</Text>
            <Text style={styles.meta}>
              {item.active_task_count > 0 ? `${item.active_task_count} 个任务进行中` : '空闲'}
            </Text>
          </View>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { color: '#999', fontSize: 14 },
  row: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#e0e0e0' },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  info: { flex: 1 },
  title: { fontSize: 15, fontWeight: '500', color: '#111' },
  meta: { fontSize: 12, color: '#888', marginTop: 2 },
});
```

- [ ] **Step 2: Rebuild SubAgents page**

Replace `ui/mobile/app/(tabs)/subagents/index.tsx`:

```typescript
import { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import { useAgentsStore } from '../../../src/store/agents';
import { useAgents } from '../../../src/hooks/useAgents';
import { getAgentSessions } from '../../../src/api/sessions';
import { Sidebar } from '../../../src/components/common/Sidebar';
import { AgentSidebar } from '../../../src/components/subagents/AgentSidebar';
import { SessionList } from '../../../src/components/subagents/SessionList';
import { EmptyState } from '../../../src/components/common/EmptyState';
import type { SessionMeta } from '../../../src/types';

export default function SubAgentsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { currentAgentId, setCurrentAgent } = useAgentsStore();
  const { data: agents = [] } = useAgents();

  const selectedAgent = agents.find((a) => a.id === currentAgentId);

  const { data: sessions = [] } = useQuery({
    queryKey: ['agent-sessions', currentAgentId],
    queryFn: () => getAgentSessions(selectedAgent?.name ?? ''),
    enabled: !!currentAgentId && !!selectedAgent,
  });

  function handleSelectSession(session: SessionMeta) {
    router.push(`/(tabs)/subagents/session/${session.id}?agent=${session.agent}`);
  }

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <TouchableOpacity style={styles.menuButton} onPress={() => setSidebarOpen(true)}>
          <Text style={styles.menuIcon}>☰</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>
          {selectedAgent ? selectedAgent.name : 'Sub-Agents'}
        </Text>
      </View>
      {!currentAgentId ? (
        <EmptyState message="从左侧选择一个 Sub-Agent 查看会话" />
      ) : (
        <SessionList sessions={sessions} onSelect={handleSelectSession} />
      )}
      <Sidebar visible={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <AgentSidebar
          agents={agents}
          currentAgentId={currentAgentId}
          onSelect={(id) => { setCurrentAgent(id); setSidebarOpen(false); }}
        />
      </Sidebar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: {
    minHeight: 48,
    backgroundColor: '#ffffff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  menuButton: { padding: 8 },
  menuIcon: { fontSize: 20 },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '600',
    marginRight: 36,
  },
});
```

- [ ] **Step 3: Commit**

```bash
git add ui/mobile/src/components/subagents/SessionList.tsx \
        ui/mobile/app/\(tabs\)/subagents/index.tsx
git commit -m "feat(mobile): rebuild SubAgents page as session supervision panel"
```

---

### Task 10: Add Session Detail page

**Files:**
- Create: `ui/mobile/src/components/subagents/SessionDetailView.tsx`
- Create: `ui/mobile/app/(tabs)/subagents/session/[id].tsx`

- [ ] **Step 1: Create SessionDetailView**

Create `ui/mobile/src/components/subagents/SessionDetailView.tsx`:

```typescript
import { View, Text, FlatList, StyleSheet } from 'react-native';
import type { TaskDetail } from '../../types';

interface Props {
  tasks: TaskDetail[];
}

function taskStatusColor(status: TaskDetail['status']): string {
  switch (status) {
    case 'running': return '#FF9500';
    case 'completed': return '#34C759';
    case 'failed': return '#FF3B30';
    case 'cancelled': return '#999';
    default: return '#007AFF';
  }
}

export function SessionDetailView({ tasks }: Props) {
  if (tasks.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>暂无任务</Text>
      </View>
    );
  }
  return (
    <FlatList
      data={tasks}
      keyExtractor={(t) => t.id}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={[styles.status, { color: taskStatusColor(item.status) }]}>
              {item.status.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.goal}>{item.goal}</Text>
          <Text style={styles.meta}>
            {new Date(item.created_at).toLocaleString()}
          </Text>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { color: '#999', fontSize: 14 },
  list: { padding: 12 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, marginBottom: 10, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'flex-end', marginBottom: 6 },
  status: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  goal: { fontSize: 14, color: '#111', lineHeight: 20 },
  meta: { fontSize: 11, color: '#aaa', marginTop: 6 },
});
```

- [ ] **Step 2: Create session detail screen**

Create `ui/mobile/app/(tabs)/subagents/session/[id].tsx`:

```typescript
import { useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getSessionDetail, getSessionTasks, sendTurnToSession } from '../../../../src/api/sessions';
import { MessageList } from '../../../../src/components/chat/MessageList';
import { MessageInput } from '../../../../src/components/chat/MessageInput';
import { SessionDetailView } from '../../../../src/components/subagents/SessionDetailView';

type Tab = 'messages' | 'tasks';

export default function SessionDetailScreen() {
  const { id, agent = 'sebastian' } = useLocalSearchParams<{ id: string; agent: string }>();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>('messages');
  const [sending, setSending] = useState(false);

  const { data: detail } = useQuery({
    queryKey: ['session-detail', id, agent],
    queryFn: () => getSessionDetail(id, agent),
    enabled: !!id,
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ['session-tasks', id, agent],
    queryFn: () => getSessionTasks(id, agent),
    enabled: !!id,
  });

  const handleSend = useCallback(async (text: string) => {
    if (!id) return;
    setSending(true);
    try {
      await sendTurnToSession(id, text, agent);
      queryClient.invalidateQueries({ queryKey: ['session-detail', id, agent] });
    } catch {
      Alert.alert('发送失败，请重试');
    } finally {
      setSending(false);
    }
  }, [id, agent, queryClient]);

  const messages = detail?.messages.map((m, i) => ({
    id: String(i),
    sessionId: id,
    role: m.role as 'user' | 'assistant',
    content: m.content,
    createdAt: m.ts ?? '',
  })) ?? [];

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <TouchableOpacity style={styles.back} onPress={() => router.back()}>
          <Text style={styles.backText}>‹ 返回</Text>
        </TouchableOpacity>
        <Text style={styles.title} numberOfLines={1}>
          {detail?.session.title ?? '会话详情'}
        </Text>
      </View>
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, tab === 'messages' && styles.tabActive]}
          onPress={() => setTab('messages')}
        >
          <Text style={[styles.tabText, tab === 'messages' && styles.tabTextActive]}>消息</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'tasks' && styles.tabActive]}
          onPress={() => setTab('tasks')}
        >
          <Text style={[styles.tabText, tab === 'tasks' && styles.tabTextActive]}>
            任务 {tasks.length > 0 ? `(${tasks.length})` : ''}
          </Text>
        </TouchableOpacity>
      </View>
      <View style={styles.body}>
        {tab === 'messages' ? (
          <MessageList messages={messages} streamingContent="" />
        ) : (
          <SessionDetailView tasks={tasks} />
        )}
      </View>
      <MessageInput isWorking={sending} onSend={handleSend} onStop={() => {}} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: {
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 48,
    paddingHorizontal: 12,
  },
  back: { padding: 8, marginRight: 4 },
  backText: { fontSize: 16, color: '#007AFF' },
  title: { flex: 1, fontSize: 15, fontWeight: '600', color: '#111' },
  tabs: { flexDirection: 'row', backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e0e0e0' },
  tab: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#007AFF' },
  tabText: { fontSize: 14, color: '#888' },
  tabTextActive: { color: '#007AFF', fontWeight: '600' },
  body: { flex: 1 },
});
```

- [ ] **Step 3: Commit**

```bash
git add ui/mobile/src/components/subagents/SessionDetailView.tsx \
        "ui/mobile/app/(tabs)/subagents/session/[id].tsx"
git commit -m "feat(mobile): add Session detail page with messages + task progress tabs"
```

---

### Task 11: Wire ApprovalModal to real approvals flow

**Files:**
- Modify: `ui/mobile/src/store/approval.ts`
- Modify: `ui/mobile/app/_layout.tsx`

- [ ] **Step 1: Check current approval store**

Read `ui/mobile/src/store/approval.ts` to understand current state, then replace with:

```typescript
import { create } from 'zustand';
import type { Approval } from '../types';
import { apiClient } from '../api/client';

interface ApprovalState {
  pending: Approval | null;
  setPending: (approval: Approval | null) => void;
  grant: () => Promise<void>;
  deny: () => Promise<void>;
}

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  pending: null,

  setPending: (approval) => set({ pending: approval }),

  grant: async () => {
    const { pending } = get();
    if (!pending) return;
    await apiClient.post(`/api/v1/approvals/${pending.id}/grant`);
    set({ pending: null });
  },

  deny: async () => {
    const { pending } = get();
    if (!pending) return;
    await apiClient.post(`/api/v1/approvals/${pending.id}/deny`);
    set({ pending: null });
  },
}));
```

- [ ] **Step 2: Wire ApprovalModal into root layout**

Read `ui/mobile/app/_layout.tsx`, then add ApprovalModal. In the root layout's return, wrap children with:

```typescript
// Add these imports at top of _layout.tsx:
import { useApprovalStore } from '../src/store/approval';
import { ApprovalModal } from '../src/components/common/ApprovalModal';
import { useSSE } from '../src/hooks/useSSE';

// Inside the root layout component, add:
const { pending, grant, deny, setPending } = useApprovalStore();

// The useSSE hook should call setPending when an approval.required event arrives.
// Add this effect (assumes useSSE exposes an onEvent callback or you can modify it):
useSSE({
  onApprovalRequired: (approval) => setPending(approval),
});

// At the end of the return JSX, before closing tag, add:
<ApprovalModal approval={pending} onGrant={grant} onDeny={deny} />
```

Check `ui/mobile/src/hooks/useSSE.ts` to confirm the SSE hook signature and add `onApprovalRequired` callback if not present.

- [ ] **Step 3: Check useSSE and add approval callback if missing**

Read `ui/mobile/src/hooks/useSSE.ts`. If `approval.required` events are not forwarded to a callback, add:

```typescript
// In useSSE.ts, in the event handler switch/if block, add:
if (event.type === 'approval.required') {
  opts?.onApprovalRequired?.(event.data.approval);
}
```

And update the hook's options type to include `onApprovalRequired?: (a: Approval) => void`.

- [ ] **Step 4: Commit**

```bash
git add ui/mobile/src/store/approval.ts ui/mobile/app/_layout.tsx \
        ui/mobile/src/hooks/useSSE.ts
git commit -m "feat(mobile): wire ApprovalModal to real approvals API via SSE trigger"
```

---

## Mainline D — Docker Compose (Phase 1 Closeout)

### Task 12: Finalize Docker Compose single-machine deployment

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile`
- Create: `.env.example` (if not present)

- [ ] **Step 1: Check current docker-compose.yml and Dockerfile**

The existing `docker-compose.yml` and `Dockerfile` are mostly correct. The only gap: the `data/sessions` subdirectory needs to exist on first run, and the health check endpoint needs to be present.

- [ ] **Step 2: Verify health endpoint exists**

Check `sebastian/gateway/routes/agents.py` for `GET /api/v1/health`. If missing, add it:

```python
@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3: Update docker-compose.yml to pre-create sessions dirs**

Replace `docker-compose.yml`:

```yaml
services:
  gateway:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./knowledge:/app/knowledge
      - ./sebastian/agents:/app/sebastian/agents
      - ./sebastian/capabilities:/app/sebastian/capabilities
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  # Phase 2+: uncomment when ChromaDB semantic memory is wired
  # chromadb:
  #   image: chromadb/chroma:latest
  #   volumes:
  #     - ./data/chroma:/chroma/chroma
  #   restart: unless-stopped
```

- [ ] **Step 4: Update Dockerfile to pre-create sessions subdirs**

In `Dockerfile`, update the `RUN mkdir` line:

```dockerfile
RUN mkdir -p /app/data /app/data/sessions/sebastian /app/data/sessions/subagents /app/knowledge
```

- [ ] **Step 5: Ensure .env.example exists and is complete**

Create or verify `.env.example`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

SEBASTIAN_OWNER_NAME=Eric
SEBASTIAN_DATA_DIR=./data
SEBASTIAN_SANDBOX_ENABLED=false
SEBASTIAN_GATEWAY_HOST=0.0.0.0
SEBASTIAN_GATEWAY_PORT=8000
SEBASTIAN_JWT_SECRET=change-me-in-production
SEBASTIAN_OWNER_PASSWORD_HASH=
SEBASTIAN_MODEL=claude-opus-4-6
```

- [ ] **Step 6: Test Docker build**

```bash
docker compose build && docker compose up -d
sleep 5
curl -f http://127.0.0.1:8000/api/v1/health
docker compose down
```
Expected: `{"status":"ok"}`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml Dockerfile .env.example sebastian/gateway/routes/agents.py
git commit -m "chore(deploy): finalize Docker Compose Phase 1 single-machine deployment"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Session 一等公民，文件存储 | Task 3, 4 |
| Task 归属 Session，session_id 字段 | Task 1 |
| Checkpoint 改为 JSONL 文件 | Task 4 |
| index.json 维护 | Task 3, 6 |
| Gateway 路由以 Session 为中心 | Task 7 |
| POST /sessions/{id}/turns | Task 7 |
| GET /agents/{agent}/sessions | Task 7 |
| user.intervened 事件 | Task 6 |
| SubAgents 页 → Session 列表督导面板 | Task 9 |
| Session 详情页（消息 + 任务进度 + 纠偏输入） | Task 10 |
| SessionMeta 字段补全 | Task 8 |
| ApprovalModal 接入 | Task 11 |
| Docker Compose 单机部署 | Task 12 |

**Type consistency check:**
- `Session`, `SessionStatus` defined in Task 1, used in Task 3/4/6/7/8 ✓
- `Task.session_id` added in Task 1, used in Task 4/5/6/7 ✓
- `SessionStore` methods: `create_session`, `get_session`, `append_message`, `get_messages`, `create_task`, `get_task`, `list_tasks`, `update_task_status`, `append_checkpoint`, `get_checkpoints` — consistent across Tasks 4/5/6/7 ✓
- `IndexStore` methods: `upsert`, `list_all`, `list_by_agent`, `remove` — consistent across Tasks 3/6/7 ✓
- Mobile: `SessionMeta` fields `agent, status, updated_at, task_count, active_task_count` added in Task 8, used in Tasks 9/10 ✓
- `sendTurnToSession` in `sessions.ts` used in Task 10's `[id].tsx` ✓

No gaps found.
