"""DB-backed job queue — restart-safe campaign execution."""
import json

from app.db.connection import get_conn


def enqueue_job(job_type: str, payload: dict) -> int:
    """Insert a new pending job and return its ID."""
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO job_queue (job_type, payload_json, status) OUTPUT INSERTED.id VALUES (?, ?, 'pending')",
            (job_type, json.dumps(payload, ensure_ascii=False)),
        ).fetchone()
        return row["id"] if row else None


def claim_next_job() -> dict | None:
    """Atomically claim the next pending job.  Returns None if queue is empty.

    Uses UPDATE ... OUTPUT to claim a single job atomically, preventing
    double-claiming if ever running concurrent workers.
    """
    with get_conn() as conn:
        row = conn.execute("""
            UPDATE TOP(1) job_queue
            SET status='running', started_at=GETDATE()
            OUTPUT INSERTED.id, INSERTED.job_type, INSERTED.payload_json,
                   INSERTED.retry_count
            WHERE status='pending'
        """).fetchone()
        return dict(row) if row else None


def mark_job_done(job_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE job_queue SET status='done', finished_at=GETDATE() WHERE id=?",
            (job_id,),
        )


def mark_job_failed(job_id: int, error: str, max_retries: int = 3) -> None:
    with get_conn() as conn:
        # Get current retry count
        row = conn.execute(
            "SELECT retry_count FROM job_queue WHERE id=?", (job_id,)
        ).fetchone()
        if row and row["retry_count"] < max_retries:
            # Retry: reset to pending
            conn.execute(
                "UPDATE job_queue SET status='pending', error_msg=?, "
                "retry_count=retry_count+1, started_at=NULL WHERE id=?",
                (error[:2000], job_id),
            )
        else:
            conn.execute(
                "UPDATE job_queue SET status='failed', finished_at=GETDATE(), "
                "error_msg=?, retry_count=retry_count+1 WHERE id=?",
                (error[:2000], job_id),
            )


def reset_stuck_jobs(stuck_minutes: int = 10) -> int:
    """Reset jobs stuck in 'running' state longer than stuck_minutes (crash recovery)."""
    with get_conn() as conn:
        conn.execute("""
            UPDATE job_queue SET status='pending', started_at=NULL
            WHERE status='running'
              AND started_at < DATEADD(MINUTE, ?, GETDATE())
        """, (-stuck_minutes,))
    return 0


def get_job_status(job_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, job_type, status, created_at, started_at, finished_at, error_msg, retry_count "
            "FROM job_queue WHERE id=?",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None
