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
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.router import find_route, build_directions
from scripts.search import fuzzy_find_stop
from scripts.week9_performance import LRUCache

try:
    from scripts.gps_tracker import live_store, run_live_feed
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    live_store = None

USE_REAL_GPS = os.getenv("USE_REAL_GPS", "0") == "1"

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

    live_delays = live_store.all_delays() if (GPS_AVAILABLE and live_store) else None
    delays_str = ",".join(f"{k}:{v}" for k, v in sorted(live_delays.items())) if live_delays else ""
    key    = f"{sid}:{eid}:{algorithm}:{transfers}:{delays_str}"
    cached = state.route_cache.get(key)
    if cached:
        return {**cached, "cached": True}

    result = find_route(state.graph, state.stops, sid, eid, algorithm, live_delays=live_delays)
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

    if req.prior_stop_delay == 0.0 and GPS_AVAILABLE and live_store:
        predecessors = []
        for u, neighbors in state.graph.items():
            if req.stop_id in neighbors:
                if neighbors[req.stop_id].get("route") != "WALK":
                    predecessors.append(u)
        
        valid_delays = [live_store.get_delay(p) for p in predecessors]
        valid_delays = [d for d in valid_delays if d is not None]
        if valid_delays:
            req.prior_stop_delay = round(sum(valid_delays) / len(valid_delays), 2)
            log.info(f"Seeded prior_stop_delay for {req.stop_id} as {req.prior_stop_delay} from predecessors")

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
#
# Computer Networks concept:
#   HTTP: client asks → server answers once → connection closes.
#   WebSocket: client connects → both sides can send at any time → stays open.
#   This is why dashboards use WebSockets for live data instead of polling.
# ════════════════════════════════════════════════════════════════════════════════

import asyncio
import random
from fastapi import WebSocket, WebSocketDisconnect

# Track all active WebSocket connections
_ws_clients: list[WebSocket] = []


async def _broadcast_delay_events():
    """Background task: push live or simulated delay events to connected clients."""
    routes    = ["Route 5", "Route 12", "Route 27", "Route 33", "M1 Metro", "Route 41"]
    stop_list = list(state.stops.values()) if state.stops else [{"name": "MG Road"}]
    last_seen_timestamp = datetime.now()

    while True:
        await asyncio.sleep(5)
        if not _ws_clients:
            continue

        if GPS_AVAILABLE and live_store:
            events = live_store.recent_events(10)
            new_events = [e for e in events if e.timestamp > last_seen_timestamp]
            if new_events:
                new_events.sort(key=lambda e: e.timestamp)
                for obs in new_events:
                    severity = "high" if obs.delay_min > 4 else "medium" if obs.delay_min > 1 else "low"
                    event = {
                        "route":          obs.route_name,
                        "stop":           obs.stop_name,
                        "delay_minutes":  max(0.0, obs.delay_min),
                        "severity":       severity,
                        "time":           obs.timestamp.strftime("%H:%M"),
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
                
                last_seen_timestamp = new_events[-1].timestamp
                continue

        # Fallback to simulated random event
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


# Broadcaster task is started inside the lifespan context manager


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
        _ws_clients.remove(websocket)
        log.info(f"WebSocket disconnected — {len(_ws_clients)} remaining")


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 1 — Live GPS integration endpoints
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/live-delays", tags=["live"])
async def get_live_delays():
    """
    Current live delay in minutes for every stop that has been observed.
    Returns empty dict if GPS tracker hasn't fired yet.
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
    Returns null if no observation yet.
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
# Dedicated endpoints for bus stop display boards.
# A Raspberry Pi or Android screen at any stop polls these every 30s.
#
# New endpoints:
#   GET /board/{stop_id}          → next arrivals + live delay for one stop
#   GET /board/{stop_id}/full     → full timetable for today
#   WS  /ws/board/{stop_id}       → push updates whenever delay changes
# ════════════════════════════════════════════════════════════════════════════════

from typing import List

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
    """
    Primary display board endpoint.
    Returns the next N arrivals at a stop with live delay predictions.

    Designed for:
      - Raspberry Pi display at bus stop
      - Android/TV screen in metro station
      - Web embed on BMTC website

    Poll every 30 seconds for live updates.
    """
    stop = state.stops.get(stop_id)
    if not stop:
        raise HTTPException(404, f"Stop '{stop_id}' not found")

    now_min   = datetime.now().hour * 60 + datetime.now().minute
    hour      = datetime.now().hour
    is_rush   = int((7 <= hour <= 10) or (17 <= hour <= 20))
    is_wknd   = int(datetime.now().weekday() >= 5)

    # Get live delay from GPS tracker if available
    live_delay = 0.0
    if GPS_AVAILABLE and live_store:
        d = live_store.get_delay(stop_id)
        if d is not None:
            live_delay = d

    # Build arrivals from graph edges (routes that pass through this stop)
    arrivals = []
    for from_id, neighbours in state.graph.items():
        for to_id, edge in neighbours.items():
            if from_id == stop_id and edge.get("route") != "WALK":
                route      = edge.get("route", "?")
                to_stop    = state.stops.get(to_id, {})
                dest_name  = to_stop.get("name", to_id)

                # Scheduled time — generate plausible times every 12 min
                base_offset = (hash(route + stop_id) % 12)
                for dep_offset in range(0, 60, 12):
                    sched_min = now_min + base_offset + dep_offset
                    if sched_min - now_min < 1:
                        continue

                    # ML predicted delay
                    if state.model:
                        X = np.array([[
                            0.5, hour, is_rush, is_wknd,
                            datetime.now().weekday(),
                            3, 6, live_delay, 0.3, 2.0,
                        ]])
                        pred_delay = max(0.0, float(state.model.predict(X)[0]))
                    else:
                        pred_delay = live_delay

                    total_delay  = round((live_delay + pred_delay) / 2, 1)
                    predicted_min = sched_min + total_delay

                    sched_h, sched_m   = divmod(int(sched_min), 60)
                    pred_h,  pred_m    = divmod(int(predicted_min), 60)

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
                    break   # one next arrival per route

    # Sort by predicted arrival time and cap
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


# ── Per-stop WebSocket — push when delay changes ─────────────────────────────

_board_clients: dict[str, list[WebSocket]] = {}


@app.websocket("/ws/board/{stop_id}")
async def ws_board(websocket: WebSocket, stop_id: str):
    """
    WebSocket for a specific stop's display board.
    Pushes an update whenever the delay changes by > 0.5 min.
    Much more efficient than polling every 5s for 100 boards.

    Usage (in display board client):
        ws = new WebSocket("wss://your-api.railway.app/ws/board/S001")
        ws.onmessage = (e) => updateDisplay(JSON.parse(e.data))
    """
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
            # Check for delay change every 5s
            await asyncio.sleep(5)
            current_delay = (
                live_store.get_delay(stop_id)
                if (GPS_AVAILABLE and live_store) else None
            )
            # Push if delay changed by more than 0.5 min
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
        _board_clients[stop_id].remove(websocket)


# ════════════════════════════════════════════════════════════════════════════════
# UPGRADE 3 — Delivery Routing Endpoints
# Same A* algorithm, different graph (road network vs transit stops).
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
    """List all delivery locations (restaurants, customers, warehouses, intersections)."""
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")
    locs = DELIVERY_LOCATIONS
    if type:
        locs = {k: v for k, v in locs.items() if v.get("type") == type}
    return [{"location_id": k, **v} for k, v in locs.items()]


@app.get("/delivery/route", tags=["delivery"])
async def get_delivery_route(
    from_id: str = Query(..., description="Origin location ID e.g. R001"),
    to_id:   str = Query(..., description="Destination location ID e.g. C001"),
    hour:    int = Query(12, ge=0, le=23, description="Hour for congestion model"),
):
    """
    Find fastest delivery route between two locations using A* and road graph.
    Adjusts weights dynamically based on time-of-day traffic congestion.
    """
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")
    if from_id not in DELIVERY_LOCATIONS:
        raise HTTPException(404, f"Location '{from_id}' not found")
    if to_id not in DELIVERY_LOCATIONS:
        raise HTTPException(404, f"Location '{to_id}' not found")

    graph  = build_delivery_graph(hour)
    result = astar_delivery(graph, from_id, to_id)
    if not result.get("found"):
        raise HTTPException(404, f"No route found from '{from_id}' to '{to_id}'")

    path_details = []
    for node in result["path"]:
        loc = DELIVERY_LOCATIONS.get(node, {})
        path_details.append({
            "node_id": node,
            "name":    loc.get("name", node),
            "type":    loc.get("type", "unknown"),
            "lat":     loc.get("lat"),
            "lon":     loc.get("lon"),
        })

    return {
        "from_id":       from_id,
        "from_name":     DELIVERY_LOCATIONS[from_id]["name"],
        "to_id":         to_id,
        "to_name":       DELIVERY_LOCATIONS[to_id]["name"],
        "hour":          hour,
        "total_minutes": result["total_minutes"],
        "total_km":      result["total_km"],
        "nodes_visited": result["nodes_visited"],
        "elapsed_ms":    round(result["elapsed_ms"], 4),
        "path":          path_details,
    }


@app.post("/delivery/multi-stop", tags=["delivery"])
async def delivery_multi_stop(req: MultiStopRequest):
    """
    Solve TSP route optimization for multi-stop delivery batching.
    Finds the optimal sequence of drops starting from start_id.
    """
    if not DELIVERY_AVAILABLE:
        raise HTTPException(503, "Delivery module not installed")
    if req.start_id not in DELIVERY_LOCATIONS:
        raise HTTPException(404, f"Start location '{req.start_id}' not found")
    for sid in req.stop_ids:
        if sid not in DELIVERY_LOCATIONS:
            raise HTTPException(404, f"Drop-off location '{sid}' not found")

    graph  = build_delivery_graph(req.hour)
    result = nearest_neighbour_tsp(graph, req.start_id, req.stop_ids)

    route_details = []
    for node in result["route"]:
        loc = DELIVERY_LOCATIONS.get(node, {})
        route_details.append({
            "node_id": node,
            "name":    loc.get("name", node),
            "type":    loc.get("type", "unknown"),
        })

    return {
        "start_id":        req.start_id,
        "start_name":      DELIVERY_LOCATIONS[req.start_id]["name"],
        "hour":            req.hour,
        "optimized_route": route_details,
        "total_minutes":   result["total_minutes"],
        "total_km":        result["total_km"],
        "stops_count":     result["stops_count"],
    }

