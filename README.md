# SmartCity Transit Optimizer 🚌

![Tests](https://img.shields.io/badge/tests-49%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Phase](https://img.shields.io/badge/phase-1%20complete-blue)

An end-to-end transit routing engine built as a first-year CS mega project.  
Finds the fastest route between any two bus/metro stops using graph algorithms,
caches results with a hand-rolled LRU cache, and outputs Google Maps-style directions.

```
$ python main.py --from "MG Road" --to "HSR Layout"

  MG Road  →  HSR Layout

  Total time: 25 min   Segments: 1   Transfers: 0
  Algorithm: ASTAR  |  3 nodes visited  |  0.023ms

  🚌  Route 33   MG Road → HSR Layout   2 stops     25m
```

---

## What it does

| Feature | Detail |
|---|---|
| Routing engine | Dijkstra + A* on a weighted directed graph |
| Data source | GTFS (General Transit Feed Specification) |
| Transfer edges | Walking connections between nearby stops (≤1.2km) |
| Directions | Google Maps-style: 🚌 transit + 🚶 walk segments |
| Fuzzy search | Type "mg road" or "majestic" — no exact names needed |
| LRU cache | Repeat queries return in ~0.001ms (39× speedup) |
| Threading | Graph loads in a background thread while CLI starts |
| Logging | Every query logged to `logs/queries.log` with HIT/MISS |
| Tests | 49 pytest tests — unit, integration, thread-safety |

---

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/transit-optimizer.git
cd transit-optimizer
pip install -r requirements.txt

# Build the database and graph (run once)
python scripts/week2_database.py
python scripts/week3_graph.py
python scripts/week6_transfers.py

# Find a route
python main.py --from "MG Road" --to "BTM Layout"

# Switch algorithm
python main.py --from "Hebbal" --to "Electronic City" --algorithm dijkstra

# Disable walking transfers
python main.py --from "MG Road" --to "HSR Layout" --no-transfers

# List all stops (with optional filter)
python main.py --list-stops
python main.py --list-stops --filter "metro"

# Graph stats
python main.py --stats
```

---

## Algorithm comparison

Both algorithms find identical optimal paths. A* visits fewer nodes by using
straight-line (Haversine) distance as a geographic heuristic.

| Route | Dijkstra nodes | A* nodes | Saving |
|---|---|---|---|
| MG Road → BTM Layout | 8 | 3 | 62% |
| MG Road → Yeshwanthpur | 12 | 4 | 67% |
| Hebbal → Electronic City | 22 | 6 | 73% |

On a city-scale graph (100k+ stops), A* is typically 10–50× faster than Dijkstra.

---

## LRU Cache performance

```
Query: MG Road → Yeshwanthpur
  Cold (cache miss):  0.0319ms
  Warm (cache hit):   0.0010ms
  Speedup:            33×
```

Cache is implemented from scratch using `collections.OrderedDict` for O(1)
get and put. Thread-safe via `threading.Lock` for Phase 2 (concurrent API).

---

## Project structure

```
transit-optimizer/
├── main.py                     CLI entrypoint (click + rich)
├── scripts/
│   ├── router.py               A* and Dijkstra routing engine
│   ├── search.py               Fuzzy stop-name matching
│   ├── week1_explore.py        GTFS data exploration
│   ├── week2_database.py       SQLite schema + data loader
│   ├── week3_graph.py          Adjacency list graph builder
│   ├── week4_dijkstra.py       Dijkstra with heap trace
│   ├── week5_astar.py          A* with Haversine heuristic
│   ├── week6_transfers.py      Walking transfer edge injection
│   └── week9_performance.py   Threading, LRU cache, cProfile
├── tests/
│   └── test_phase1.py          49 pytest tests
├── data/
│   ├── transit.db              SQLite: stops, routes, trips, stop_times
│   ├── graph.json              Base transit graph
│   └── graph_with_transfers.json  Enriched graph with walk edges
├── logs/
│   └── queries.log             Structured query log (HIT/MISS)
└── requirements.txt
```

---

## Year 1 CS topics covered

| Topic | Where |
|---|---|
| **DSA** — graphs, Dijkstra, A*, heapq, BFS | weeks 3–5 |
| **DSA** — LRU cache, OrderedDict, O(1) ops | week 9 |
| **DBMS** — SQLite schema, FK constraints, indexes, JOINs | week 2 |
| **OS** — threading, Event sync, Lock, file I/O, logging | week 9 |
| **Computer Networks** — REST API ready (Phase 2) | Phase 2 |
| **Maths** — Haversine formula, heuristic admissibility | week 5 |

---

## Test suite

```
$ pytest tests/test_phase1.py -v

49 passed in 0.18s

TestHaversine      5 tests   Haversine distance, heuristic admissibility
TestGraph          8 tests   Adjacency list structure, edge weights
TestLRUCache      12 tests   Eviction, LRU order, thread safety, hit rate
TestRouting       10 tests   Shortest paths, path validity, directions
TestFuzzySearch    7 tests   Case-insensitive matching, partial matches
TestIntegration    7 tests   End-to-end, concurrent reads, warm queries
```

---

## Roadmap

| Phase | Status | What gets built |
|---|---|---|
| 1 | ✅ Complete | Data layer, graph, routing CLI |
| 2 | 📅 Planned | ML delay prediction + FastAPI REST endpoint |
| 3 | 📅 Planned | React dashboard with live WebSocket updates |
| 4 | 📅 Planned | Docker, CI/CD, production hardening |

---

## Built with

Python · pandas · SQLite · click · rich · pytest · threading

---

## Data source

GTFS (General Transit Feed Specification) — the open standard used by
Google Maps, Citymapper, and Apple Maps worldwide.

Free Indian feeds: [otd.in](https://otd.in) (BMTC Bengaluru, DIMTS Delhi)
