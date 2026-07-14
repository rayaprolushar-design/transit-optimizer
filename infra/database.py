"""
infra/database.py — Upgrade 7: PostgreSQL with Connection Pooling
Replaces SQLite from Week 2.

Why PostgreSQL over SQLite?
  1. Concurrent writes — SQLite locks the whole file, Postgres handles thousands
  2. Connection pooling — reuse connections instead of opening new ones per request
  3. JSONB columns — store graph data natively
  4. Full-text search — stop name search without loading all stops into memory
  5. Industry standard — every company at scale uses Postgres

Why connection pooling matters:
  Without pooling: every HTTP request opens a new DB connection (expensive, ~50ms)
  With pooling:    connections are reused from a pool (fast, ~0.1ms)
  FastAPI handles 1000 req/s → needs 20 pool connections, not 1000

Environment variables:
  DATABASE_URL — PostgreSQL connection string
    Local:    postgresql://postgres:password@localhost:5432/transit
    Railway:  postgresql://postgres:xxx@xxx.railway.app:5432/railway
    No PG:    falls back to SQLite automatically
"""

import os
import sqlite3
import json
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from rich.console import Console

console = Console()

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH  = Path("data/transit.db")

# ── Try to import SQLAlchemy + asyncpg ────────────────────────────────────────

try:
    from sqlalchemy import (
        create_engine, text, Column, String, Float,
        Integer, DateTime, JSON, Index
    )
    from sqlalchemy.orm import declarative_base, sessionmaker, Session
    from sqlalchemy.pool import QueuePool
    _sqla_available = True
except ImportError:
    _sqla_available = False


# ── Schema ────────────────────────────────────────────────────────────────────

POSTGRES_SCHEMA = """
-- Stops table
CREATE TABLE IF NOT EXISTS stops (
    stop_id    TEXT PRIMARY KEY,
    stop_name  TEXT NOT NULL,
    stop_lat   FLOAT NOT NULL,
    stop_lon   FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Routes table
CREATE TABLE IF NOT EXISTS routes (
    route_id         TEXT PRIMARY KEY,
    route_short_name TEXT NOT NULL,
    route_long_name  TEXT,
    route_type       INTEGER NOT NULL
);

-- Algorithm benchmark runs
CREATE TABLE IF NOT EXISTS algorithm_runs (
    id            SERIAL PRIMARY KEY,
    run_at        TIMESTAMP DEFAULT NOW(),
    algorithm     TEXT NOT NULL,
    start_stop    TEXT NOT NULL,
    end_stop      TEXT NOT NULL,
    found         BOOLEAN NOT NULL,
    total_minutes FLOAT,
    nodes_visited INTEGER NOT NULL,
    elapsed_ms    FLOAT NOT NULL
);

-- Delay observations from GPS tracker
CREATE TABLE IF NOT EXISTS delay_observations (
    id            SERIAL PRIMARY KEY,
    observed_at   TIMESTAMP DEFAULT NOW(),
    route_name    TEXT NOT NULL,
    stop_id       TEXT NOT NULL,
    delay_minutes FLOAT NOT NULL,
    hour          INTEGER NOT NULL,
    is_rush       BOOLEAN NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_delay_obs_stop    ON delay_observations(stop_id);
CREATE INDEX IF NOT EXISTS idx_delay_obs_hour    ON delay_observations(hour);
CREATE INDEX IF NOT EXISTS idx_delay_obs_time    ON delay_observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_algo_runs_algo    ON algorithm_runs(algorithm);

-- Full-text search on stop names
CREATE INDEX IF NOT EXISTS idx_stops_name
    ON stops USING gin(to_tsvector('english', stop_name));
"""


# ── Database class ────────────────────────────────────────────────────────────

class Database:
    """
    Unified database interface.
    Uses PostgreSQL if DATABASE_URL is set, otherwise SQLite.
    Same public API either way — the rest of the code doesn't need to know.
    """

    def __init__(self):
        self._engine     = None
        self._session_mk = None
        self._sqlite     = None
        self._using_pg   = False
        self._connect()

    def _connect(self):
        if DATABASE_URL and _sqla_available:
            self._connect_postgres()
        else:
            self._connect_sqlite()

    def _connect_postgres(self):
        try:
            self._engine = create_engine(
                DATABASE_URL,
                poolclass=QueuePool,
                pool_size=10,           # keep 10 connections open
                max_overflow=20,        # allow 20 extra under peak load
                pool_pre_ping=True,     # check connection health before use
                pool_recycle=3600,      # recycle connections every hour
            )
            with self._engine.connect() as conn:
                conn.execute(text(POSTGRES_SCHEMA))
                conn.commit()
            self._session_mk = sessionmaker(bind=self._engine)
            self._using_pg   = True
            console.print(f"[green]✓[/green] PostgreSQL connected with pool_size=10")
        except Exception as e:
            console.print(f"[yellow]ℹ PostgreSQL unavailable ({e}) — using SQLite[/yellow]")
            self._connect_sqlite()

    def _connect_sqlite(self):
        SQLITE_PATH.parent.mkdir(exist_ok=True)
        self._sqlite = str(SQLITE_PATH)
        console.print(f"[green]✓[/green] SQLite: {SQLITE_PATH}")

    @contextmanager
    def session(self):
        """Context manager for database sessions."""
        if self._using_pg:
            sess = self._session_mk()
            try:
                yield sess
                sess.commit()
            except Exception:
                sess.rollback()
                raise
            finally:
                sess.close()
        else:
            conn = sqlite3.connect(self._sqlite)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def execute(self, sql: str, params: dict = None):
        """Execute a query and return results."""
        if self._using_pg:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                conn.commit()
                # Return list of dicts to match SQLite Row interface
                return [dict(row) for row in result.mappings()]
        else:
            with sqlite3.connect(self._sqlite) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql, params or {})
                return cursor.fetchall()

    def log_algorithm_run(self, algorithm: str, start: str, end: str,
                          found: bool, total_minutes: float,
                          nodes_visited: int, elapsed_ms: float):
        """Log a routing result to the database."""
        try:
            if self._using_pg:
                self.execute("""
                    INSERT INTO algorithm_runs
                        (algorithm, start_stop, end_stop, found,
                         total_minutes, nodes_visited, elapsed_ms)
                    VALUES (:algo, :start, :end, :found, :mins, :nodes, :ms)
                """, dict(algo=algorithm, start=start, end=end,
                          found=found, mins=total_minutes,
                          nodes=nodes_visited, ms=elapsed_ms))
            else:
                with sqlite3.connect(self._sqlite) as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO algorithm_runs
                            (algorithm, start_stop, end_stop, found,
                             total_minutes, nodes_visited, elapsed_ms)
                        VALUES (?,?,?,?,?,?,?)
                    """, (algorithm, start, end, int(found),
                          total_minutes, nodes_visited, elapsed_ms))
        except Exception:
            pass   # logging failure should never break the request

    def log_delay(self, route: str, stop_id: str, delay_min: float,
                  hour: int, is_rush: bool, is_weekend: bool):
        """Log a delay observation from the GPS tracker."""
        try:
            if self._using_pg:
                self.execute("""
                    INSERT INTO delay_observations
                        (route_name, stop_id, delay_minutes, hour,
                         is_rush, is_weekend)
                    VALUES (:route, :stop, :delay, :hour, :rush, :wknd)
                """, dict(route=route, stop=stop_id, delay=delay_min,
                          hour=hour, rush=is_rush, wknd=is_weekend))
            else:
                pass   # SQLite doesn't have this table in current schema
        except Exception:
            pass

    def get_delay_stats(self, stop_id: str) -> dict:
        """Average delay by hour for a stop (last 7 days)."""
        try:
            if self._using_pg:
                rows = self.execute("""
                    SELECT hour,
                           AVG(delay_minutes)  AS avg_delay,
                           COUNT(*)            AS observations
                    FROM   delay_observations
                    WHERE  stop_id = :stop
                      AND  observed_at > NOW() - INTERVAL '7 days'
                    GROUP  BY hour
                    ORDER  BY hour
                """, {"stop": stop_id})
                return {r["hour"]: {"avg": round(r["avg_delay"],2),
                                    "n": r["observations"]}
                        for r in rows}
        except Exception:
            pass
        return {}

    def search_stops_fulltext(self, query: str, limit: int = 10) -> list:
        """Full-text stop name search (PostgreSQL only)."""
        if self._using_pg:
            try:
                rows = self.execute("""
                    SELECT stop_id, stop_name, stop_lat, stop_lon,
                           ts_rank(to_tsvector('english', stop_name),
                                   plainto_tsquery(:q)) AS rank
                    FROM   stops
                    WHERE  to_tsvector('english', stop_name)
                           @@ plainto_tsquery(:q)
                    ORDER  BY rank DESC
                    LIMIT  :limit
                """, {"q": query, "limit": limit})
                return [dict(r) for r in rows]
            except Exception:
                pass
        return []

    @property
    def backend(self) -> str:
        return "postgresql" if self._using_pg else "sqlite"

    def pool_status(self) -> dict:
        """Connection pool status (PostgreSQL only)."""
        if self._using_pg and self._engine:
            pool = self._engine.pool
            return {
                "size":       pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow":   pool.overflow(),
            }
        return {"backend": "sqlite", "pooling": False}


# ── Singleton ─────────────────────────────────────────────────────────────────
db = Database()
