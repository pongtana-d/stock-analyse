"""In-app analysis scheduler (APScheduler, Asia/Bangkok / UTC+7).

Replaces the external cron job. Reads enable/disable + frequency from the
config table so the schedule can be changed from the Web UI without a restart.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.repositories import config_repo

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Bangkok"
JOB_ID = "portfolio_analysis"

# Frequency preset key -> (human label, cron expression in Bangkok time).
# All presets are constrained to SET trading hours (10:00-16:xx) on weekdays;
# the job itself additionally skips market holidays via the SET calendar.
FREQUENCY_PRESETS: dict[str, tuple[str, str]] = {
    "default": ("Market hours (10-12, 14-16)", "0 10-12,14-16 * * 1-5"),
    "30m": ("Every 30 minutes", "*/30 10-16 * * 1-5"),
    "1h": ("Every 1 hour", "0 10-16 * * 1-5"),
    "2h": ("Every 2 hours", "0 10,12,14,16 * * 1-5"),
}
DEFAULT_FREQUENCY = "default"

_scheduler: AsyncIOScheduler | None = None


def _cron_for(freq: str) -> str:
    return FREQUENCY_PRESETS.get(freq, FREQUENCY_PRESETS[DEFAULT_FREQUENCY])[1]


async def _is_enabled() -> bool:
    raw = await config_repo.get_config("scheduler_enabled")
    return (raw or "false").strip().lower() == "true"


async def _frequency() -> str:
    freq = await config_repo.get_config("scheduler_frequency")
    return freq if freq in FREQUENCY_PRESETS else DEFAULT_FREQUENCY


async def _run_job() -> None:
    # Local import to avoid a circular import at module load time.
    from app.routers.analysis import execute_portfolio_run

    logger.info("Scheduler: starting scheduled portfolio analysis")
    try:
        result = await execute_portfolio_run(force=False, send_discord=True)
        logger.info(
            "Scheduler: finished (market_open=%s, %d tickers)",
            result.market_open,
            len(result.results),
        )
    except Exception:
        logger.exception("Scheduler: portfolio analysis failed")


async def start_scheduler() -> None:
    """Start the scheduler and load the configured job (called on startup)."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        _scheduler.start()
    await reload_scheduler()


async def reload_scheduler() -> None:
    """(Re)apply the schedule from current config. Call after config changes."""
    if _scheduler is None:
        return

    if _scheduler.get_job(JOB_ID):
        _scheduler.remove_job(JOB_ID)

    if not await _is_enabled():
        logger.info("Scheduler disabled; no analysis job scheduled")
        return

    freq = await _frequency()
    cron = _cron_for(freq)
    _scheduler.add_job(
        _run_job,
        trigger=CronTrigger.from_crontab(cron, timezone=TIMEZONE),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info("Scheduler enabled: freq=%s cron='%s' tz=%s", freq, cron, TIMEZONE)


async def shutdown_scheduler() -> None:
    """Stop the scheduler (called on shutdown)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_next_run() -> str | None:
    """ISO timestamp of the next scheduled run, or None when idle/disabled."""
    if _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
