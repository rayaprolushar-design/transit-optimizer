"""
infra/cache.py — Upgrade 7: Redis Cache
Replaces the in-memory LRU dict from Week 9 with Redis.

Why Redis over Python dict?
  1. Survives server restart (persistent if configured)
  2. Shared across multiple FastAPI workers/processes
  3. TTL (Time To Live) — entries expire automatically
  4. Industry standard — used by Uber, Amazon, every major company
  5. Atomic operations — no race conditions under concurrent load

How it connects to your existing code:
  Week 9 LRUCache:  get(key) → value | None
  RedisCache:       get(key) → value | None   ← same interface
  FastAPI server:   imports cache, calls cache.get/set  ← unchanged

Environment variables:
  REDIS_URL  — Redis connection string
               Local:      redis://localhost:6379
               Railway:    redis://default:password@host:port (from Railway Redis plugin)
               No Redis:   falls back to in-memory dict automatically
"""

import json
import os
import time
import threading
from collections import OrderedDict
from typing import Any, Optional
from rich.console import Console

console = Console()

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379")
DEFAULT_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))   # 5 minutes


# ── Try to import Redis ────────────────────────────────────────────────────────

try:
    import redis as redis_lib
    _redis_available = True
except ImportError:
    _redis_available = False


# ── Redis Cache ────────────────────────────────────────────────────────────────

class RedisCache:
    """
    Redis-backed cache with automatic fallback to in-memory dict.

    Key design decisions:
      - Serialise values as JSON (not pickle — JSON is safe and readable)
      - Prefix all keys with "transit:" to avoid conflicts in shared Redis
      - TTL on every key — prevents stale data building up
      - Thread-safe fallback uses OrderedDict (same as Week 9 LRUCache)
      - Metrics tracked regardless of backend (hits, misses, errors)
    """

    def __init__(self, ttl: int = DEFAULT_TTL, prefix: str = "transit"):
        self.ttl      = ttl
        self.prefix   = prefix
        self._client  = None
        self._using_redis = False

        # Stats
        self.hits      = 0
        self.misses    = 0
        self.errors    = 0
        self.sets      = 0
        self._lock     = threading.Lock()

        # Fallback in-memory store
        self._memory: OrderedDict = OrderedDict()
        self._memory_ttl: dict    = {}   # key → expiry timestamp
        self._capacity = 512

        self._connect()

    def _connect(self):
        """Attempt Redis connection. Fall back silently if unavailable."""
        if not _redis_available:
            console.print("[yellow]ℹ[/yellow] redis-py not installed — using in-memory cache")
            return
        try:
            self._client = redis_lib.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            self._using_redis = True
            console.print(f"[green]✓[/green] Redis connected: {REDIS_URL}")
        except Exception as e:
            console.print(f"[yellow]ℹ Redis unavailable ({e}) — using in-memory cache[/yellow]")
            self._client = None

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    # ── Get ────────────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value. Returns None on miss or error."""
        with self._lock:
            if self._using_redis:
                return self._redis_get(key)
            else:
                return self._memory_get(key)

    def _redis_get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(self._key(key))
            if raw is None:
                self.misses += 1
                return None
            self.hits += 1
            return json.loads(raw)
        except Exception:
            self.errors += 1
            return self._memory_get(key)   # fallback to memory on Redis error

    def _memory_get(self, key: str) -> Optional[Any]:
        # Check TTL
        expiry = self._memory_ttl.get(key)
        if expiry and time.time() > expiry:
            self._memory.pop(key, None)
            self._memory_ttl.pop(key, None)
            self.misses += 1
            return None
        if key not in self._memory:
            self.misses += 1
            return None
        self._memory.move_to_end(key)
        self.hits += 1
        return self._memory[key]

    # ── Set ────────────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value with TTL. Returns True on success."""
        ttl = ttl or self.ttl
        with self._lock:
            if self._using_redis:
                return self._redis_set(key, value, ttl)
            else:
                return self._memory_set(key, value, ttl)

    # Alias put to set to ensure absolute compatibility with LRUCache interface
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        return self.set(key, value, ttl)

    def _redis_set(self, key: str, value: Any, ttl: int) -> bool:
        try:
            self._client.setex(self._key(key), ttl, json.dumps(value))
            self.sets += 1
            return True
        except Exception:
            self.errors += 1
            return self._memory_set(key, value, ttl)

    def _memory_set(self, key: str, value: Any, ttl: int) -> bool:
        if key in self._memory:
            self._memory.move_to_end(key)
        elif len(self._memory) >= self._capacity:
            oldest = next(iter(self._memory))
            self._memory.pop(oldest)
            self._memory_ttl.pop(oldest, None)
        self._memory[key] = value
        self._memory_ttl[key] = time.time() + ttl
        self.sets += 1
        return True

    # ── Delete ─────────────────────────────────────────────────────────────────

    def delete(self, key: str) -> bool:
        with self._lock:
            if self._using_redis:
                try:
                    self._client.delete(self._key(key))
                    return True
                except Exception:
                    pass
            self._memory.pop(key, None)
            self._memory_ttl.pop(key, None)
            return True

    def flush(self, pattern: str = "*") -> int:
        """Delete all keys matching pattern (useful for cache invalidation)."""
        if self._using_redis:
            try:
                keys = self._client.keys(f"{self.prefix}:{pattern}")
                if keys:
                    return self._client.delete(*keys)
            except Exception:
                pass
        n = len(self._memory)
        self._memory.clear()
        self._memory_ttl.clear()
        return n

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        total    = self.hits + self.misses
        hit_rate = round(self.hits / total * 100, 1) if total else 0

        base = {
            "backend":   "redis" if self._using_redis else "memory",
            "hits":      self.hits,
            "misses":    self.misses,
            "sets":      self.sets,
            "errors":    self.errors,
            "hit_rate":  hit_rate,
        }

        if self._using_redis:
            try:
                info = self._client.info("memory")
                base["redis_memory_mb"] = round(
                    info.get("used_memory", 0) / 1024 / 1024, 2
                )
                base["redis_connected"] = True
            except Exception:
                base["redis_connected"] = False
        else:
            base["memory_size"] = len(self._memory)
            base["memory_capacity"] = self._capacity

        return base

    @property
    def is_redis(self) -> bool:
        return self._using_redis


# ── Singleton ─────────────────────────────────────────────────────────────────
# One shared cache instance for the whole FastAPI app.
# route_cache and pred_cache are namespaced with different prefixes.

route_cache = RedisCache(ttl=300,  prefix="transit:route")
pred_cache  = RedisCache(ttl=60,   prefix="transit:pred")
board_cache = RedisCache(ttl=30,   prefix="transit:board")
