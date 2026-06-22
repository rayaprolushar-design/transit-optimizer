"""
api/server.py — Transit Optimizer FastAPI Server
Week 16 | Phase 2

Endpoints:
  GET  /                     Health check
  GET  /stops                List all stops
  GET  /route?from=X&to=Y   Find fastest route
  POST /predict-delay        Predict delay minutes
  GET  /model-info           Model metadata
  GET  /stats                Graph + server stats

Run:
  uvicorn api.server:app --reload --port 8000
  http://localhost:8000/docs   ← Swagger UI
"""

from __future__ import annotations

import json
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.router import find_route, build_directions
from scripts.search import fuzzy_find_stop
from scripts.week9_performance import LRUCache

GRAPH_PATH = Path("data/graph_with_transfers.json")
MODEL_PATH = Path("data/delay_model.joblib")
META_PATH  = Path("data/model_meta.json")
LOG_PATH   = Path("logs/api.log")
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("transit-api")


# ── App state (loaded once at startup) ───────────────────────────────────────

class AppState:
    graph:       dict   = {}
    stops:       dict   = {}
    model:       object = None
    model_meta:  dict   = {}
    route_cache: LRUCache = LRUCache(capacity=512)
    pred_cache:  LRUCache = LRUCache(capacity=256)
    start_time:  float  = 0.0
    requests:    int    = 0

state = AppState()


def _load_resources():
    """Load graph + model into state. Called at startup and in tests."""
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    state.graph = data["graph"]
    state.stops = data["stops"]
    state.model      = joblib.load(MODEL_PATH)
    state.model_meta = json.loads(META_PATH.read_text())
    state.start_time = time.perf_counter()
    log.info(f"Resources loaded: {len(state.stops)} stops, "
             f"model={state.model_meta['model_name']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_resources()
    yield
    log.info(f"Shutdown after {state.requests} requests")


# ── Pydantic models ───────────────────────────────────────────────────────────

class DelayRequest(BaseModel):
    stop_id:            str   = Field(...,  description="Stop ID e.g. S001")
    hour:               int   = Field(...,  ge=0, le=23)
    is_weekend:         int   = Field(0,    ge=0, le=1)
    prior_stop_delay:   float = Field(0.0,  ge=0.0)
    temp_deviation:     float = Field(0.0)
    stop_sequence_norm: float = Field(0.0,  ge=0.0, le=1.0)
    route_type:         int   = Field(3,    description="1=Metro 3=Bus")
    n_stops_on_trip:    int   = Field(6,    ge=1)


class DelayResponse(BaseModel):
    stop_id:          str
    stop_name:        str
    predicted_delay:  float
    confidence:       str
    model_mae:        float
    cached:           bool


class StopInfo(BaseModel):
    stop_id: str
    name:    str
    lat:     float
    lon:     float


class HealthResponse(BaseModel):
    status:          str
    version:         str
    uptime_s:        float
    stops:           int
    edges:           int
    model:           str
    requests_served: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _feature_vector(req: DelayRequest) -> np.ndarray:
    dow          = 5 if req.is_weekend else datetime.now().weekday()
    is_rush      = int((7 <= req.hour <= 10) or (17 <= req.hour <= 20))
    route_freq   = 3.0 if req.route_type == 1 else 2.0
    return np.array([[
        req.stop_sequence_norm, req.hour, is_rush, req.is_weekend,
        dow, req.route_type, req.n_stops_on_trip,
        req.prior_stop_delay, req.temp_deviation, route_freq,
    ]])


def _confidence(delay: float, mae: float) -> str:
    if delay < mae:       return "high"
    elif delay < mae * 3: return "medium"
    else:                 return "low"


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Transit Optimizer API",
    description="AI-powered transit routing and delay prediction.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── WebSockets Telemetry ─────────────────────────────────────────────────────

active_connections: list[WebSocket] = []

async def broadcast_event(event: dict):
    for connection in list(active_connections):
        try:
            await connection.send_json(event)
        except Exception:
            if connection in active_connections:
                active_connections.remove(connection)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

async def _broadcast_prediction(req: DelayRequest, stop_name: str, pred_delay: float, cached: bool):
    event = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "stop_id": req.stop_id,
        "stop_name": stop_name,
        "predicted_delay": pred_delay,
        "confidence": _confidence(pred_delay, state.model_meta["test_mae"]),
        "route_type": "Metro" if req.route_type == 1 else "Bus",
        "hour": req.hour,
        "is_weekend": bool(req.is_weekend),
        "cached": cached,
    }
    await broadcast_event(event)


@app.middleware("http")
async def count_requests(request: Request, call_next):
    state.requests += 1
    t0 = time.perf_counter()
    response = await call_next(request)
    log.info(f"{request.method} {request.url.path} "
             f"→ {response.status_code} [{(time.perf_counter()-t0)*1000:.1f}ms]")
    return response


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", response_model=HealthResponse, tags=["health"])
async def health():
    return HealthResponse(
        status="ok", version="2.0.0",
        uptime_s=round(time.perf_counter() - state.start_time, 1),
        stops=len(state.stops),
        edges=sum(len(v) for v in state.graph.values()),
        model=state.model_meta.get("model_name", ""),
        requests_served=state.requests,
    )


@app.get("/stops", response_model=list[StopInfo], tags=["stops"])
async def list_stops(
    filter: Optional[str] = Query(None),
    limit:  int           = Query(50, ge=1, le=200),
):
    out = []
    for sid, s in sorted(state.stops.items(), key=lambda x: x[1]["name"]):
        if filter and filter.lower() not in s["name"].lower():
            continue
        out.append(StopInfo(stop_id=sid, name=s["name"],
                            lat=float(s["lat"]), lon=float(s["lon"])))
        if len(out) >= limit:
            break
    return out


@app.get("/route", tags=["routing"])
async def get_route(
    from_stop: str  = Query(..., alias="from", description="Origin stop name"),
    to_stop:   str  = Query(..., alias="to",   description="Destination stop name"),
    algorithm: str  = Query("astar"),
    transfers: bool = Query(True),
):
    if algorithm not in ("astar", "dijkstra"):
        raise HTTPException(400, "algorithm must be 'astar' or 'dijkstra'")

    sid, sname, _ = fuzzy_find_stop(from_stop, state.stops)
    eid, ename, _ = fuzzy_find_stop(to_stop,   state.stops)

    if not sid:
        raise HTTPException(404, f"Stop not found: '{from_stop}'")
    if not eid:
        raise HTTPException(404, f"Stop not found: '{to_stop}'")
    if sid == eid:
        raise HTTPException(400, "Start and destination are the same stop")

    key    = f"{sid}:{eid}:{algorithm}:{transfers}"
    cached = state.route_cache.get(key)
    if cached:
        return {**cached, "cached": True}

    result = find_route(state.graph, state.stops, sid, eid, algorithm)
    if not result["found"]:
        raise HTTPException(404, f"No route found from '{sname}' to '{ename}'")

    directions  = build_directions(result, state.stops)
    n_transfers = sum(1 for d in directions if d["type"] == "walk")

    response = {
        "found":         True,
        "from_stop":     sname,
        "to_stop":       ename,
        "total_minutes": result["total_minutes"],
        "segments":      len(directions),
        "transfers":     n_transfers,
        "algorithm":     algorithm.upper(),
        "nodes_visited": result["nodes_visited"],
        "elapsed_ms":    round(result["elapsed_ms"], 4),
        "cached":        False,
        "path":          result.get("path", []),
        "directions":    directions,
    }
    state.route_cache.put(key, response)
    return response


@app.post("/predict-delay", response_model=DelayResponse, tags=["ml"])
async def predict_delay(req: DelayRequest):
    stop = state.stops.get(req.stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{req.stop_id}' not found")

    key    = (f"{req.stop_id}:{req.hour}:{req.is_weekend}:"
              f"{req.prior_stop_delay:.1f}:{req.stop_sequence_norm:.2f}")
    cached = state.pred_cache.get(key)
    if cached is not None:
        await _broadcast_prediction(req, stop["name"], cached, True)
        return DelayResponse(
            stop_id=req.stop_id, stop_name=stop["name"],
            predicted_delay=cached,
            confidence=_confidence(cached, state.model_meta["test_mae"]),
            model_mae=state.model_meta["test_mae"], cached=True,
        )

    pred = float(state.model.predict(_feature_vector(req))[0])
    pred = round(max(0.0, pred), 2)
    state.pred_cache.put(key, pred)

    await _broadcast_prediction(req, stop["name"], pred, False)
    return DelayResponse(
        stop_id=req.stop_id, stop_name=stop["name"],
        predicted_delay=pred,
        confidence=_confidence(pred, state.model_meta["test_mae"]),
        model_mae=state.model_meta["test_mae"], cached=False,
    )


@app.get("/model-info", tags=["ml"])
async def model_info():
    return {
        "model_name":   state.model_meta.get("model_name"),
        "test_mae":     state.model_meta.get("test_mae"),
        "test_rmse":    state.model_meta.get("test_rmse"),
        "test_r2":      state.model_meta.get("test_r2"),
        "cv_mae_mean":  state.model_meta.get("cv_mae_mean"),
        "n_train":      state.model_meta.get("n_train"),
        "feature_cols": state.model_meta.get("feature_cols"),
    }


@app.get("/stats", tags=["health"])
async def stats():
    return {
        "graph": {
            "stops":        len(state.stops),
            "total_edges":  sum(len(v) for v in state.graph.values()),
            "transit_edges": sum(1 for nbrs in state.graph.values()
                                 for e in nbrs.values() if e.get("route") != "WALK"),
            "walk_edges":   sum(1 for nbrs in state.graph.values()
                                for e in nbrs.values() if e.get("route") == "WALK"),
        },
        "cache": {
            "route_cache":      state.route_cache.stats(),
            "prediction_cache": state.pred_cache.stats(),
        },
        "server": {
            "uptime_s":        round(time.perf_counter() - state.start_time, 1),
            "requests_served": state.requests,
        },
    }
