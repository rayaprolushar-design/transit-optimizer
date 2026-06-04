"""
Week 6 — Transfer Edges & Multi-Route Trips
Transit Optimizer | Phase 1

What this script does:
  1. Detects nearby stops using Haversine distance (< WALK_RADIUS_KM)
  2. Adds "walking transfer" edges between them with a time penalty
  3. Rebuilds the enriched graph and saves to data/graph_with_transfers.json
  4. Runs A* on the enriched graph and produces human-readable directions
     e.g. "Take Route 5 from MG Road → Majestic (18 min)
           Walk to Lalbagh Road (4 min)
           Take Route 41 → HSR Layout (22 min)"
  5. Compares routing quality: before vs after transfers

Key CS concepts covered:
  - Graph augmentation (adding synthetic edges)
  - Spatial proximity queries (Haversine threshold)
  - Edge types (transit vs walking)
  - Path post-processing (merge consecutive same-route steps)
  - Real-world data modeling

Run: python scripts/week6_transfers.py
"""

import json
import heapq
import math
import time
from pathlib import Path
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

GRAPH_PATH     = Path("data/graph.json")
ENRICHED_PATH  = Path("data/graph_with_transfers.json")

# ── Tuning constants ──────────────────────────────────────────────────────────
WALK_RADIUS_KM   = 1.2    # stops within 600m get a walking transfer edge
WALK_SPEED_KM_MIN = 0.08  # average walking speed: ~80m/min (4.8 km/h)
TRANSFER_PENALTY  = 3     # extra minutes added per transfer (waiting, boarding)
BUS_SPEED_KM_MIN  = 0.333 # for A* heuristic


# ── Haversine ─────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def walk_minutes(dist_km: float) -> float:
    """Convert km to walking minutes, plus transfer penalty."""
    return (dist_km / WALK_SPEED_KM_MIN) + TRANSFER_PENALTY


# ── 1. Build transfer edges ───────────────────────────────────────────────────

def find_transfer_edges(stops: dict) -> list[dict]:
    """
    For every pair of stops within WALK_RADIUS_KM, create a bidirectional
    walking edge.

    Returns a list of transfer edge descriptors:
        {from_id, to_id, dist_km, minutes, type: "walk"}
    """
    stop_ids = list(stops.keys())
    transfers = []

    for i in range(len(stop_ids)):
        for j in range(i + 1, len(stop_ids)):
            a_id, b_id = stop_ids[i], stop_ids[j]
            a, b = stops[a_id], stops[b_id]

            dist = haversine_km(
                float(a["lat"]), float(a["lon"]),
                float(b["lat"]), float(b["lon"]),
            )

            if dist <= WALK_RADIUS_KM:
                mins = round(walk_minutes(dist), 1)
                # Add both directions (walking is bidirectional)
                transfers.append({
                    "from_id": a_id, "to_id":   b_id,
                    "dist_km": round(dist, 3),
                    "minutes": mins, "type": "walk",
                })
                transfers.append({
                    "from_id": b_id, "to_id":   a_id,
                    "dist_km": round(dist, 3),
                    "minutes": mins, "type": "walk",
                })

    return transfers


def build_enriched_graph(graph: dict, transfers: list[dict]) -> dict:
    """
    Start with the existing transit graph and inject walking transfer edges.
    Walking edges are only added where no direct transit edge already exists,
    OR where the walk is faster than the bus.
    """
    import copy
    enriched = copy.deepcopy(graph)

    added = 0
    for t in transfers:
        src, dst, mins = t["from_id"], t["to_id"], t["minutes"]

        # Initialise adjacency dict for this stop if needed
        if src not in enriched:
            enriched[src] = {}

        existing = enriched[src].get(dst)
        if existing is None or mins < existing["minutes"]:
            enriched[src][dst] = {
                "minutes": mins,
                "route":   "WALK",
                "trips":   1,
                "type":    "walk",
                "dist_km": t["dist_km"],
            }
            added += 1

    return enriched, added


# ── 2. A* on enriched graph ───────────────────────────────────────────────────

def heuristic(stop_id: str, goal_id: str, stops: dict) -> float:
    s, g = stops.get(stop_id), stops.get(goal_id)
    if not s or not g or stop_id == goal_id:
        return 0.0
    d = haversine_km(float(s["lat"]), float(s["lon"]),
                     float(g["lat"]), float(g["lon"]))
    return d / BUS_SPEED_KM_MIN


def astar(graph: dict, stops: dict, start_id: str, end_id: str) -> dict:
    """A* — same implementation as Week 5, works on any graph dict."""
    g_cost = {s: float("inf") for s in stops}
    g_cost[start_id] = 0.0
    parent: dict = {s: None for s in stops}
    heap = [(heuristic(start_id, end_id, stops), 0.0, start_id)]
    visited = set()
    nodes_visited = 0
    t0 = time.perf_counter()

    while heap:
        f, gc, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        nodes_visited += 1
        if node == end_id:
            break
        for nb, edge in graph.get(node, {}).items():
            if nb in visited:
                continue
            new_g = gc + edge["minutes"]
            if new_g < g_cost.get(nb, float("inf")):
                g_cost[nb] = new_g
                parent[nb] = (node, edge)
                heapq.heappush(heap, (new_g + heuristic(nb, end_id, stops), new_g, nb))

    elapsed = (time.perf_counter() - t0) * 1000

    if g_cost.get(end_id, float("inf")) == float("inf"):
        return {"found": False, "elapsed_ms": elapsed, "nodes_visited": nodes_visited}

    # Reconstruct path with full edge data
    path_nodes, path_edges = [], []
    node = end_id
    while node:
        path_nodes.append(node)
        entry = parent.get(node)
        if entry:
            path_edges.append((entry[0], node, entry[1]))  # (from, to, edge)
            node = entry[0]
        else:
            node = None
    path_nodes.reverse()
    path_edges.reverse()

    return {
        "found": True,
        "total_minutes": round(g_cost[end_id], 1),
        "path": path_nodes,
        "edges": path_edges,
        "nodes_visited": nodes_visited,
        "elapsed_ms": elapsed,
    }


# ── 3. Human-readable directions ──────────────────────────────────────────────

def build_directions(result: dict, stops: dict) -> list[dict]:
    """
    Merge consecutive same-route steps into single instructions.

    Raw:  MG Rd→Trinity (Rt5), Trinity→Halasuru (Rt5), Halasuru→Majestic (Rt5)
    Nice: Take Route 5: MG Road → Majestic (3 stops, 18 min)
    """
    if not result["found"]:
        return []

    # Group consecutive edges by route
    segments = []
    current_route = None
    current_segment = None

    for from_id, to_id, edge in result["edges"]:
        route = edge.get("route", "?")
        edge_type = edge.get("type", "transit")

        if route != current_route:
            # Start a new segment
            if current_segment:
                segments.append(current_segment)
            current_segment = {
                "type":     edge_type if edge_type == "walk" else "transit",
                "route":    route,
                "stops":    [from_id, to_id],
                "minutes":  edge["minutes"],
                "dist_km":  edge.get("dist_km", None),
            }
            current_route = route
        else:
            # Continue same route — extend segment
            current_segment["stops"].append(to_id)
            current_segment["minutes"] += edge["minutes"]

    if current_segment:
        segments.append(current_segment)

    # Convert stop IDs to names
    directions = []
    for seg in segments:
        from_name = stops.get(seg["stops"][0],  {}).get("name", seg["stops"][0])
        to_name   = stops.get(seg["stops"][-1], {}).get("name", seg["stops"][-1])
        n_stops   = len(seg["stops"]) - 1

        if seg["type"] == "walk":
            dist_m = int(seg["dist_km"] * 1000) if seg["dist_km"] else "?"
            directions.append({
                "type":       "walk",
                "from":       from_name,
                "to":         to_name,
                "minutes":    round(seg["minutes"], 1),
                "detail":     f"Walk {dist_m}m",
            })
        else:
            directions.append({
                "type":       "transit",
                "route":      seg["route"],
                "from":       from_name,
                "to":         to_name,
                "stops":      n_stops,
                "minutes":    round(seg["minutes"], 1),
                "detail":     f"Take Route {seg['route']}",
            })

    return directions


def print_directions(directions: list[dict], start: str, end: str, total_min: float):
    """Print Google Maps-style step-by-step directions."""
    console.print(Panel(
        f"[bold]{start}[/bold] → [bold]{end}[/bold]   "
        f"[cyan]{total_min} min total[/cyan]   "
        f"[dim]{len(directions)} segment(s)[/dim]",
        border_style="green",
    ))

    table = Table(box=box.SIMPLE, header_style="bold magenta", show_header=True)
    table.add_column("",        width=3)
    table.add_column("Action",  min_width=38)
    table.add_column("Time",    justify="right", width=8)
    table.add_column("Running", justify="right", width=9)

    running = 0
    for i, d in enumerate(directions, 1):
        running += d["minutes"]
        if d["type"] == "walk":
            icon   = "🚶"
            action = f"[yellow]Walk[/yellow] {d['from']} → {d['to']}   [dim]{d['detail']}[/dim]"
        else:
            icon   = "🚌"
            action = (f"[blue]Route {d['route']}[/blue]  "
                      f"{d['from']} → {d['to']}   "
                      f"[dim]{d['stops']} stop{'s' if d['stops']!=1 else ''}[/dim]")
        table.add_row(icon, action, f"{d['minutes']}m", f"{running:.0f}m")

    console.print(table)


# ── 4. Before vs After comparison ────────────────────────────────────────────

def compare_graphs(orig_graph: dict, enr_graph: dict,
                   stops: dict, pairs: list[tuple]):
    """Show how transfers open up new routes or improve existing ones."""
    table = Table(
        title="Routing quality: before vs after transfers",
        box=box.ROUNDED, header_style="bold blue",
    )
    table.add_column("From",       min_width=13)
    table.add_column("To",         min_width=13)
    table.add_column("Before",     justify="right")
    table.add_column("After",      justify="right")
    table.add_column("Δ",          justify="right")
    table.add_column("Transfer?",  justify="center")

    for start_id, end_id in pairs:
        r_orig = astar(orig_graph, stops, start_id, end_id)
        r_enr  = astar(enr_graph,  stops, start_id, end_id)

        start_name = stops.get(start_id, {}).get("name", start_id)
        end_name   = stops.get(end_id,   {}).get("name", end_id)

        before = f"{r_orig['total_minutes']}m" if r_orig["found"] else "[red]none[/red]"
        after  = f"{r_enr['total_minutes']}m"  if r_enr["found"]  else "[red]none[/red]"

        if r_orig["found"] and r_enr["found"]:
            delta = r_orig["total_minutes"] - r_enr["total_minutes"]
            delta_str = (f"[green]-{delta}m[/green]" if delta > 0
                         else ("[dim]same[/dim]" if delta == 0
                               else f"[red]+{abs(delta)}m[/red]"))
        elif r_enr["found"] and not r_orig["found"]:
            delta_str = "[green]NEW ROUTE[/green]"
        else:
            delta_str = "[dim]—[/dim]"

        # Detect if the enriched result uses a walk edge
        has_walk = False
        if r_enr.get("edges"):
            has_walk = any(e[2].get("route") == "WALK" for e in r_enr["edges"])

        table.add_row(
            start_name, end_name,
            before, after, delta_str,
            "[green]✓[/green]" if has_walk else "[dim]—[/dim]",
        )

    console.print(table)


# ── 5. Transfer edge summary ──────────────────────────────────────────────────

def print_transfer_summary(transfers: list[dict], stops: dict):
    """Show all generated walking transfer edges."""
    # Deduplicate (show each pair once)
    seen = set()
    unique = []
    for t in transfers:
        key = tuple(sorted([t["from_id"], t["to_id"]]))
        if key not in seen:
            seen.add(key)
            unique.append(t)

    unique.sort(key=lambda x: x["dist_km"])

    table = Table(
        title=f"Walking transfer edges generated ({len(unique)} pairs, "
              f"radius={WALK_RADIUS_KM*1000:.0f}m)",
        box=box.ROUNDED, header_style="bold cyan",
    )
    table.add_column("Stop A",     min_width=14)
    table.add_column("Stop B",     min_width=14)
    table.add_column("Distance",   justify="right")
    table.add_column("Walk time",  justify="right")

    for t in unique:
        a_name = stops.get(t["from_id"], {}).get("name", t["from_id"])
        b_name = stops.get(t["to_id"],   {}).get("name", t["to_id"])
        dist_m = int(t["dist_km"] * 1000)
        table.add_row(a_name, b_name, f"{dist_m}m", f"{t['minutes']}min")

    console.print(table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 6: Transfer Edges\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Load base graph
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    graph  = data["graph"]
    stops  = data["stops"]
    console.print(
        f"[green]✓[/green] Base graph: {len(stops)} stops, "
        f"{sum(len(v) for v in graph.values())} edges\n"
    )

    # ── Step 1: Find transfer edges ───────────────────────────────────────────
    console.rule("[bold]Step 1 — Detect nearby stops[/bold]")
    console.print(
        f"  Walk radius: [bold]{WALK_RADIUS_KM*1000:.0f}m[/bold]   "
        f"Walk speed: [bold]{WALK_SPEED_KM_MIN*1000:.0f}m/min[/bold]   "
        f"Transfer penalty: [bold]+{TRANSFER_PENALTY}min[/bold]\n"
    )
    transfers = find_transfer_edges(stops)
    print_transfer_summary(transfers, stops)

    # ── Step 2: Build enriched graph ──────────────────────────────────────────
    console.rule("[bold]Step 2 — Build enriched graph[/bold]")
    enriched, added = build_enriched_graph(graph, transfers)
    orig_edges = sum(len(v) for v in graph.values())
    enr_edges  = sum(len(v) for v in enriched.values())
    console.print(
        f"[green]✓[/green] Edges before: [bold]{orig_edges}[/bold]   "
        f"after: [bold]{enr_edges}[/bold]   "
        f"transfer edges added: [bold green]+{added}[/bold green]"
    )

    # Save enriched graph
    with open(ENRICHED_PATH, "w") as f:
        json.dump({"stops": stops, "graph": enriched}, f, indent=2)
    size_kb = ENRICHED_PATH.stat().st_size / 1024
    console.print(f"[green]✓[/green] Saved to [bold]{ENRICHED_PATH}[/bold] ({size_kb:.1f} KB)\n")

    # ── Step 3: Before vs after comparison ───────────────────────────────────
    console.rule("[bold]Step 3 — Before vs after: routing quality[/bold]")
    compare_pairs = [
        ("S001", "S007"),   # MG Road → BTM Layout
        ("S001", "S017"),   # MG Road → HSR Layout
        ("S004", "S010"),   # Indiranagar → Majestic
        ("S013", "S018"),   # Hebbal → Electronic City
        ("S015", "S007"),   # Whitefield → BTM Layout
        ("S011", "S006"),   # Rajajinagar → Koramangala
    ]
    compare_graphs(graph, enriched, stops, compare_pairs)

    # ── Step 4: Full directions for interesting routes ────────────────────────
    console.rule("[bold]Step 4 — Human-readable directions[/bold]")

    demo_routes = [
        ("S001", "S017", "MG Road", "HSR Layout"),
        ("S004", "S008", "Indiranagar", "Jayanagar"),
        ("S013", "S007", "Hebbal", "BTM Layout"),
    ]

    for start_id, end_id, start_name, end_name in demo_routes:
        console.print()
        r = astar(enriched, stops, start_id, end_id)
        if r["found"]:
            directions = build_directions(r, stops)
            print_directions(directions, start_name, end_name, r["total_minutes"])
            console.print(
                f"  [dim]A* visited {r['nodes_visited']} nodes "
                f"in {r['elapsed_ms']:.3f}ms[/dim]\n"
            )
        else:
            console.print(f"[red]No route: {start_name} → {end_name}[/red]")

    # ── Step 5: What changed conceptually ────────────────────────────────────
    console.print(Panel(
        "[bold]What transfer edges add to the model[/bold]\n\n"
        "  Before: you can only follow official bus routes in the data.\n"
        "  After:  you can walk between nearby stops and board a different route.\n\n"
        "  This mirrors how Google Maps actually works:\n"
        "    1. Plan transit legs  (routes in GTFS)\n"
        "    2. Add walking legs   (proximity threshold, ~400–800m)\n"
        "    3. Re-run shortest path on the combined graph\n\n"
        f"  Our graph: {orig_edges} transit edges + {added} walk edges "
        f"= {enr_edges} total edges\n\n"
        "  [dim]Production systems use 300–500m walk radius and\n"
        "  model wait time per stop from live timetable data.[/dim]",
        border_style="dim",
        title="Concept",
    ))

    console.print(Panel(
        "[bold green]Week 6 complete![/bold green]\n\n"
        "You've enriched the graph with real-world transfer behavior:\n"
        f"  • {len(transfers)//2} walking transfer pairs detected within "
        f"{WALK_RADIUS_KM*1000:.0f}m\n"
        f"  • +{added} edges injected into graph\n"
        "  • Human-readable directions: merge same-route steps\n"
        "  • Google Maps-style output: 🚌 transit + 🚶 walk segments\n\n"
        "Graph saved → [bold]data/graph_with_transfers.json[/bold]\n\n"
        "Next up → [bold]Week 7–8:[/bold] CLI tool with rich terminal UI\n"
        "          [dim]python main.py --from 'MG Road' --to 'HSR Layout'[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
