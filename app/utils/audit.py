"""Audit log — record key admin actions to the audit_log table."""
import asyncio
import json
import structlog

from app.db.connection import get_conn

logger = structlog.get_logger(__name__)


def _write_audit(
    actor: str,
    action: str,
    entity_type: str | None,
    entity_id: str | None,
    detail_json: str | None,
    ip: str | None,
) -> None:
    """Synchronous DB write — runs in calling thread or thread pool."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (actor, action, entity_type, entity_id, detail_json, ip_address)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (actor, action, entity_type, str(entity_id) if entity_id else None,
                 detail_json, ip),
            )
        logger.debug("audit.logged", actor=actor, action=action)
    except Exception as e:
        logger.error("audit.failed", actor=actor, action=action, error=str(e))


def log_action(
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """Insert an audit record.  Non-blocking when called from async context (uses thread pool);
    falls back to synchronous write when no event loop is running."""
    detail_json = json.dumps(detail, ensure_ascii=False) if detail else None
    try:
        loop = asyncio.get_running_loop()
        # Running inside an async handler — schedule the DB write in a thread pool
        # so it does not block the event loop.  The returned task is fire-and-forget.
        loop.create_task(asyncio.to_thread(
            _write_audit, actor, action, entity_type, entity_id, detail_json, ip
        ))
    except RuntimeError:
        # No running event loop (e.g., called from startup or sync context)
        _write_audit(actor, action, entity_type, entity_id, detail_json, ip)


async def log_action_bg(
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """Non-blocking async wrapper — runs log_action in a thread pool, fire-and-forget.

    Usage in async route handlers (replaces blocking log_action call):
        asyncio.create_task(log_action_bg(...))
    """
    try:
        await asyncio.to_thread(log_action, actor, action, entity_type, entity_id, detail, ip)
    except Exception as e:
        logger.error("audit.bg_failed", actor=actor, action=action, error=str(e))
