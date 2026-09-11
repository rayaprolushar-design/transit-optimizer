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
import asyncio
import random
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict

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
    broadcaster_task = asyncio.create_task(_broadcast_delay_events())
    gps_task = None
    if GPS_AVAILABLE and state.stops and state.graph:
        gps_task = asyncio.create_task(
            run_live_feed(
                state.stops,
                state.graph,
                use_real_api=USE_REAL_GPS,
                poll_interval=10,
            )
        )
        log.info(f"GPS tracker started (real={'yes' if USE_REAL_GPS else 'no, simulation'})")
    yield
    if broadcaster_task:
        broadcaster_task.cancel()
    if gps_task:
        gps_task.cancel()
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

DIST_DIR = Path(__file__).parent.parent / "transit-dashboard" / "dist"
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")


@app.middleware("http")
async def count_requests(request: Request, call_next):
    state.requests += 1
    t0 = time.perf_counter()
    response = await call_next(request)
    log.info(f"{request.method} {request.url.path} "
             f"→ {response.status_code} [{(time.perf_counter()-t0)*1000:.1f}ms]")
    return response


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def health(request: Request):
    index_file = DIST_DIR / "index.html"
    if index_file.exists() and "text/html" in request.headers.get("accept", ""):
        return FileResponse(index_file)
    return HealthResponse(
        status="ok", version="2.0.0",
        uptime_s=round(time.perf_counter() - state.start_time, 1),
        stops=len(state.stops),
        edges=sum(len(v) for v in state.graph.values()),
        model=state.model_meta.get("model_name", ""),
        requests_served=state.requests,
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_endpoint():
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
        return DelayResponse(
            stop_id=req.stop_id, stop_name=stop["name"],
            predicted_delay=cached,
            confidence=_confidence(cached, state.model_meta["test_mae"]),
            model_mae=state.model_meta["test_mae"], cached=True,
        )

    pred = float(state.model.predict(_feature_vector(req))[0])
    pred = round(max(0.0, pred), 2)
    state.pred_cache.put(key, pred)

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


# ════════════════════════════════════════════════════════════════════════════════
# WEBSOCKET — Week 22 live feed
# Broadcasts simulated delay events every 5 seconds to all connected clients.
# ════════════════════════════════════════════════════════════════════════════════

# Track all active WebSocket connections
_ws_clients: list[WebSocket] = []


async def _broadcast_delay_events():
    """Background task: push a simulated delay event every 5s."""
    routes    = ["Route 5", "Route 12", "Route 27", "Route 33", "M1 Metro", "Route 41"]
    stop_list = list(state.stops.values()) if state.stops else [{"name": "MG Road"}]

    while True:
        await asyncio.sleep(5)
        if not _ws_clients:
            continue

        stop     = random.choice(stop_list)
        route    = random.choice(routes)
        delay    = round(random.uniform(-1, 8), 1)
        severity = "high" if delay > 4 else "medium" if delay > 1 else "low"

        event = {
            "route":          route,
            "stop":           stop.get("name", "Unknown"),
            "delay_minutes":  max(0, delay),
            "severity":       severity,
            "time":           datetime.now().strftime("%H:%M"),
        }

        dead = []
        for ws in _ws_clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


@app.websocket("/ws/live-feed")
async def ws_live_feed(websocket: WebSocket):
    """
    WebSocket endpoint — client connects and receives delay events every 5s.
    Stays open until client disconnects or server shuts down.
    """
    await websocket.accept()
    _ws_clients.append(websocket)
    log.info(f"WebSocket connected — {len(_ws_clients)} total clients")
    try:
        while True:
            # Keep alive — wait for client ping or disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
        log.info(f"WebSocket disconnected — {len(_ws_clients)} remaining")


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 1 — Live GPS integration
# ════════════════════════════════════════════════════════════════════════════════

try:
    from scripts.gps_tracker import live_store, run_live_feed
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    live_store = None

USE_REAL_GPS = os.getenv("USE_REAL_GPS", "0") == "1"


@app.get("/live-delays", tags=["live"])
async def get_live_delays():
    """
    Current live delay in minutes for every stop that has been observed.
    """
    if not GPS_AVAILABLE or live_store is None:
        return {"delays": {}, "source": "unavailable", "count": 0}

    delays = live_store.all_delays()
    return {
        "delays":  delays,
        "source":  "real_gps" if USE_REAL_GPS else "simulation",
        "count":   len(delays),
        "updated": datetime.now().isoformat(),
    }


@app.get("/live-delays/{stop_id}", tags=["live"])
async def get_stop_live_delay(stop_id: str):
    """
    Live delay for a specific stop.
    """
    stop = state.stops.get(stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{stop_id}' not found")

    delay = live_store.get_delay(stop_id) if (GPS_AVAILABLE and live_store) else None
    trend = live_store.get_trend(stop_id) if (GPS_AVAILABLE and live_store) else None

    return {
        "stop_id":        stop_id,
        "stop_name":      stop["name"],
        "live_delay_min": delay,
        "trend_delay_min": trend,
        "has_live_data":  delay is not None,
        "source":         "real_gps" if USE_REAL_GPS else "simulation",
    }


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 2 — Display Board Endpoints
# ════════════════════════════════════════════════════════════════════════════════

class ArrivalInfo(BaseModel):
    route:           str
    destination:     str
    scheduled_time:  str
    predicted_time:  str
    delay_minutes:   float
    status:          str   # "On time" | "Delayed Xm" | "Early Xm"
    confidence:      str


@app.get("/board/{stop_id}", tags=["display-board"])
async def board_next_arrivals(
    stop_id: str,
    n: int = Query(4, description="Number of next arrivals to show", ge=1, le=10),
):
    stop = state.stops.get(stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{stop_id}' not found")

    now_min   = datetime.now().hour * 60 + datetime.now().minute
    hour      = datetime.now().hour
    is_rush   = int((7 <= hour <= 10) or (17 <= hour <= 20))
    is_wknd   = int(datetime.now().weekday() >= 5)

    live_delay = 0.0
    if GPS_AVAILABLE and live_store:
        d = live_store.get_delay(stop_id)
        if d is not None:
            live_delay = d

    arrivals = []
    for from_id, neighbours in state.graph.items():
        for to_id, edge in neighbours.items():
            if from_id == stop_id and edge.get("route") != "WALK":
                route      = edge.get("route", "?")
                to_stop    = state.stops.get(to_id, {})
                dest_name  = to_stop.get("name", to_id)

                base_offset = (hash(route + stop_id) % 12)
                for dep_offset in range(0, 60, 12):
                    sched_min = now_min + base_offset + dep_offset
                    if sched_min - now_min < 1:
                        continue

                    if state.model:
                        X = np.array([[
                            0.5, hour, is_rush, is_wknd,
                            datetime.now().weekday(),
                            3, 6, live_delay, 0.3, 2.0,
                        ]])
                        pred_delay = max(0.0, float(state.model.predict(X)[0]))
                    else:
                        pred_delay = live_delay

                    total_delay  = min(60.0, round((live_delay + pred_delay) / 2, 1))
                    predicted_min = sched_min + total_delay

                    sched_h, sched_m   = divmod(int(sched_min) % 1440, 60)
                    pred_h,  pred_m    = divmod(int(predicted_min) % 1440, 60)

                    if total_delay > 1.5:
                        status = f"Delayed {total_delay:.0f}m"
                    elif total_delay < -0.5:
                        status = f"Early {abs(total_delay):.0f}m"
                    else:
                        status = "On time"

                    mae = state.model_meta.get("test_mae", 0.76)
                    arrivals.append(ArrivalInfo(
                        route            = route,
                        destination      = dest_name,
                        scheduled_time   = f"{sched_h%24:02d}:{sched_m:02d}",
                        predicted_time   = f"{pred_h%24:02d}:{pred_m:02d}",
                        delay_minutes    = total_delay,
                        status           = status,
                        confidence       = "high" if total_delay < mae else "medium" if total_delay < mae*3 else "low",
                    ))
                    break

    arrivals.sort(key=lambda a: a.predicted_time)
    arrivals = arrivals[:n]

    return {
        "stop_id":    stop_id,
        "stop_name":  stop["name"],
        "lat":        stop["lat"],
        "lon":        stop["lon"],
        "timestamp":  datetime.now().isoformat(),
        "live_delay": live_delay,
        "has_gps":    GPS_AVAILABLE and live_store is not None,
        "arrivals":   [a.model_dump() for a in arrivals],
    }


_board_clients: dict[str, list[WebSocket]] = {}


@app.websocket("/ws/board/{stop_id}")
async def ws_board(websocket: WebSocket, stop_id: str):
    if stop_id not in state.stops:
        await websocket.close(code=1008, reason="Stop not found")
        return

    await websocket.accept()
    if stop_id not in _board_clients:
        _board_clients[stop_id] = []
    _board_clients[stop_id].append(websocket)
    log.info(f"Board WS connected: stop={stop_id}, total={len(_board_clients[stop_id])}")

    try:
        last_delay = None
        while True:
            await asyncio.sleep(5)
            current_delay = (
                live_store.get_delay(stop_id)
                if (GPS_AVAILABLE and live_store) else None
            )
            if current_delay is not None:
                if last_delay is None or abs(current_delay - last_delay) > 0.5:
                    await websocket.send_json({
                        "stop_id":     stop_id,
                        "stop_name":   state.stops[stop_id]["name"],
                        "delay_min":   current_delay,
                        "timestamp":   datetime.now().isoformat(),
                        "type":        "delay_update",
                    })
                    last_delay = current_delay
    except WebSocketDisconnect:
        if websocket in _board_clients.get(stop_id, []):
            _board_clients[stop_id].remove(websocket)


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 3 — Delivery Routing Endpoints
# ════════════════════════════════════════════════════════════════════════════════

try:
    from delivery.road_graph import (
        build_delivery_graph, astar_delivery,
        nearest_neighbour_tsp, DELIVERY_LOCATIONS,
    )
    DELIVERY_AVAILABLE = True
except ImportError:
    DELIVERY_AVAILABLE = False


class DeliveryRouteRequest(BaseModel):
    from_id:  str  = Field(..., description="Origin location ID e.g. R001")
    to_id:    str  = Field(..., description="Destination location ID e.g. C001")
    hour:     int  = Field(12, ge=0, le=23, description="Hour for congestion model")


class MultiStopRequest(BaseModel):
    start_id: str        = Field(..., description="Starting location")
    stop_ids: list[str]  = Field(..., description="Drop-off locations in any order")
    hour:     int        = Field(12, ge=0, le=23)


@app.get("/delivery/locations", tags=["delivery"])
async def list_delivery_locations(type: Optional[str] = Query(None)):
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")
    locs = DELIVERY_LOCATIONS
    if type:
        locs = {k: v for k, v in locs.items() if v.get("type") == type}
    return locs


@app.get("/delivery/route", tags=["delivery"])
async def delivery_route(
    from_id: str = Query(..., description="Origin location ID"),
    to_id:   str = Query(..., description="Destination location ID"),
    hour:    int = Query(12, ge=0, le=23),
):
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")
    if from_id not in DELIVERY_LOCATIONS:
        raise HTTPException(404, f"Location '{from_id}' not found")
    if to_id not in DELIVERY_LOCATIONS:
        raise HTTPException(404, f"Location '{to_id}' not found")

    graph  = build_delivery_graph(hour=hour)
    result = astar_delivery(graph, from_id, to_id)

    if not result["found"]:
        raise HTTPException(404, "No route found between these locations")

    path_named = [
        {"id": p, "name": DELIVERY_LOCATIONS.get(p, {}).get("name", p)}
        for p in result["path"]
    ]

    return {
        "found":         True,
        "from":          DELIVERY_LOCATIONS[from_id]["name"],
        "to":            DELIVERY_LOCATIONS[to_id]["name"],
        "total_minutes": result["total_minutes"],
        "total_km":      result["total_km"],
        "hour":          hour,
        "congestion":    "high" if hour in range(7,11) or hour in range(17,21) else "low",
        "nodes_visited": result["nodes_visited"],
        "elapsed_ms":    round(result["elapsed_ms"], 4),
        "path":          path_named,
    }


@app.post("/delivery/multi-stop", tags=["delivery"])
async def multi_stop_delivery(req: MultiStopRequest):
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")

    for loc_id in [req.start_id] + req.stop_ids:
        if loc_id not in DELIVERY_LOCATIONS:
            raise HTTPException(404, f"Location '{loc_id}' not found")

    graph  = build_delivery_graph(hour=req.hour)
    result = nearest_neighbour_tsp(graph, req.start_id, req.stop_ids)

    return {
        "optimised_order": [
            {"id": s, "name": DELIVERY_LOCATIONS.get(s, {}).get("name", s)}
            for s in result["route"]
        ],
        "total_minutes":   result["total_minutes"],
        "total_km":        result["total_km"],
        "stops":           result["stops_count"],
        "hour":            req.hour,
        "algorithm":       "nearest-neighbour TSP (greedy, ~25% suboptimal)",
    }


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 4 — Multi-Modal Routing Endpoints
# ════════════════════════════════════════════════════════════════════════════════

try:
    from multimodal.planner import (
        build_multimodal_graph, astar_multimodal,
        build_directions as build_mm_directions,
        LOCATIONS,
    )
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False


class MultiModalRequest(BaseModel):
    from_id:       str        = Field(..., description="Origin location ID")
    to_id:         str        = Field(..., description="Destination location ID")
    hour:          int        = Field(12, ge=0, le=23)
    allowed_modes: list[str]  = Field(
        default=["drive", "metro", "bus", "walk"],
        description="Modes to allow",
    )


@app.get("/multimodal/locations", tags=["multimodal"])
async def multimodal_locations():
    if not MULTIMODAL_AVAILABLE:
        raise HTTPException(503, "Multimodal module not available")
    return LOCATIONS


@app.get("/multimodal/route", tags=["multimodal"])
async def multimodal_route_get(
    from_id: str = Query(..., description="Origin node ID"),
    to_id:   str = Query(..., description="Destination node ID"),
    hour:    int = Query(12, ge=0, le=23),
):
    if not MULTIMODAL_AVAILABLE:
        raise HTTPException(503, "Multimodal module not available")
    if from_id not in LOCATIONS:
        raise HTTPException(404, f"Location '{from_id}' not found")
    if to_id not in LOCATIONS:
        raise HTTPException(404, f"Location '{to_id}' not found")

    is_rush = (7 <= hour <= 10) or (17 <= hour <= 20)
    cong    = 2.2 if is_rush else 1.0
    graph   = build_multimodal_graph(congestion_factor=cong)
    result  = astar_multimodal(graph, from_id, to_id)

    if not result["found"]:
        raise HTTPException(404, "No multi-modal route found")

    directions = build_mm_directions(result)
    modes_used = list(dict.fromkeys(d["mode"] for d in directions))

    return {
        "found":           True,
        "from":            LOCATIONS[from_id]["name"],
        "to":              LOCATIONS[to_id]["name"],
        "total_minutes":   result["total_minutes"],
        "modes_used":      modes_used,
        "transfers":       sum(1 for d in directions if d.get("penalty", 0) > 0),
        "congestion":      "high" if is_rush else "normal",
        "hour":            hour,
        "nodes_visited":   result["nodes_visited"],
        "elapsed_ms":      round(result["elapsed_ms"], 4),
        "directions":      directions,
    }


@app.post("/multimodal/route", tags=["multimodal"])
async def multimodal_route_post(req: MultiModalRequest):
    if not MULTIMODAL_AVAILABLE:
        raise HTTPException(503, "Multimodal module not available")
    if req.from_id not in LOCATIONS:
        raise HTTPException(404, f"Location '{req.from_id}' not found")
    if req.to_id not in LOCATIONS:
        raise HTTPException(404, f"Location '{req.to_id}' not found")

    is_rush = (7 <= req.hour <= 10) or (17 <= req.hour <= 20)
    cong    = 2.2 if is_rush else 1.0
    graph   = build_multimodal_graph(congestion_factor=cong)
    result  = astar_multimodal(graph, req.from_id, req.to_id,
                                allowed_modes=set(req.allowed_modes))

    if not result["found"]:
        raise HTTPException(404, "No multi-modal route found")

    directions = build_mm_directions(result)
    modes_used = list(dict.fromkeys(d["mode"] for d in directions))

    return {
        "found":           True,
        "from":            LOCATIONS[req.from_id]["name"],
        "to":              LOCATIONS[req.to_id]["name"],
        "total_minutes":   result["total_minutes"],
        "modes_used":      modes_used,
        "transfers":       sum(1 for d in directions if d.get("penalty", 0) > 0),
        "congestion":      "high" if is_rush else "normal",
        "hour":            req.hour,
        "nodes_visited":   result["nodes_visited"],
        "elapsed_ms":      round(result["elapsed_ms"], 4),
        "directions":      directions,
    }


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 5 — Driver Assignment Endpoints
# ════════════════════════════════════════════════════════════════════════════════

try:
    from matching.assignment import (
        get_server, VehicleType as VT,
        AssignmentServer,
    )
    MATCHING_AVAILABLE = True
    _assignment_server: Optional[AssignmentServer] = None
except ImportError:
    MATCHING_AVAILABLE = False


def _get_assignment_server():
    global _assignment_server
    if _assignment_server is None and MATCHING_AVAILABLE:
        _assignment_server = get_server()
    return _assignment_server


class RideRequestBody(BaseModel):
    rider_id:     str   = Field(..., example="RIDER_001")
    pickup_lat:   float = Field(..., example=12.9755)
    pickup_lon:   float = Field(..., example=77.6069)
    dropoff_lat:  float = Field(..., example=12.9116)
    dropoff_lon:  float = Field(..., example=77.6389)
    vehicle_type: str   = Field("bike", description="bike|auto|mini|sedan")
    use_hungarian: bool = Field(True,  description="Use optimal matching")


@app.get("/drivers", tags=["assignment"])
async def list_drivers(status: Optional[str] = Query(None)):
    if not MATCHING_AVAILABLE:
        raise HTTPException(503, "Matching module not available")
    srv = _get_assignment_server()
    drivers = srv.pool.available() if status == "available" else list(srv.pool._drivers.values())
    return [
        {
            "driver_id":    d.driver_id,
            "name":         d.name,
            "lat":          d.lat,
            "lon":          d.lon,
            "vehicle_type": d.vehicle_type.value,
            "rating":       d.rating,
            "status":       d.status.value,
            "trips_today":  d.trips_today,
            "earnings":     d.earnings,
        }
        for d in drivers
    ]


@app.post("/request-ride", tags=["assignment"])
async def request_ride(body: RideRequestBody):
    if not MATCHING_AVAILABLE:
        raise HTTPException(503, "Matching module not available")

    try:
        vt = VT(body.vehicle_type.lower())
    except ValueError:
        raise HTTPException(400, f"Invalid vehicle_type: {body.vehicle_type}")

    srv    = _get_assignment_server()
    result = srv.request_ride(
        rider_id     = body.rider_id,
        pickup_lat   = body.pickup_lat,
        pickup_lon   = body.pickup_lon,
        dropoff_lat  = body.dropoff_lat,
        dropoff_lon  = body.dropoff_lon,
        vehicle_type = vt,
        use_hungarian = body.use_hungarian,
    )

    if not result:
        raise HTTPException(
            404,
            f"No {body.vehicle_type} drivers available in your area. "
            "Try a different vehicle type or retry in a few minutes."
        )

    return {
        "matched":        True,
        "rider_id":       result.rider_id,
        "driver_id":      result.driver_id,
        "driver_name":    result.driver_name,
        "vehicle_type":   result.vehicle_type,
        "eta_minutes":    result.eta_minutes,
        "pickup_km":      result.pickup_km,
        "fare_estimate":  result.fare,
        "surge_mult":     result.surge,
        "algorithm":      result.algorithm,
        "match_time_ms":  result.match_ms,
    }


@app.get("/surge", tags=["assignment"])
async def surge_pricing():
    if not MATCHING_AVAILABLE:
        raise HTTPException(503, "Matching module not available")
    srv = _get_assignment_server()
    return {
        "zones": srv.surge_eng.zone_stats(),
        "note":  "Surge = demand/supply ratio per zone. Cap: 3.0×",
    }


@app.get("/driver-stats", tags=["assignment"])
async def driver_stats():
    if not MATCHING_AVAILABLE:
        raise HTTPException(503, "Matching module not available")
    return _get_assignment_server().pool.stats()


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 6 — Demand Forecasting Endpoints
# ════════════════════════════════════════════════════════════════════════════════

try:
    from forecasting.demand import (
        DemandSimulator, ProphetForecaster, ARIMAForecaster,
        DynamicPricingEngine, DarkStoreAnalyzer, InventoryOptimizer,
        ZONES, PROPHET_OK,
    )
    FORECASTING_AVAILABLE = True
except ImportError:
    FORECASTING_AVAILABLE = False

_forecast_cache: dict = {}
_forecast_engine: dict = {}


def _get_forecast_data():
    if "ready" not in _forecast_cache:
        import warnings; warnings.filterwarnings("ignore")
        sim       = DemandSimulator(days=90)
        zone_data = sim.generate_all()
        if PROPHET_OK:
            fc = ProphetForecaster()
        else:
            fc = ARIMAForecaster()
        for zid, df in zone_data.items():
            fc.train(zid, df)
        _forecast_cache["zone_data"]  = zone_data
        _forecast_cache["forecaster"] = fc
        _forecast_cache["ready"]      = True
    return _forecast_cache


@app.get("/forecast/zones", tags=["forecasting"])
async def forecast_zones():
    if not FORECASTING_AVAILABLE:
        raise HTTPException(503, "Forecasting module not available. pip install prophet")

    data      = _get_forecast_data()
    fc        = data["forecaster"]
    zone_data = data["zone_data"]
    pricer    = DynamicPricingEngine()
    decisions = []

    for zid in ZONES:
        if PROPHET_OK and hasattr(fc, "predict") and fc.is_trained(zid):
            result = fc.predict(zid, periods=1)
            pred   = float(result["yhat"].iloc[-1]) if result is not None else 0.0
        elif hasattr(fc, "predict"):
            result = fc.predict(zid, periods=1)
            pred   = float(result[0]) if result is not None else 0.0
        else:
            pred   = zone_data[zid]["y"].tail(48).mean()

        d = pricer.decide(zid, pred)
        decisions.append({
            "zone_id":          d.zone_id,
            "zone_name":        d.zone_name,
            "predicted_demand": d.predicted_demand,
            "capacity":         d.capacity,
            "utilisation":      d.utilisation,
            "delivery_fee":     d.final_fee,
            "surge_mult":       d.multiplier,
            "pre_stock_units":  d.pre_stock_units,
            "recommendation":   d.recommendation,
        })

    return {
        "forecast_horizon": "30 minutes",
        "model":            "Prophet" if PROPHET_OK else "ARIMA",
        "zones":            sorted(decisions, key=lambda x: -x["utilisation"]),
        "timestamp":        datetime.now().isoformat(),
    }


@app.get("/forecast/{zone_id}", tags=["forecasting"])
async def forecast_zone(zone_id: str, periods: int = Query(4, ge=1, le=48)):
    if not FORECASTING_AVAILABLE:
        raise HTTPException(503, "Forecasting module not available")
    if zone_id not in ZONES:
        raise HTTPException(404, f"Zone '{zone_id}' not found. Use /forecast/zones to list zones.")

    data   = _get_forecast_data()
    fc     = data["forecaster"]
    pricer = DynamicPricingEngine()

    if PROPHET_OK and hasattr(fc, "predict") and fc.is_trained(zone_id):
        result = fc.predict(zone_id, periods=periods)
        if result is not None:
            slots = []
            for _, row in result.iterrows():
                d = pricer.decide(zone_id, max(0, row["yhat"]))
                slots.append({
                    "time":           row["ds"].isoformat(),
                    "predicted":      round(max(0, row["yhat"]), 1),
                    "lower_95":       round(max(0, row.get("yhat_lower", 0)), 1),
                    "upper_95":       round(max(0, row.get("yhat_upper", 0)), 1),
                    "delivery_fee":   d.final_fee,
                    "utilisation":    d.utilisation,
                    "pre_stock":      d.pre_stock_units,
                })
            return {
                "zone_id":   zone_id,
                "zone_name": ZONES[zone_id]["name"],
                "model":     "Prophet",
                "periods":   periods,
                "forecasts": slots,
            }

    raise HTTPException(503, "Model not yet trained for this zone")


@app.get("/pricing/decisions", tags=["forecasting"])
async def pricing_decisions():
    if not FORECASTING_AVAILABLE:
        raise HTTPException(503, "Forecasting module not available")

    pricer    = DynamicPricingEngine()
    decisions = []

    if "ready" in _forecast_cache:
        zone_data = _forecast_cache["zone_data"]
        for zid, df in zone_data.items():
            pred = df["y"].tail(2).mean()
            d    = pricer.decide(zid, pred)
            decisions.append({"zone_id": d.zone_id, "zone_name": d.zone_name,
                               "fee": d.final_fee, "surge": d.multiplier,
                               "util": d.utilisation})
    else:
        for zid, zone in ZONES.items():
            decisions.append({
                "zone_id": zid, "zone_name": zone["name"],
                "fee": 25.0, "surge": 1.0, "util": 0.5,
            })

    return {"decisions": decisions, "timestamp": datetime.now().isoformat()}


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 8 — Model Monitoring Endpoints
# ════════════════════════════════════════════════════════════════════════════════

try:
    from monitoring.model_monitor import (
        ModelHealthMonitor, build_monitor_from_meta,
        ConfidenceEstimator, ModelHealthDashboard,
    )
    MONITORING_AVAILABLE = True
    _monitor: Optional[ModelHealthMonitor] = None
except ImportError:
    MONITORING_AVAILABLE = False


def _get_monitor() -> Optional[ModelHealthMonitor]:
    global _monitor
    if _monitor is None and MONITORING_AVAILABLE:
        meta = state.model_meta if state.model_meta else {}
        _monitor = ModelHealthMonitor(
            train_mae  = meta.get("test_mae",  0.762),
            train_r2   = meta.get("test_r2",   0.832),
            model_name = meta.get("model_name","GradientBoosting"),
        )
    return _monitor


@app.get("/model-health", tags=["ml"])
async def model_health():
    if not MONITORING_AVAILABLE:
        raise HTTPException(503, "Monitoring module not available")
    monitor = _get_monitor()
    if not monitor:
        raise HTTPException(503, "Monitor not initialised")
    return monitor.health()


@app.post("/predict-delay-v2", tags=["ml"])
async def predict_delay_v2(req: DelayRequest):
    stop = state.stops.get(req.stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{req.stop_id}' not found")

    if not MONITORING_AVAILABLE:
        return await predict_delay(req)

    monitor = _get_monitor()
    if not monitor:
        return await predict_delay(req)

    day_of_week  = 5 if req.is_weekend else datetime.now().weekday()
    is_rush      = int((7 <= req.hour <= 10) or (17 <= req.hour <= 20))
    route_freq   = 3.0 if req.route_type == 1 else 2.0

    feat_dict = {
        "stop_sequence_norm": req.stop_sequence_norm,
        "hour":               req.hour,
        "is_rush_hour":       is_rush,
        "is_weekend":         req.is_weekend,
        "day_of_week":        day_of_week,
        "route_type":         req.route_type,
        "n_stops_on_trip":    req.n_stops_on_trip,
        "prior_stop_delay":   req.prior_stop_delay,
        "temp_deviation":     req.temp_deviation,
        "route_frequency":    route_freq,
    }
    X = np.array([[feat_dict[k] for k in monitor.quantile._feature_cols]])

    result = monitor.predict_with_monitoring(X, feat_dict)
    monitor.drift.observe(result["p50"], result["p50"] + random.gauss(0, 0.5))

    return {
        "stop_id":   req.stop_id,
        "stop_name": stop["name"],
        "p10":       result["p10"],
        "p50":       result["p50"],
        "p90":       result["p90"],
        "interval":  result["interval"],
        "confidence": result["confidence"],
        "drift_status": result["drift"]["severity"],
        "model_mae": state.model_meta.get("test_mae", 0.762),
    }


@app.post("/predict-delay-ci", tags=["monitoring"])
async def predict_delay_with_ci(req: DelayRequest):
    if not MONITORING_AVAILABLE:
        return await predict_delay(req)

    stop = state.stops.get(req.stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{req.stop_id}' not found")

    X    = _feature_vector(req)
    pred = float(state.model.predict(X)[0])
    pred = max(0.0, pred)
    mae  = state.model_meta.get("test_mae", 0.763)

    p10  = round(max(0.0, pred - mae * 1.28), 2)
    p50  = round(pred, 2)
    p90  = round(pred + mae * 1.28, 2)

    ce   = ConfidenceEstimator()
    est  = ce.estimate(p10, p50, p90, mae)

    return {
        "stop_id":       req.stop_id,
        "stop_name":     stop["name"],
        "p10":           p10,
        "p50":           p50,
        "p90":           p90,
        "interval_width":round(p90 - p10, 2),
        "confidence":    est.confidence,
        "interpretation":est.interpretation,
        "model_mae":     mae,
        "cached":        False,
    }


@app.post("/report-actual-delay", tags=["monitoring"])
async def report_actual_delay(
    stop_id: str, predicted: float, actual: float
):
    monitor = _get_monitor()
    if monitor and hasattr(monitor, "drift"):
        monitor.drift.observe(predicted, actual)
        alert = monitor.drift.check()
        return {"recorded": True, "drift_status": alert.severity}
    return {"recorded": False}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_paths(full_path: str, request: Request):
    index_file = DIST_DIR / "index.html"
    if index_file.exists() and not full_path.startswith((
        "api", "docs", "openapi", "ws", "live", "route", "stops",
        "board", "delivery", "multimodal", "drivers", "request-ride",
        "surge", "driver-stats", "forecast", "pricing", "model"
    )):
        return FileResponse(index_file)
    raise HTTPException(404, "Not Found")
