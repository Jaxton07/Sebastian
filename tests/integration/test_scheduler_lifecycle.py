from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sebastian.trigger.job_runs import ScheduledJobRunStore
from sebastian.trigger.jobs import register_builtin_jobs
from sebastian.trigger.scheduler import JobRegistry, SchedulerRunner


@pytest.fixture
async def lifecycle_db(tmp_path):
    import sebastian.store.models  # noqa: F401
    from sebastian.store.database import Base, _apply_idempotent_migrations

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_idempotent_migrations(conn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory, tmp_path
    finally:
        await engine.dispose()
        await asyncio.sleep(0)


async def test_register_builtin_jobs_registers_attachments_cleanup(lifecycle_db) -> None:
    from sebastian.store.attachments import AttachmentStore

    factory, tmp_path = lifecycle_db
    root = tmp_path / "attachments"
    for sub in ("blobs", "thumbs", "tmp"):
        (root / sub).mkdir(parents=True)
    attachment_store = AttachmentStore(root_dir=root, db_factory=factory)

    registry = JobRegistry()
    register_builtin_jobs(registry, attachment_store=attachment_store)

    jobs = registry.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "attachments.cleanup"
    assert jobs[0].interval == timedelta(hours=6)
    assert jobs[0].run_on_startup is True


async def test_scheduler_runs_job_and_persists_success(lifecycle_db) -> None:
    """Full end-to-end: tick → job runs → success record written."""
    from sebastian.store.attachments import AttachmentStore

    factory, tmp_path = lifecycle_db
    root = tmp_path / "attachments"
    for sub in ("blobs", "thumbs", "tmp"):
        (root / sub).mkdir(parents=True)
    attachment_store = AttachmentStore(root_dir=root, db_factory=factory)

    registry = JobRegistry()
    register_builtin_jobs(registry, attachment_store=attachment_store)
    run_store = ScheduledJobRunStore(factory)
    runner = SchedulerRunner(registry=registry, run_store=run_store)

    now = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    runner._next_run["attachments.cleanup"] = now  # force immediately due

    await runner._tick(now)
    task = runner._running.get("attachments.cleanup")
    assert task is not None
    await task  # wait for cleanup to complete

    last_success = await run_store.get_last_success_at("attachments.cleanup")
    assert last_success is not None


async def test_restart_recovery_uses_db_history(lifecycle_db) -> None:
    """After a simulated restart, next_run is last_success + interval, not epoch."""
    from sebastian.store.attachments import AttachmentStore

    factory, tmp_path = lifecycle_db
    root = tmp_path / "attachments"
    for sub in ("blobs", "thumbs", "tmp"):
        (root / sub).mkdir(parents=True)
    attachment_store = AttachmentStore(root_dir=root, db_factory=factory)

    # First run: job completes successfully
    run_store = ScheduledJobRunStore(factory)
    registry1 = JobRegistry()
    register_builtin_jobs(registry1, attachment_store=attachment_store)
    runner1 = SchedulerRunner(registry=registry1, run_store=run_store)

    now = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    runner1._next_run["attachments.cleanup"] = now
    await runner1._tick(now)
    task1 = runner1._running.get("attachments.cleanup")
    if task1:
        await task1

    last_success = await run_store.get_last_success_at("attachments.cleanup")
    assert last_success is not None

    # Simulate restart: new runner uses _compute_initial_next_run with DB history
    registry2 = JobRegistry()
    register_builtin_jobs(registry2, attachment_store=attachment_store)
    job = registry2.list_jobs()[0]

    restart_now = datetime(2024, 1, 1, 10, 30, 0, tzinfo=UTC)  # 30min after first run
    computed = SchedulerRunner._compute_initial_next_run(job, last_success, restart_now)

    # next run = last_success + 6h; NOT immediately
    assert computed > restart_now
