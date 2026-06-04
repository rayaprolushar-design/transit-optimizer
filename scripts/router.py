"""
scripts/router.py
Reusable routing module — A* and Dijkstra on the transit graph.
Imported by main.py (CLI) and later by the FastAPI server (Phase 2).
"""

import heapq
import math
import time

BUS_SPEED_KM_MIN = 0.333


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _heuristic(stop_id, goal_id, stops):
    s, g = stops.get(stop_id), stops.get(goal_id)
    if not s or not g or stop_id == goal_id:
        return 0.0
    d = _haversine_km(float(s["lat"]), float(s["lon"]),
                      float(g["lat"]), float(g["lon"]))
    return d / BUS_SPEED_KM_MIN


def _reconstruct(parent, stops, graph, start_id, end_id):
    path_nodes, edges = [], []
    node = end_id
    while node:
        path_nodes.append(node)
        entry = parent.get(node)
        if entry:
            prev, edge_data = entry
            edges.append((prev, node, edge_data))
            node = prev
        else:
            node = None
    path_nodes.reverse()
    edges.reverse()
    return path_nodes, edges


def _astar(graph, stops, start_id, end_id):
    g = {s: float("inf") for s in stops}
    g[start_id] = 0.0
    parent = {s: None for s in stops}
    heap = [(_heuristic(start_id, end_id, stops), 0.0, start_id)]
    visited = set()
    nv = 0
    t0 = time.perf_counter()

    while heap:
        f, gc, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node); nv += 1
        if node == end_id:
            break
        for nb, edge in graph.get(node, {}).items():
            if nb in visited:
                continue
            ng = gc + edge["minutes"]
            if ng < g.get(nb, float("inf")):
                g[nb] = ng
                parent[nb] = (node, edge)
                heapq.heappush(heap, (ng + _heuristic(nb, end_id, stops), ng, nb))

    return g, parent, nv, (time.perf_counter() - t0) * 1000


def _dijkstra(graph, stops, start_id, end_id):
    dist = {s: float("inf") for s in stops}
    dist[start_id] = 0.0
    parent = {s: None for s in stops}
    heap = [(0.0, start_id)]
    visited = set()
    nv = 0
    t0 = time.perf_counter()

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node); nv += 1
        if node == end_id:
            break
        for nb, edge in graph.get(node, {}).items():
            if nb in visited:
                continue
            nc = cost + edge["minutes"]
            if nc < dist.get(nb, float("inf")):
                dist[nb] = nc
                parent[nb] = (node, edge)
                heapq.heappush(heap, (nc, nb))

    return dist, parent, nv, (time.perf_counter() - t0) * 1000


def find_route(graph: dict, stops: dict,
               start_id: str, end_id: str,
               algorithm: str = "astar") -> dict:
    """
    Find shortest path between two stop IDs.
    Returns a result dict compatible with build_directions().
    """
    if algorithm.lower() == "dijkstra":
        costs, parent, nv, ms = _dijkstra(graph, stops, start_id, end_id)
    else:
        costs, parent, nv, ms = _astar(graph, stops, start_id, end_id)

    total = costs.get(end_id, float("inf"))

    if total == float("inf"):
        return {"found": False, "nodes_visited": nv, "elapsed_ms": ms}

    path_nodes, path_edges = _reconstruct(parent, stops, graph, start_id, end_id)

    return {
        "found":         True,
        "total_minutes": round(total, 1),
        "path":          path_nodes,
        "edges":         path_edges,
        "nodes_visited": nv,
        "elapsed_ms":    ms,
    }


def build_directions(result: dict, stops: dict) -> list[dict]:
    """
    Convert raw edge list into merged, human-readable direction segments.
    Consecutive edges on the same route are merged into one instruction.
    """
    if not result.get("found"):
        return []

    segments = []
    cur_route = None
    cur_seg   = None

    for from_id, to_id, edge in result["edges"]:
        route     = edge.get("route", "?")
        edge_type = edge.get("type", "transit")

        if route != cur_route:
            if cur_seg:
                segments.append(cur_seg)
            cur_seg = {
                "type":    "walk" if edge_type == "walk" else "transit",
                "route":   route,
                "stops":   [from_id, to_id],
                "minutes": edge["minutes"],
                "dist_km": edge.get("dist_km"),
            }
            cur_route = route
        else:
            cur_seg["stops"].append(to_id)
            cur_seg["minutes"] += edge["minutes"]

    if cur_seg:
        segments.append(cur_seg)

    directions = []
    for seg in segments:
        frm  = stops.get(seg["stops"][0],  {}).get("name", seg["stops"][0])
        to   = stops.get(seg["stops"][-1], {}).get("name", seg["stops"][-1])
        n    = len(seg["stops"]) - 1

        if seg["type"] == "walk":
            directions.append({
                "type":    "walk",
                "from":    frm, "to": to,
                "minutes": round(seg["minutes"], 1),
                "dist_km": seg.get("dist_km") or 0,
            })
        else:
            directions.append({
                "type":    "transit",
                "route":   seg["route"],
                "from":    frm, "to": to,
                "stops":   n,
                "minutes": round(seg["minutes"], 1),
            })

    return directions
