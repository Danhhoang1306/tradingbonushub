"""SQL Server database connection via pyodbc — with thread-safe connection pool.

Provides a thin wrapper over pyodbc that mimics the sqlite3 API
(dict-like row access, .execute()/.executemany() on connection, .lastrowid).
"""
import logging
import os
import queue
import threading
from contextlib import contextmanager

import pyodbc
from dotenv import load_dotenv

_log = logging.getLogger(__name__)

load_dotenv()

# ── Connection config (from environment) ──────────────────────────────────────
# NOTE: In production, create a dedicated SQL Server service account with only
# SELECT/INSERT/UPDATE/DELETE permissions on app tables — never use 'sa'.
# Example: CREATE LOGIN app_user WITH PASSWORD='...'; CREATE USER app_user FOR LOGIN app_user;
#          GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO app_user;
SERVER   = os.environ.get("DB_SERVER",   "")
DATABASE = os.environ.get("DB_NAME",     "TradingBonusHub")
USERNAME = os.environ.get("DB_USER",     "")
PASSWORD = os.environ.get("DB_PASSWORD", "")

_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
)

# Used by init.py to create the DB against master
MASTER_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SERVER};"
    "DATABASE=master;"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "TrustServerCertificate=yes;"
)


# ── Row / Cursor wrapper ───────────────────────────────────────────────────────

class _Cursor:
    """pyodbc cursor wrapper: fetchone/fetchall return dicts; lastrowid works."""

    def __init__(self, cursor: pyodbc.Cursor):
        self._c = cursor

    def _to_dict(self, row):
        if row is None:
            return None
        cols = [d[0] for d in self._c.description]
        return dict(zip(cols, row))

    def fetchone(self):
        return self._to_dict(self._c.fetchone())

    def fetchall(self):
        rows = self._c.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._c.description]
        return [dict(zip(cols, r)) for r in rows]

    @property
    def lastrowid(self) -> int | None:
        """Return the IDENTITY value inserted by the last INSERT statement.
        Uses SCOPE_IDENTITY() (not @@IDENTITY) to avoid returning values from triggers."""
        self._c.execute("SELECT SCOPE_IDENTITY()")
        row = self._c.fetchone()
        val = row[0] if row else None
        return int(val) if val is not None else None

    @property
    def rowcount(self) -> int:
        """Number of rows affected by the last DML statement."""
        return self._c.rowcount

    def __iter__(self):
        cols = [d[0] for d in self._c.description]
        for row in self._c:
            yield dict(zip(cols, row))


# ── Connection wrapper ─────────────────────────────────────────────────────────

class _Conn:
    """pyodbc connection wrapper providing a sqlite3-compatible interface."""

    def __init__(self, conn: pyodbc.Connection):
        self._conn = conn

    def execute(self, sql: str, params=None) -> _Cursor:
        cur = self._conn.cursor()
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return _Cursor(cur)

    def executemany(self, sql: str, seq_params) -> None:
        cur = self._conn.cursor()
        for params in seq_params:  # loop is safer than executemany for MERGE/complex T-SQL
            cur.execute(sql, params)


# ── Connection pool ────────────────────────────────────────────────────────────

_pool: queue.Queue | None = None
_pool_lock = threading.Lock()
_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))


def init_pool(size: int = _POOL_SIZE) -> None:
    """Create the connection pool at startup. Call once before first request.

    Pool size is controlled by the DB_POOL_SIZE environment variable (default 20).
    Each connection is validated with a SELECT 1 before being added to the pool.

    Startup resilience: waits up to 60s for SQL Server to become ready (handles
    the case where app boots before SQL Server after a Windows reboot).
    """
    import time
    global _pool
    with _pool_lock:
        if _pool is not None:
            return  # already initialized

        # Wait for SQL Server to be reachable before opening the full pool.
        # Backs off with 2s sleeps for up to 60s. After that, give up and let
        # get_conn() use the per-request fallback path.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                probe = pyodbc.connect(_CONN_STR, timeout=5)
                probe.cursor().execute("SELECT 1")
                probe.close()
                break
            except Exception as e:
                _log.warning("db.pool_waiting_for_server", error=str(e))
                time.sleep(2)
        else:
            _log.error("db.pool_server_unreachable_after_60s")
            return  # leave _pool as None; get_conn() will fall back per-request

        _pool = queue.Queue(maxsize=size)
        for i in range(size):
            for attempt in range(3):
                try:
                    conn = pyodbc.connect(_CONN_STR, timeout=15)
                    conn.autocommit = False
                    conn.cursor().execute("SELECT 1")
                    _pool.put(conn)
                    break
                except Exception:
                    if attempt == 2:
                        _log.warning("db.pool_conn_failed", index=i)
                    else:
                        time.sleep(1)


def _new_raw_conn() -> pyodbc.Connection:
    conn = pyodbc.connect(_CONN_STR, timeout=15)
    conn.autocommit = False
    return conn


# ── Context manager ────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    """Yield a wrapped pyodbc connection from the pool.

    Commits on success, rolls back on error, returns the connection to the pool
    regardless. Falls back to a direct connection when the pool is not yet
    initialized (e.g. during init_db() at startup).
    """
    if _pool is None:
        # Fallback for init_db() which runs before init_pool()
        raw = _new_raw_conn()
        try:
            yield _Conn(raw)
            raw.commit()
        except Exception:
            try:
                raw.rollback()
            except Exception:
                pass
            raise
        finally:
            raw.close()
        return

    try:
        raw = _pool.get(timeout=30)
    except queue.Empty:
        _log.error("db.pool_exhausted", pool_size=_pool.maxsize,
                   detail="All DB connections are in use. Consider increasing DB_POOL_SIZE.")
        raise RuntimeError(
            f"DB connection pool exhausted (pool_size={_pool.maxsize}). "
            "Set DB_POOL_SIZE env var to a higher value."
        )
    try:
        yield _Conn(raw)
        raw.commit()
    except Exception:
        try:
            raw.rollback()
        except Exception:
            pass
        raise
    finally:
        # Validate connection before returning to pool — replace if broken.
        # A ping (SELECT 1) catches stale connections dropped by SQL Server
        # after idle timeout or network interruption.
        try:
            raw.autocommit = False
            raw.cursor().execute("SELECT 1")
        except Exception as e:
            _log.warning("db.pool_conn_broken_replacing", error=str(e))
            try:
                raw.close()
            except Exception:
                pass
            raw = _new_raw_conn()
        _pool.put(raw)
