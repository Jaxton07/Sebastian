from __future__ import annotations

from datetime import timedelta

from sebastian.store.attachments import AttachmentStore
from sebastian.trigger.scheduler import JobRegistry, ScheduledJob


def register_builtin_jobs(
    registry: JobRegistry,
    *,
    attachment_store: AttachmentStore,
) -> None:
    registry.register(
        ScheduledJob(
            id="attachments.cleanup",
            handler=attachment_store.cleanup,
            interval=timedelta(hours=6),
            run_on_startup=True,
            startup_delay=timedelta(minutes=2),
            timeout_seconds=300,
        )
    )
