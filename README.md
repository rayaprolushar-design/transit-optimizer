# Transit Optimizer 🚌

A full-stack AI-powered transit route optimizer built as a first-year CS mega project.

Finds the fastest route between any two bus stops using graph algorithms (Dijkstra + A*),
predicts delays with machine learning, and displays everything on a live dashboard.

---

## Project Phases

| Phase | What gets built | Status |
|-------|----------------|--------|
| 1 | Data layer + routing algorithms (CLI) | 🔨 In progress |
| 2 | ML delay prediction model + REST API | 📅 Planned |
| 3 | Real-time web dashboard | 📅 Planned |
| 4 | Docker, CI/CD, tests, pitch docs | 📅 Planned |

---

## Phase 1 — Week 1: GTFS Explorer

### What it does
- Loads GTFS transit data (stops, routes, trips, timetables)
- Shows network stats: total stops, routes, trips
- Displays stop sequences per route
- Computes network insights (busiest stop, avg stops/trip)

### How to run

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/transit-optimizer.git
cd transit-optimizer

# 2. Install dependencies
pip install pandas rich

# 3. Run the explorer
python scripts/week1_explore.py
```

### Data source
Uses GTFS (General Transit Feed Specification) — the open standard used by
Google Maps, Citymapper, and every major transit app worldwide.

Free Indian GTFS feeds:
- https://otd.in (BMTC Bengaluru, DIMTS Delhi)
- https://gtfs.org/resources/gtfs_data/

---

## Project structure

```
transit-optimizer/
├── data/
│   └── gtfs/              # GTFS feed files
│       ├── stops.txt
│       ├── routes.txt
│       ├── trips.txt
│       └── stop_times.txt
├── scripts/
│   └── week1_explore.py   # Week 1: data exploration
├── tests/                 # pytest tests (added Week 11)
├── logs/                  # query logs (added Week 9)
└── README.md
```

---

## Topics covered (Year 1 CS)

- **DSA** — graphs, Dijkstra, A*, priority queues, adjacency lists
- **DBMS** — SQLite schema design, SQL queries, indexing
- **OS** — multithreading, file I/O, process profiling
- **Computer Networks** — REST APIs, WebSockets, HTTP
- **Mathematics** — Haversine formula, ML model evaluation

---

## Built with
Python · pandas · SQLite · rich · FastAPI · React · Docker
