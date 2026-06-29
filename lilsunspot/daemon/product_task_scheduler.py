from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress

from . import product_features
from .config_paths import RuntimePaths

logger = logging.getLogger(__name__)
_scheduler_task: asyncio.Task[None] | None = None


def _interval_seconds() -> float:
    raw = os.environ.get("LILSUNSPOT_TASK_SCHEDULER_INTERVAL_SECONDS", "30").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 30.0
    return max(5.0, min(value, 3600.0))


async def _scheduler_loop(paths: RuntimePaths) -> None:
    interval = _interval_seconds()
    while True:
        try:
            results = product_features.run_due_tasks(paths=paths)
            if results:
                logger.info("product task scheduler ran due_tasks=%s", len(results))
        except Exception:
            logger.exception("product task scheduler failed")
        await asyncio.sleep(interval)


def start_task_scheduler(paths: RuntimePaths) -> asyncio.Task[None]:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop(paths), name="lilsunspot-product-task-scheduler")
    return _scheduler_task


async def stop_task_scheduler() -> None:
    global _scheduler_task
    task = _scheduler_task
    _scheduler_task = None
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
