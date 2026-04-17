"""DB-backed job worker — polls job_queue and executes pending jobs."""
import asyncio

import structlog

from app.db.repositories.job_queue import (
    claim_next_job, mark_job_done, mark_job_failed, reset_stuck_jobs,
)

logger = structlog.get_logger(__name__)

_POLL_INTERVAL = 2       # seconds between queue polls
_MAX_CONCURRENT_JOBS = 5  # maximum campaigns running in parallel

_sem: asyncio.Semaphore | None = None


async def _run_job(job: dict) -> None:
    job_id = job["id"]
    job_type = job["job_type"]
    async with _sem:
        logger.info("job.started", job_id=job_id, job_type=job_type)
        try:
            if job_type == "campaign":
                import json
                from app.services.mailer import execute_campaign_job
                payload = json.loads(job["payload_json"]) if isinstance(job["payload_json"], str) else job["payload_json"]
                await execute_campaign_job(payload)
            else:
                raise ValueError(f"Unknown job_type: {job_type!r}")
            mark_job_done(job_id)
            logger.info("job.done", job_id=job_id, job_type=job_type)
        except Exception as exc:
            logger.error("job.failed", job_id=job_id, job_type=job_type, error=str(exc))
            mark_job_failed(job_id, str(exc))


async def start_worker() -> None:
    """Background worker loop — call once at app startup."""
    global _sem
    _sem = asyncio.Semaphore(_MAX_CONCURRENT_JOBS)
    reset_stuck_jobs()
    logger.info("job_worker.started", poll_interval=_POLL_INTERVAL, max_concurrent=_MAX_CONCURRENT_JOBS)
    while True:
        try:
            job = claim_next_job()
            if job:
                asyncio.create_task(_run_job(job))
        except Exception as exc:
            logger.error("job_worker.poll_error", error=str(exc))
        await asyncio.sleep(_POLL_INTERVAL)
