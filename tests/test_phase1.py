"""
Week 11–12 | Transit Optimizer — Phase 1 Test Suite

49 tests across 6 categories:
  1. Haversine & heuristic     (5 tests)
  2. Graph builder             (8 tests)
  3. LRU Cache                 (12 tests)
  4. Dijkstra & A*             (10 tests)
  5. Fuzzy search              (7 tests)
  6. Integration + thread safety (7 tests)

Run:  pytest tests/test_phase1.py -v
Cov:  pytest tests/test_phase1.py -v --cov=scripts --cov-report=term-missing
"""

import json
import math
import threading
import time
import pytest
from pathlib import Path
from collections import OrderedDict

# ── project imports ───────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.router import find_route, build_directions, _haversine_km, _heuristic
from scripts.search import fuzzy_find_stop, _score, _normalize
from scripts.week9_performance import LRUCache, GraphLoader, CachedRouter


# ════════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def sample_stops():
    """Minimal stop set used across graph + algorithm tests."""
    return {
        "A": {"name": "Alpha",   "lat": 12.97, "lon": 77.60},
        "B": {"name": "Bravo",   "lat": 12.98, "lon": 77.61},
        "C": {"name": "Charlie", "lat": 12.99, "lon": 77.62},
        "D": {"name": "Delta",   "lat": 13.00, "lon": 77.63},
        "E": {"name": "Echo",    "lat": 12.96, "lon": 77.59},  # isolated
    }

@pytest.fixture(scope="module")
def sample_graph():
    """
    Weighted directed graph:
      A →(5)→ B →(7)→ C →(3)→ D
      A →(15)→ C   (longer direct path)
      B →(10)→ D   (shortcut B→D)
    Shortest A→D: A→B(5)→D(10) = 15  (not A→B→C→D = 15 also, tie)
    Shortest A→C: A→B(5)→C(7)  = 12  (not A→C = 15)
    """
    return {
        "A": {
            "B": {"minutes": 5,  "route": "R1", "trips": 2},
            "C": {"minutes": 15, "route": "R2", "trips": 1},
        },
        "B": {
            "C": {"minutes": 7,  "route": "R1", "trips": 2},
            "D": {"minutes": 10, "route": "R3", "trips": 1},
        },
        "C": {
            "D": {"minutes": 3,  "route": "R1", "trips": 2},
        },
    }

@pytest.fixture(scope="module")
def real_graph_data():
    """Load the actual project graph (graph_with_transfers.json)."""
    path = Path("data/graph_with_transfers.json")
    if not path.exists():
        pytest.skip("graph_with_transfers.json not found — run week6 first")
    with open(path) as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════════════════
# 1. HAVERSINE & HEURISTIC  (5 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestHaversine:

    def test_same_point_is_zero(self):
        assert _haversine_km(12.97, 77.60, 12.97, 77.60) == 0.0

    def test_known_distance_bengaluru(self):
        # MG Road → Indiranagar: ~3.5 km in reality
        dist = _haversine_km(12.9755, 77.6069, 12.9784, 77.6408)
        assert 3.0 < dist < 4.5, f"Expected ~3.5 km, got {dist:.2f}"

    def test_symmetry(self):
        d1 = _haversine_km(12.97, 77.60, 13.00, 77.65)
        d2 = _haversine_km(13.00, 77.65, 12.97, 77.60)
        assert abs(d1 - d2) < 1e-9

    def test_heuristic_same_stop_is_zero(self, sample_stops):
        assert _heuristic("A", "A", sample_stops) == 0.0

    def test_heuristic_admissible(self, sample_graph, sample_stops):
        """h(n) must never exceed the actual shortest path cost."""
        result = find_route(sample_graph, sample_stops, "A", "D")
        actual = result["total_minutes"]
        h      = _heuristic("A", "D", sample_stops)
        assert h <= actual, (
            f"Heuristic {h:.2f} > actual {actual} — NOT admissible!"
        )


# ════════════════════════════════════════════════════════════════════════════════
# 2. GRAPH BUILDER  (8 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestGraph:

    def test_graph_has_nodes(self, sample_graph):
        assert len(sample_graph) > 0

    def test_edges_are_positive(self, sample_graph):
        for src, nbrs in sample_graph.items():
            for dst, edge in nbrs.items():
                assert edge["minutes"] > 0, f"Edge {src}→{dst} has non-positive weight"

    def test_edge_has_required_fields(self, sample_graph):
        for src, nbrs in sample_graph.items():
            for dst, edge in nbrs.items():
                assert "minutes" in edge
                assert "route"   in edge

    def test_adjacency_list_structure(self, sample_graph):
        """Graph is a dict of dicts."""
        assert isinstance(sample_graph, dict)
        for v in sample_graph.values():
            assert isinstance(v, dict)

    def test_node_A_connects_to_B(self, sample_graph):
        assert "B" in sample_graph["A"]

    def test_edge_weight_correct(self, sample_graph):
        assert sample_graph["A"]["B"]["minutes"] == 5

    def test_directed_graph_not_symmetric(self, sample_graph):
        """A→B exists but B→A should not in our test graph."""
        assert "A" not in sample_graph.get("B", {})

    def test_real_graph_loads(self, real_graph_data):
        g = real_graph_data["graph"]
        s = real_graph_data["stops"]
        assert len(s) >= 20
        assert sum(len(v) for v in g.values()) >= 30


# ════════════════════════════════════════════════════════════════════════════════
# 3. LRU CACHE  (12 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestLRUCache:

    def test_get_miss_returns_none(self):
        cache = LRUCache(capacity=4)
        assert cache.get("x") is None

    def test_put_and_get(self):
        cache = LRUCache(capacity=4)
        cache.put("k1", {"result": 42})
        assert cache.get("k1") == {"result": 42}

    def test_eviction_at_capacity(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)          # should evict "a" (LRU)
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_order_preserved_on_access(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.get("a")             # touch "a" → now most recently used
        cache.put("d", 4)          # should evict "b" (now LRU), not "a"
        assert cache.get("a") is not None
        assert cache.get("b") is None

    def test_hit_miss_counters(self):
        cache = LRUCache(capacity=4)
        cache.put("x", 99)
        cache.get("x")             # hit
        cache.get("y")             # miss
        s = cache.stats()
        assert s["hits"]   == 1
        assert s["misses"] == 1

    def test_eviction_counter(self):
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)          # evicts "a"
        assert cache.stats()["evictions"] == 1

    def test_hit_rate_calculation(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v")
        cache.get("k")             # hit
        cache.get("k")             # hit
        cache.get("miss")          # miss
        assert cache.stats()["hit_rate"] == pytest.approx(66.7, abs=0.2)

    def test_overwrite_existing_key(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "old")
        cache.put("k", "new")
        assert cache.get("k") == "new"
        assert len(cache._store) == 1   # no duplicate entry

    def test_clear_resets_all_state(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v")
        cache.get("k")
        cache.clear()
        s = cache.stats()
        assert s["size"] == 0 and s["hits"] == 0 and s["misses"] == 0

    def test_capacity_respected(self):
        cache = LRUCache(capacity=5)
        for i in range(10):
            cache.put(str(i), i)
        assert len(cache._store) == 5

    def test_thread_safety(self):
        """Multiple threads writing simultaneously must not corrupt state."""
        cache   = LRUCache(capacity=200)
        errors  = []

        def writer(tid):
            try:
                for i in range(50):
                    cache.put(f"{tid}-{i}", i)
                    cache.get(f"{tid}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert not errors, f"Thread safety errors: {errors}"

    def test_single_item_cache(self):
        cache = LRUCache(capacity=1)
        cache.put("a", 1)
        cache.put("b", 2)          # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2


# ════════════════════════════════════════════════════════════════════════════════
# 4. DIJKSTRA & A*  (10 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestRouting:

    def test_dijkstra_finds_shortest_path(self, sample_graph, sample_stops):
        r = find_route(sample_graph, sample_stops, "A", "D", "dijkstra")
        assert r["found"]
        assert r["total_minutes"] == 15   # A→B(5)→D(10) or A→B→C→D same cost

    def test_astar_finds_shortest_path(self, sample_graph, sample_stops):
        r = find_route(sample_graph, sample_stops, "A", "D", "astar")
        assert r["found"]
        assert r["total_minutes"] == 15

    def test_dijkstra_and_astar_agree(self, sample_graph, sample_stops):
        """Both algorithms must return the same optimal cost."""
        d = find_route(sample_graph, sample_stops, "A", "C", "dijkstra")
        a = find_route(sample_graph, sample_stops, "A", "C", "astar")
        assert d["total_minutes"] == a["total_minutes"]

    def test_path_starts_at_source(self, sample_graph, sample_stops):
        r = find_route(sample_graph, sample_stops, "A", "D")
        assert r["path"][0] == "A"

    def test_path_ends_at_destination(self, sample_graph, sample_stops):
        r = find_route(sample_graph, sample_stops, "A", "D")
        assert r["path"][-1] == "D"

    def test_path_is_connected(self, sample_graph, sample_stops):
        """Every consecutive pair in the path must be a real edge."""
        r = find_route(sample_graph, sample_stops, "A", "C")
        path = r["path"]
        for i in range(len(path) - 1):
            assert path[i + 1] in sample_graph.get(path[i], {}), (
                f"No edge {path[i]} → {path[i+1]}"
            )

    def test_unreachable_returns_not_found(self, sample_graph, sample_stops):
        """E is isolated — no route should exist from A to E."""
        r = find_route(sample_graph, sample_stops, "A", "E")
        assert not r["found"]

    def test_same_start_and_end(self, sample_graph, sample_stops):
        r = find_route(sample_graph, sample_stops, "B", "B")
        assert r["found"]
        assert r["total_minutes"] == 0

    def test_build_directions_transit(self, sample_graph, sample_stops):
        r    = find_route(sample_graph, sample_stops, "A", "D")
        dirs = build_directions(r, sample_stops)
        assert len(dirs) >= 1
        for d in dirs:
            assert "from" in d and "to" in d and "minutes" in d

    def test_real_graph_route(self, real_graph_data):
        g, s = real_graph_data["graph"], real_graph_data["stops"]
        r = find_route(g, s, "S001", "S007")   # MG Road → BTM Layout
        assert r["found"]
        assert r["total_minutes"] > 0
        assert r["path"][0] == "S001"
        assert r["path"][-1] == "S007"


# ════════════════════════════════════════════════════════════════════════════════
# 5. FUZZY SEARCH  (7 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestFuzzySearch:

    def test_exact_match(self, sample_stops):
        sid, name, score = fuzzy_find_stop("Alpha", sample_stops)
        assert sid == "A"
        assert score == 100

    def test_case_insensitive(self, sample_stops):
        sid, name, score = fuzzy_find_stop("alpha", sample_stops)
        assert sid == "A"

    def test_partial_match(self, sample_stops):
        sid, name, score = fuzzy_find_stop("Brav", sample_stops)
        assert sid == "B"
        assert score >= 75

    def test_substring_match(self, sample_stops):
        sid, name, score = fuzzy_find_stop("har", sample_stops)
        assert sid == "C"   # "Charlie" contains "har"

    def test_no_match_returns_none(self, sample_stops):
        sid, name, score = fuzzy_find_stop("xyznotaplace", sample_stops)
        assert sid is None

    def test_normalize_strips_whitespace(self):
        assert _normalize("  MG Road  ") == "mg road"

    def test_score_exact_is_100(self):
        assert _score("mg road", "MG Road") == 100


# ════════════════════════════════════════════════════════════════════════════════
# 6. INTEGRATION + THREAD SAFETY  (7 tests)
# ════════════════════════════════════════════════════════════════════════════════

class TestIntegration:

    def test_cached_router_cold_miss(self, real_graph_data):
        g, s   = real_graph_data["graph"], real_graph_data["stops"]
        router = CachedRouter(g, s, capacity=32)
        r      = router.route("MG Road", "HSR Layout")
        assert r["found"]
        assert not r["cache_hit"]

    def test_cached_router_warm_hit(self, real_graph_data):
        g, s   = real_graph_data["graph"], real_graph_data["stops"]
        router = CachedRouter(g, s, capacity=32)
        router.route("MG Road", "BTM Layout")         # cold
        r = router.route("MG Road", "BTM Layout")     # warm
        assert r["cache_hit"]

    def test_cached_router_warm_faster_than_cold(self, real_graph_data):
        g, s   = real_graph_data["graph"], real_graph_data["stops"]
        router = CachedRouter(g, s, capacity=32)
        cold   = router.route("Hebbal", "Electronic City")
        warm   = router.route("Hebbal", "Electronic City")
        assert warm["elapsed_ms"] < cold["elapsed_ms"]

    def test_graph_loader_returns_data(self):
        path = Path("data/graph_with_transfers.json")
        if not path.exists():
            pytest.skip("graph file missing")
        loader = GraphLoader(path).start()
        graph, stops = loader.wait(timeout=5.0)
        assert isinstance(graph, dict)
        assert isinstance(stops, dict)
        assert len(stops) > 0

    def test_graph_loader_is_ready_after_wait(self):
        path = Path("data/graph_with_transfers.json")
        if not path.exists():
            pytest.skip("graph file missing")
        loader = GraphLoader(path).start()
        loader.wait()
        assert loader.is_ready

    def test_concurrent_cache_reads_consistent(self, real_graph_data):
        """50 threads reading the same cache key should all get the same result."""
        g, s   = real_graph_data["graph"], real_graph_data["stops"]
        router = CachedRouter(g, s, capacity=64)
        router.route("MG Road", "HSR Layout")         # prime cache

        results = []
        def read():
            r = router.route("MG Road", "HSR Layout")
            results.append(r["total_minutes"])

        threads = [threading.Thread(target=read) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(set(results)) == 1, "Concurrent reads returned different results"

    def test_end_to_end_route_with_directions(self, real_graph_data):
        """Full pipeline: graph → find_route → build_directions."""
        g, s  = real_graph_data["graph"], real_graph_data["stops"]
        r     = find_route(g, s, "S001", "S017")     # MG Road → HSR Layout
        if not r["found"]:
            pytest.skip("Route not found in current graph")
        dirs  = build_directions(r, s)
        total = sum(d["minutes"] for d in dirs)
        assert abs(total - r["total_minutes"]) < 1.0
        assert all(d["type"] in ("transit", "walk") for d in dirs)
