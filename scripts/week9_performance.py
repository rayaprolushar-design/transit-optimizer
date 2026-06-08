"""
Week 9–10 — Multithreading + Performance
Transit Optimizer | Phase 1

What this script does:
  1. GraphLoader  — loads graph.json in a background thread while you "type"
                    Uses threading.Thread + threading.Event to signal readiness
  2. LRUCache     — caches recent query results so repeat searches are instant
                    Implements LRU (Least Recently Used) eviction from scratch
  3. CachedRouter — wraps router.py + LRUCache, logs every query to queries.log
  4. Profiler     — uses cProfile to find the slowest function in the codebase
  5. Benchmark    — measures cold vs warm (cached) query times side by side

Key CS concepts covered:
  - Threads, thread safety, Event for synchronisation  (OS)
  - LRU Cache — OrderedDict, O(1) get/put               (DSA)
  - Profiling with cProfile                             (Performance)
  - Decorator pattern (@cache.cached)                   (Design patterns)
  - File I/O — structured query logging                 (OS)

Run: python scripts/week9_performance.py
"""

import threading
import time
import json
import logging
import cProfile
import pstats
import io
from collections import OrderedDict
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from scripts.router import find_route
from scripts.search import fuzzy_find_stop

console = Console()

GRAPH_PATH = Path("data/graph_with_transfers.json")
LOG_PATH   = Path("logs/queries.log")

LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ── 1. BACKGROUND GRAPH LOADER ───────────────────────────────────────────────
#
# threading.Thread  → new OS-level thread
# threading.Event   → shared signal: set() fires it, wait() blocks until fired
#
# Key insight: the graph loads concurrently with other setup.
# In a real server, this means the first request doesn't pay the load cost.

class GraphLoader:
    """Loads transit graph in a background daemon thread."""

    def __init__(self, path: Path):
        self.path    = path
        self._graph  = None
        self._stops  = None
        self._error  = None
        self._ready  = threading.Event()
        self._thread = threading.Thread(
            target=self._load,
            daemon=True,
            name="GraphLoaderThread",
        )

    def start(self) -> "GraphLoader":
        self._thread.start()
        return self

    def _load(self):
        """Runs in background thread."""
        try:
            with open(self.path) as f:
                data = json.load(f)
            self._graph = data["graph"]
            self._stops = data["stops"]
        except Exception as e:
            self._error = e
        finally:
            self._ready.set()   # fires even on error so wait() never hangs

    def wait(self, timeout: float = 10.0) -> tuple:
        loaded = self._ready.wait(timeout=timeout)
        if not loaded:
            raise TimeoutError(f"Graph did not load within {timeout}s")
        if self._error:
            raise self._error
        return self._graph, self._stops

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()


# ── 2. LRU CACHE (from scratch) ──────────────────────────────────────────────
#
# OrderedDict preserves insertion order.
# move_to_end(key)       → marks key as most recently used
# popitem(last=False)    → removes the least recently used (front)
#
# Both operations are O(1) — making this a true O(1) LRU cache.

class LRUCache:
    """Fixed-capacity LRU cache. Thread-safe via Lock."""

    def __init__(self, capacity: int = 128):
        self.capacity  = capacity
        self._store    = OrderedDict()
        self._lock     = threading.Lock()
        self.hits      = 0
        self.misses    = 0
        self.evictions = 0

    def get(self, key: str):
        with self._lock:
            if key not in self._store:
                self.misses += 1
                return None
            self._store.move_to_end(key)   # mark as recently used
            self.hits += 1
            return self._store[key]

    def put(self, key: str, value) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
                return
            if len(self._store) >= self.capacity:
                self._store.popitem(last=False)   # evict LRU
                self.evictions += 1
            self._store[key] = value

    def stats(self) -> dict:
        total    = self.hits + self.misses
        hit_rate = self.hits / total * 100 if total else 0
        return {
            "size":      len(self._store),
            "capacity":  self.capacity,
            "hits":      self.hits,
            "misses":    self.misses,
            "evictions": self.evictions,
            "hit_rate":  round(hit_rate, 1),
        }

    def clear(self):
        with self._lock:
            self._store.clear()
            self.hits = self.misses = self.evictions = 0


# ── 3. CACHED ROUTER ─────────────────────────────────────────────────────────

class CachedRouter:
    """find_route() + LRU cache + structured logging."""

    def __init__(self, graph: dict, stops: dict, capacity: int = 128):
        self.graph  = graph
        self.stops  = stops
        self.cache  = LRUCache(capacity=capacity)

    def _key(self, sid: str, eid: str, algo: str) -> str:
        return f"{sid}:{eid}:{algo}"

    def route(self, from_name: str, to_name: str, algorithm: str = "astar") -> dict:
        sid, sname, _ = fuzzy_find_stop(from_name, self.stops)
        eid, ename, _ = fuzzy_find_stop(to_name,   self.stops)
        if not sid or not eid:
            return {"found": False, "error": "Stop not found",
                    "cache_hit": False, "elapsed_ms": 0}

        key = self._key(sid, eid, algorithm)
        t0  = time.perf_counter()

        cached = self.cache.get(key)
        if cached is not None:
            ms = (time.perf_counter() - t0) * 1000
            self._log(sname, ename, algorithm, cached, ms, hit=True)
            return {**cached, "cache_hit": True, "elapsed_ms": ms}

        result = find_route(self.graph, self.stops, sid, eid, algorithm)
        ms     = (time.perf_counter() - t0) * 1000
        self.cache.put(key, result)
        self._log(sname, ename, algorithm, result, ms, hit=False)
        return {**result, "cache_hit": False, "elapsed_ms": ms}

    def _log(self, frm, to, algo, result, elapsed_ms, hit):
        status  = f"{result.get('total_minutes', 0):.0f}min" if result.get("found") else "NO_ROUTE"
        logging.info(
            f"[{'HIT ' if hit else 'MISS'}] from={frm!r:20} to={to!r:20} "
            f"algo={algo} result={status} speed={elapsed_ms:.4f}ms"
        )


# ── 4. PROFILER ───────────────────────────────────────────────────────────────

def profile_router(graph: dict, stops: dict, n: int = 50) -> str:
    pairs = [
        ("MG Road", "HSR Layout"), ("Hebbal", "Electronic City"),
        ("Rajajinagar", "BTM Layout"), ("MG Road", "Yeshwanthpur"),
        ("Majestic", "Whitefield"),
    ]

    def workload():
        for i in range(n):
            frm, to = pairs[i % len(pairs)]
            sid, _, _ = fuzzy_find_stop(frm, stops)
            eid, _, _ = fuzzy_find_stop(to,  stops)
            if sid and eid:
                find_route(graph, stops, sid, eid, "astar")

    pr = cProfile.Profile()
    pr.enable()
    workload()
    pr.disable()

    buf = io.StringIO()
    ps  = pstats.Stats(pr, stream=buf)
    ps.strip_dirs()
    ps.sort_stats("cumulative")
    ps.print_stats(10)
    return buf.getvalue()


# ── DISPLAY HELPERS ───────────────────────────────────────────────────────────

def print_cache_stats(cache: LRUCache, title: str = "LRU Cache Stats"):
    s = cache.stats()
    t = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    t.add_column("Metric", style="bold")
    t.add_column("Value",  justify="right")
    t.add_row("Cache size",  f"{s['size']} / {s['capacity']}")
    t.add_row("Hits",        str(s["hits"]))
    t.add_row("Misses",      str(s["misses"]))
    t.add_row("Evictions",   str(s["evictions"]))
    t.add_row("Hit rate",    f"[green]{s['hit_rate']}%[/green]")
    console.print(t)


def print_benchmark(rows: list):
    t = Table(title="Cold vs Warm query times", box=box.ROUNDED, header_style="bold blue")
    t.add_column("From",      min_width=13)
    t.add_column("To",        min_width=16)
    t.add_column("Cold (ms)", justify="right")
    t.add_column("Warm (ms)", justify="right")
    t.add_column("Speedup",   justify="right")
    t.add_column("Result",    justify="right")

    for r in rows:
        sp  = r["cold_ms"] / r["warm_ms"] if r["warm_ms"] > 0 else float("inf")
        res = f"{r['total_minutes']}m" if r.get("found") else "[red]none[/red]"
        t.add_row(
            r["from"], r["to"],
            f"{r['cold_ms']:.4f}", f"{r['warm_ms']:.4f}",
            f"[green]{sp:.0f}x[/green]", res,
        )
    console.print(t)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 9–10: Performance\n"
        "[dim]Threading · LRU Cache · Profiling · Logging[/dim]",
        border_style="blue",
    ))

    # Step 1 — background loader
    console.rule("[bold]Step 1 — Background GraphLoader[/bold]")
    t0     = time.perf_counter()
    loader = GraphLoader(GRAPH_PATH).start()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  transient=True) as prog:
        prog.add_task("Loading graph in background thread...")
        graph, stops = loader.wait()

    load_ms = (time.perf_counter() - t0) * 1000
    console.print(
        f"[green]✓[/green] Graph ready: {len(stops)} stops, "
        f"{sum(len(v) for v in graph.values())} edges "
        f"in [bold]{load_ms:.1f}ms[/bold]"
    )

    # Thread diagram
    t = Table(title="What happened in the threads", box=box.ROUNDED, header_style="bold magenta")
    t.add_column("Event")
    t.add_column("Which thread")
    t.add_column("Detail")
    t.add_row("GraphLoader.start()",   "[blue]Main[/blue]",             "Spawns new OS thread")
    t.add_row("_load() begins",        "[yellow]GraphLoaderThread[/yellow]", "json.load() running")
    t.add_row("Spinner shown",         "[blue]Main[/blue]",             "Main thread free to work")
    t.add_row("Event.set()",           "[yellow]GraphLoaderThread[/yellow]", "Signals: data ready")
    t.add_row("loader.wait() returns", "[blue]Main[/blue]",             f"Unblocked after {load_ms:.1f}ms")
    console.print(t)
    console.print()

    # Step 2 — cold vs warm benchmark
    console.rule("[bold]Step 2 — LRU Cache: cold vs warm[/bold]")
    router = CachedRouter(graph, stops, capacity=64)

    test_pairs = [
        ("MG Road",     "HSR Layout"),
        ("Hebbal",      "Electronic City"),
        ("Rajajinagar", "BTM Layout"),
        ("MG Road",     "Yeshwanthpur"),
        ("Majestic",    "Whitefield"),
    ]

    rows = []
    for frm, to in test_pairs:
        r_cold = router.route(frm, to)
        r_warm = router.route(frm, to)
        rows.append({
            "from": frm, "to": to,
            "cold_ms":       r_cold["elapsed_ms"],
            "warm_ms":       r_warm["elapsed_ms"],
            "found":         r_cold.get("found"),
            "total_minutes": r_cold.get("total_minutes", 0),
        })

    print_benchmark(rows)
    console.print()
    print_cache_stats(router.cache, "Cache after 10 queries (5 cold + 5 warm)")
    console.print()

    # Step 3 — simulate real query pattern
    console.rule("[bold]Step 3 — Simulate 10 queries with repeats[/bold]")

    pattern = [
        ("MG Road",     "HSR Layout"),       # MISS
        ("MG Road",     "BTM Layout"),       # MISS
        ("Hebbal",      "Electronic City"),  # MISS
        ("MG Road",     "HSR Layout"),       # HIT
        ("Rajajinagar", "BTM Layout"),       # MISS
        ("MG Road",     "BTM Layout"),       # HIT
        ("MG Road",     "HSR Layout"),       # HIT
        ("Majestic",    "Whitefield"),       # MISS
        ("MG Road",     "HSR Layout"),       # HIT
        ("Hebbal",      "Electronic City"),  # HIT
    ]

    sim = Table(title="Query simulation", box=box.SIMPLE, header_style="bold yellow")
    sim.add_column("#",       justify="right", width=3)
    sim.add_column("From",    min_width=13)
    sim.add_column("To",      min_width=16)
    sim.add_column("Result",  justify="right", width=7)
    sim.add_column("Cache",   justify="center", width=8)
    sim.add_column("Time",    justify="right",  width=10)

    router.cache.clear()   # fresh slate for this demo
    for i, (frm, to) in enumerate(pattern, 1):
        r       = router.route(frm, to)
        mins    = f"{r['total_minutes']:.0f}m" if r.get("found") else "none"
        hit_str = "[green]HIT[/green]"  if r["cache_hit"] else "[yellow]MISS[/yellow]"
        sim.add_row(str(i), frm, to, mins, hit_str, f"{r['elapsed_ms']:.4f}ms")

    console.print(sim)
    console.print()
    print_cache_stats(router.cache, "Cache after simulation")
    console.print()

    # Step 4 — cProfile
    console.rule("[bold]Step 4 — cProfile: find the bottleneck[/bold]")
    console.print("[dim]Profiling 50 route queries...[/dim]\n")

    raw = profile_router(graph, stops, n=50)
    lines = raw.strip().split("\n")

    prof = Table(
        title="Top functions by cumulative time (50 queries)",
        box=box.SIMPLE, header_style="bold red",
    )
    prof.add_column("ncalls",   justify="right", width=8)
    prof.add_column("tottime",  justify="right", width=9)
    prof.add_column("cumtime",  justify="right", width=9)
    prof.add_column("function", min_width=36)

    for line in lines:
        parts = line.split()
        if len(parts) >= 6 and parts[0].replace("/","").isdigit():
            prof.add_row(parts[0], parts[1], parts[3], " ".join(parts[5:])[:48])

    console.print(prof)
    console.print(
        "[dim]Largest cumtime = the real bottleneck.\n"
        "For our graph heapq operations dominate — normal for Dijkstra/A*.\n"
        "On a 100k-stop graph you'd optimise by precomputing stop clusters.[/dim]\n"
    )

    # Step 5 — log file
    console.rule("[bold]Step 5 — Query log[/bold]")
    if LOG_PATH.exists():
        all_lines = LOG_PATH.read_text().strip().split("\n")
        console.print(f"[green]✓[/green] {LOG_PATH} — {len(all_lines)} total entries\n")
        for line in all_lines[-6:]:
            console.print(f"  [dim]{line}[/dim]")
    console.print()

    # Concepts panel
    console.print(Panel(
        "[bold]Why threading.Lock() in LRUCache?[/bold]\n\n"
        "  The CLI is single-threaded, so the lock costs nothing here.\n"
        "  But in Phase 2 (FastAPI), many HTTP requests arrive concurrently.\n"
        "  Without a lock, two threads can both see a cache miss, both\n"
        "  run the algorithm, and corrupt OrderedDict during simultaneous\n"
        "  writes — a classic [bold]race condition[/bold].\n\n"
        "  The lock adds ~0.001ms and eliminates the entire bug class.\n\n"
        "  [dim]This is the kind of thing interviewers at Google ask about.[/dim]",
        title="Thread Safety",
        border_style="dim",
    ))

    console.print(Panel(
        "[bold green]Week 9–10 complete![/bold green]\n\n"
        "  [bold]GraphLoader[/bold]   threading.Thread + Event sync\n"
        "  [bold]LRUCache[/bold]      O(1) get/put, thread-safe, eviction tracking\n"
        "  [bold]CachedRouter[/bold]  cache + logging wrapped cleanly\n"
        "  [bold]cProfile[/bold]      found the real bottleneck by function\n"
        "  [bold]queries.log[/bold]   every query logged with HIT/MISS\n\n"
        "Next up → [bold]Week 11–12:[/bold] pytest unit tests + polished README.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
