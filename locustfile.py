"""
locustfile.py — Upgrade 7: Load Testing with Locust
Transit Optimizer

What this does:
  Simulates hundreds of concurrent users hitting your FastAPI server.
  Measures: requests/second, response time (avg, p50, p95, p99), error rate.

Run:
  # Install locust
  pip install locust

  # Start FastAPI first:
  uvicorn api.server:app --workers 4 --port 8000

  # Run load test (headless — outputs to terminal):
  locust -f locustfile.py --headless \
         --users 100 --spawn-rate 10 \
         --run-time 60s \
         --host http://localhost:8000

  # Run with web UI (see live charts at localhost:8089):
  locust -f locustfile.py --host http://localhost:8000

  # Against Railway production:
  locust -f locustfile.py --headless \
         --users 200 --spawn-rate 20 \
         --run-time 120s \
         --host https://transit-optimizer-xxxx.railway.app

Target metrics (what to put in your email):
  Throughput:  > 500 req/s  (good), > 800 req/s (excellent)
  p99 latency: < 100ms      (good), < 50ms       (excellent)
  Error rate:  < 0.1%

Key Locust concepts:
  HttpUser   — simulates one virtual user making HTTP requests
  @task(N)   — decorator with weight N (higher = more frequent)
  wait_time  — pause between requests (models real user behaviour)
  TaskSet    — group related tasks together
"""

import random
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# ── Test data ─────────────────────────────────────────────────────────────────
# Real stop IDs from your transit graph
STOP_PAIRS = [
    ("MG Road",      "HSR Layout"),
    ("MG Road",      "BTM Layout"),
    ("Hebbal",       "Electronic City"),
    ("Indiranagar",  "Majestic"),
    ("Rajajinagar",  "BTM Layout"),
    ("Silk Board",   "Yeshwanthpur"),
    ("Koramangala",  "MG Road"),
    ("Whitefield",   "Silk Board"),
]

STOP_IDS = ["S001","S002","S004","S006","S007","S010","S012","S013","S017","S018","S020"]


# ── User behaviour: Route Planner ─────────────────────────────────────────────
# Models an IT employee looking up their commute route

class RoutePlannerUser(HttpUser):
    """
    Simulates a user on the Route Planner page.
    Most requests hit cached routes (realistic — same routes repeated).
    """
    wait_time = between(1, 3)   # 1-3 second pause between requests

    @task(5)
    def get_route_astar(self):
        """Most common task — search a route with A*."""
        frm, to = random.choice(STOP_PAIRS)
        with self.client.get(
            f"/route?from={frm}&to={to}&algorithm=astar",
            name="/route [astar]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("found"):
                    resp.failure("Route not found")
            elif resp.status_code == 404:
                resp.success()   # no route is valid, not a server error
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def get_route_dijkstra(self):
        """Occasional Dijkstra comparison."""
        frm, to = random.choice(STOP_PAIRS)
        self.client.get(
            f"/route?from={frm}&to={to}&algorithm=dijkstra",
            name="/route [dijkstra]",
        )

    @task(3)
    def predict_delay(self):
        """Delay predictor — POST with ML model."""
        stop_id = random.choice(STOP_IDS)
        hour    = random.randint(6, 22)
        self.client.post(
            "/predict-delay",
            json={
                "stop_id":            stop_id,
                "hour":               hour,
                "is_weekend":         random.randint(0, 1),
                "prior_stop_delay":   round(random.uniform(0, 5), 1),
                "temp_deviation":     round(random.uniform(0, 2), 1),
                "stop_sequence_norm": round(random.uniform(0, 1), 1),
                "route_type":         random.choice([1, 3]),
                "n_stops_on_trip":    random.randint(3, 8),
            },
            name="/predict-delay",
        )

    @task(1)
    def get_stops(self):
        """Load stop list (used on page load — less frequent)."""
        self.client.get("/stops?limit=50", name="/stops")

    @task(1)
    def health_check(self):
        """Health endpoint — very fast, always hits."""
        self.client.get("/", name="/health")

    @task(2)
    def get_stats(self):
        """Analytics page stats."""
        self.client.get("/stats", name="/stats")


# ── User behaviour: Display Board ─────────────────────────────────────────────
# Models many physical display boards polling at bus stops

class DisplayBoardUser(HttpUser):
    """
    Simulates display boards polling the /board endpoint every 30s.
    Many boards = high sustained load.
    """
    wait_time = between(25, 35)   # poll every ~30 seconds

    @task(10)
    def get_board(self):
        """Primary display board poll."""
        stop_id = random.choice(STOP_IDS)
        self.client.get(
            f"/board/{stop_id}?n=6",
            name="/board/{stop_id}",
        )

    @task(3)
    def get_live_delay(self):
        """Live delay check."""
        stop_id = random.choice(STOP_IDS)
        self.client.get(
            f"/live-delays/{stop_id}",
            name="/live-delays/{stop_id}",
        )


# ── Mixed workload (default) ──────────────────────────────────────────────────
# Realistic mix: 80% route planners, 20% display boards

class MixedUser(HttpUser):
    """
    Realistic mixed workload for overall API testing.
    Use this for the headline number in your email.
    """
    wait_time = between(0.5, 2)

    @task(8)
    def route(self):
        frm, to = random.choice(STOP_PAIRS)
        self.client.get(
            f"/route?from={frm}&to={to}",
            name="/route",
        )

    @task(4)
    def predict(self):
        self.client.post("/predict-delay", json={
            "stop_id": random.choice(STOP_IDS),
            "hour": random.randint(6, 22),
            "is_weekend": 0, "prior_stop_delay": 1.0,
            "temp_deviation": 0.5, "stop_sequence_norm": 0.5,
            "route_type": 3, "n_stops_on_trip": 6,
        }, name="/predict-delay")

    @task(2)
    def board(self):
        self.client.get(
            f"/board/{random.choice(STOP_IDS)}",
            name="/board",
        )

    @task(1)
    def health(self):
        self.client.get("/", name="/")


# ── Event hooks ───────────────────────────────────────────────────────────────
# Print a summary when the test ends

@events.quitting.add_listener
def on_quit(environment, **kwargs):
    stats = environment.stats.total
    print("\n" + "="*60)
    print("LOAD TEST RESULTS")
    print("="*60)
    print(f"Requests:         {stats.num_requests:,}")
    print(f"Failures:         {stats.num_failures:,}")
    print(f"Error rate:       {stats.fail_ratio*100:.2f}%")
    print(f"Throughput:       {stats.current_rps:.0f} req/s")
    print(f"Avg response:     {stats.avg_response_time:.0f}ms")
    print(f"p50 response:     {stats.get_response_time_percentile(0.5):.0f}ms")
    print(f"p95 response:     {stats.get_response_time_percentile(0.95):.0f}ms")
    print(f"p99 response:     {stats.get_response_time_percentile(0.99):.0f}ms")
    print("="*60)
    print("\nPut these numbers in your email to companies.")
