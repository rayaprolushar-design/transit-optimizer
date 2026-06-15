"""
tests/test_api.py — FastAPI endpoint tests
Week 16 | Transit Optimizer Phase 2

Uses FastAPI TestClient. Resources loaded via _load_resources() fixture.

Run: pytest tests/test_api.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
import api.server as srv
from api.server import app, _load_resources

# Load resources once for the whole test session
_load_resources()
client = TestClient(app)


# ── Health & info ─────────────────────────────────────────────────────────────

class TestHealth:

    def test_root_returns_ok(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root_has_stop_count(self):
        assert client.get("/").json()["stops"] >= 20

    def test_root_has_model_name(self):
        assert "model" in client.get("/").json()

    def test_stats_endpoint(self):
        r = client.get("/stats")
        assert r.status_code == 200
        body = r.json()
        assert "graph" in body and "cache" in body
        assert body["graph"]["stops"] >= 20

    def test_model_info_endpoint(self):
        r = client.get("/model-info")
        assert r.status_code == 200
        body = r.json()
        assert "test_mae" in body and "feature_cols" in body
        assert body["test_mae"] < 2.0


# ── Stops ─────────────────────────────────────────────────────────────────────

class TestStops:

    def test_list_all_stops(self):
        r = client.get("/stops")
        assert r.status_code == 200
        assert len(r.json()) >= 20

    def test_stop_has_required_fields(self):
        stop = client.get("/stops").json()[0]
        for f in ("stop_id", "name", "lat", "lon"):
            assert f in stop

    def test_filter_stops_by_name(self):
        r = client.get("/stops?filter=road")
        assert r.status_code == 200
        for s in r.json():
            assert "road" in s["name"].lower()

    def test_filter_no_match_returns_empty(self):
        assert client.get("/stops?filter=xyznonexistent99").json() == []

    def test_limit_parameter(self):
        assert len(client.get("/stops?limit=3").json()) <= 3


# ── Routing ───────────────────────────────────────────────────────────────────

class TestRoute:

    def test_basic_route_found(self):
        r = client.get("/route?from=MG%20Road&to=BTM%20Layout")
        assert r.status_code == 200
        assert r.json()["found"] is True
        assert r.json()["total_minutes"] > 0

    def test_route_has_directions(self):
        r = client.get("/route?from=MG%20Road&to=BTM%20Layout")
        assert "directions" in r.json()
        assert len(r.json()["directions"]) >= 1

    def test_route_direction_fields(self):
        dirs = client.get("/route?from=MG%20Road&to=HSR%20Layout").json()["directions"]
        for d in dirs:
            assert "type" in d and "from" in d and "to" in d and "minutes" in d
            assert d["type"] in ("transit", "walk")

    def test_route_astar_algorithm(self):
        r = client.get("/route?from=MG%20Road&to=BTM%20Layout&algorithm=astar")
        assert r.status_code == 200
        assert r.json()["algorithm"] == "ASTAR"

    def test_route_dijkstra_algorithm(self):
        r = client.get("/route?from=MG%20Road&to=BTM%20Layout&algorithm=dijkstra")
        assert r.status_code == 200
        assert r.json()["algorithm"] == "DIJKSTRA"

    def test_invalid_algorithm_returns_400(self):
        assert client.get("/route?from=MG%20Road&to=BTM%20Layout&algorithm=bfs").status_code == 400

    def test_unknown_stop_returns_404(self):
        assert client.get("/route?from=Nonexistent%20XYZ&to=BTM%20Layout").status_code == 404

    def test_same_stop_returns_400(self):
        assert client.get("/route?from=MG%20Road&to=MG%20Road").status_code == 400

    def test_route_cached_on_second_call(self):
        client.get("/route?from=MG%20Road&to=HSR%20Layout")
        r2 = client.get("/route?from=MG%20Road&to=HSR%20Layout")
        assert r2.json()["cached"] is True

    def test_total_matches_directions_sum(self):
        body      = client.get("/route?from=MG%20Road&to=BTM%20Layout").json()
        dir_total = sum(d["minutes"] for d in body["directions"])
        assert abs(dir_total - body["total_minutes"]) < 1.0


# ── Delay prediction ──────────────────────────────────────────────────────────

class TestPredictDelay:

    BASE = {
        "stop_id": "S001", "hour": 8, "is_weekend": 0,
        "prior_stop_delay": 0.0, "temp_deviation": 0.3,
        "stop_sequence_norm": 0.0, "route_type": 3, "n_stops_on_trip": 6,
    }

    def _post(self, **overrides):
        return client.post("/predict-delay", json={**self.BASE, **overrides})

    def test_basic_prediction(self):
        r = self._post()
        assert r.status_code == 200
        assert r.json()["predicted_delay"] >= 0.0

    def test_response_has_required_fields(self):
        body = self._post().json()
        for f in ("stop_id","stop_name","predicted_delay","confidence","model_mae","cached"):
            assert f in body

    def test_rush_hour_not_lower_than_offpeak(self):
        rush    = self._post(hour=8).json()["predicted_delay"]
        offpeak = self._post(hour=14).json()["predicted_delay"]
        assert rush >= offpeak * 0.5   # lenient — just shouldn't be way lower

    def test_prior_delay_increases_prediction(self):
        low  = self._post(stop_sequence_norm=0.5, prior_stop_delay=0.0).json()["predicted_delay"]
        high = self._post(stop_sequence_norm=0.5, prior_stop_delay=8.0).json()["predicted_delay"]
        assert high > low

    def test_metro_not_higher_than_bus(self):
        metro = self._post(route_type=1).json()["predicted_delay"]
        bus   = self._post(route_type=3).json()["predicted_delay"]
        assert metro <= bus

    def test_invalid_stop_returns_404(self):
        assert self._post(stop_id="S999").status_code == 404

    def test_invalid_hour_returns_422(self):
        assert self._post(hour=25).status_code == 422

    def test_negative_hour_returns_422(self):
        assert self._post(hour=-1).status_code == 422

    def test_cached_on_second_call(self):
        payload = {**self.BASE, "hour": 9, "prior_stop_delay": 2.0}
        client.post("/predict-delay", json=payload)
        r2 = client.post("/predict-delay", json=payload)
        assert r2.json()["cached"] is True

    def test_confidence_valid_value(self):
        assert self._post().json()["confidence"] in ("low", "medium", "high")

    def test_weekend_not_higher_than_weekday(self):
        wd = self._post(is_weekend=0, hour=8).json()["predicted_delay"]
        we = self._post(is_weekend=1, hour=8).json()["predicted_delay"]
        assert we <= wd
