"""Thin database layer that speaks both SQLite (local dev) and Postgres (Supabase).

Design notes for readability:
  * All SQL in this project is written with ``?`` placeholders.
  * ``_sql()`` rewrites them to ``%s`` when the target is Postgres.
  * Rows are returned as plain dicts so routers never depend on a driver type.
  * Every query in the app is workspace-scoped; this module does not enforce that
    (routers do), but it does provide ``tx()`` so multi-statement writes are atomic.
"""
from __future__ import annotations

import queue
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from .config import get_settings

_POOL_SIZE = 8


def _sql(query: str) -> str:
    """Translate ``?`` placeholders to the driver's style."""
    if get_settings().is_postgres:
        return query.replace("?", "%s")
    return query


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.is_postgres = url.startswith(("postgres://", "postgresql://"))
        self._lock = threading.RLock()
        self._pool: queue.Queue[Any] = queue.Queue(maxsize=_POOL_SIZE)
        self._sqlite_conn: sqlite3.Connection | None = None
        if self.is_postgres:
            self._pg_url = self._normalise_pg(url)
        else:
            self._sqlite_path = url.replace("sqlite:///", "").replace("sqlite://", "")
            self._sqlite_conn = sqlite3.connect(
                self._sqlite_path, check_same_thread=False, isolation_level=None
            )
            self._sqlite_conn.row_factory = sqlite3.Row
            self._sqlite_conn.execute("PRAGMA journal_mode=WAL")
            self._sqlite_conn.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _normalise_pg(url: str) -> str:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url.replace("postgresql+psycopg://", "postgresql://")

    # -- connection management ------------------------------------------------
    @contextmanager
    def _conn(self) -> Iterator[Any]:
        if not self.is_postgres:
            assert self._sqlite_conn is not None
            with self._lock:
                yield self._sqlite_conn
            return

        import psycopg
        from psycopg.rows import dict_row

        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            conn = psycopg.connect(self._pg_url, row_factory=dict_row)
        try:
            yield conn
        finally:
            if conn.closed:
                pass
            else:
                try:
                    self._pool.put_nowait(conn)
                except queue.Full:
                    conn.close()

    # -- public API -----------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(_sql(sql), tuple(params))
            rows = cur.fetchall()
            if self.is_postgres:
                return [dict(r) for r in rows]
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a write statement. Returns affected row count."""
        with self._conn() as conn:
            cur = conn.execute(_sql(sql), tuple(params))
            if self.is_postgres:
                conn.commit()
            return cur.rowcount

    def insert(self, sql: str, params: Sequence[Any] = ()) -> None:
        self.execute(sql, params)

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        with self._conn() as conn:
            if self.is_postgres:
                with conn.cursor() as cur:
                    cur.executemany(_sql(sql), rows)
                conn.commit()
            else:
                conn.executemany(sql, rows)

    @contextmanager
    def tx(self) -> Iterator[Any]:
        """Atomic block. SQLite uses an explicit transaction; Postgres commits."""
        with self._conn() as conn:
            if self.is_postgres:
                with conn.transaction():
                    yield conn
            else:
                conn.execute("BEGIN")
                try:
                    yield conn
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
                else:
                    conn.execute("COMMIT")

    def healthcheck(self) -> bool:
        try:
            self.query("SELECT 1 AS ok")
            return True
        except Exception:
            return False


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(get_settings().database_url)
    return _db
