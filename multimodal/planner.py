"""
multimodal/planner.py — Upgrade 4: Multi-Modal Route Planner
Transit Optimizer

What this does:
  Combines FOUR transport modes into ONE unified graph:
    🚗 Drive   — car/scooter on city roads (fastest door-to-door)
    🚇 Metro   — BMRCL Purple/Green line (fast, fixed stops)
    🚌 Bus     — BMTC routes (wide coverage, slower)
    🚶 Walk    — short connections between modes (< 800m)

  The user picks any two points in the city.
  A* finds the optimal MIX of modes automatically.
  Output: "Drive 4km to Hebbal Metro → Metro to MG Road → Walk 300m to office"

Key algorithm insight:
  Multi-modal is NOT multiple algorithms running in sequence.
  It's ONE A* run on a COMBINED graph that has all four edge types.
  The router picks the fastest combination naturally — no special logic needed.

Concepts covered:
  - Graph merging (combine 4 sub-graphs into 1)
  - Edge type labelling (mode = drive/metro/bus/walk)
  - Parking penalty (switching from drive to any other mode costs wait time)
  - Mode-aware path reconstruction (group by mode for human-readable output)
  - Intermodal transfer nodes (parking lots, metro entrances, bus stops)
"""

import json
import math
import heapq
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.columns import Columns
from rich         import box

console = Console()
GRAPH_PATH = Path("data/graph_with_transfers.json")


# ════════════════════════════════════════════════════════════════════════════════
# 1. NODE DEFINITIONS
# Every location in the city is a node. Nodes have a mode context:
#   pure nodes  — just a location (home, office, restaurant)
#   stop nodes  — bus stop or metro station (can board transit here)
#   park nodes  — parking lot (can switch from driving to walking/transit)
# ════════════════════════════════════════════════════════════════════════════════

# Bengaluru locations with real GPS coordinates
LOCATIONS = {
    # Origins / Destinations (where people actually start/end)
    "HOME_WHITEFIELD": {"name": "Home — Whitefield",        "lat": 12.9698, "lon": 77.7499, "type": "location"},
    "HOME_HEBBAL":     {"name": "Home — Hebbal",             "lat": 13.0353, "lon": 77.5963, "type": "location"},
    "HOME_JAYANAGAR":  {"name": "Home — Jayanagar",          "lat": 12.9252, "lon": 77.5938, "type": "location"},
    "OFFICE_MANYATA":  {"name": "Manyata Tech Park",         "lat": 13.0452, "lon": 77.6215, "type": "location"},
    "OFFICE_ECITY":    {"name": "Electronic City",           "lat": 12.8458, "lon": 77.6661, "type": "location"},
    "OFFICE_KORAMA":   {"name": "Koramangala (IT hub)",      "lat": 12.9339, "lon": 77.6269, "type": "location"},

    # Metro stations (BMRCL Purple + Green line)
    "M_WHITEFIELD":    {"name": "Whitefield Metro",          "lat": 12.9688, "lon": 77.7494, "type": "metro"},
    "M_MARATHAHALLI":  {"name": "Marathahalli Metro",        "lat": 12.9577, "lon": 77.7004, "type": "metro"},
    "M_INDIRANAGAR":   {"name": "Indiranagar Metro",         "lat": 12.9783, "lon": 77.6406, "type": "metro"},
    "M_TRINITY":       {"name": "Trinity Metro",             "lat": 12.9762, "lon": 77.6183, "type": "metro"},
    "M_MGROAD":        {"name": "MG Road Metro",             "lat": 12.9755, "lon": 77.6063, "type": "metro"},
    "M_MAJESTIC":      {"name": "Majestic Metro",            "lat": 12.9774, "lon": 77.5726, "type": "metro"},
    "M_YESHWANTHPUR":  {"name": "Yeshwanthpur Metro",        "lat": 12.9933, "lon": 77.5514, "type": "metro"},
    "M_HEBBAL":        {"name": "Hebbal Metro (proposed)",   "lat": 13.0350, "lon": 77.5960, "type": "metro"},
    "M_SILKBOARD":     {"name": "Silk Board Metro (u/c)",    "lat": 12.9170, "lon": 77.6232, "type": "metro"},
    "M_ECITY":         {"name": "Electronics City Metro",    "lat": 12.8461, "lon": 77.6658, "type": "metro"},

    # Key bus stops
    "B_KORAMANGALA":   {"name": "Koramangala Bus Stop",      "lat": 12.9341, "lon": 77.6271, "type": "bus"},
    "B_SILKBOARD":     {"name": "Silk Board Junction",       "lat": 12.9170, "lon": 77.6232, "type": "bus"},
    "B_HEBBAL":        {"name": "Hebbal Bus Stop",           "lat": 12.9354, "lon": 77.5964, "type": "bus"},

    # Parking lots (drive → walk/transit interchange)
    "P_WHITEFIELD":    {"name": "Whitefield Parking",        "lat": 12.9701, "lon": 77.7497, "type": "parking"},
    "P_INDIRANAGAR":   {"name": "Indiranagar Parking",       "lat": 12.9788, "lon": 77.6410, "type": "parking"},
    "P_MAJESTIC":      {"name": "Majestic Parking",          "lat": 12.9772, "lon": 77.5720, "type": "parking"},
}


# ════════════════════════════════════════════════════════════════════════════════
# 2. EDGE DEFINITIONS BY MODE
# Each mode has its own set of edges with realistic travel times.
# ════════════════════════════════════════════════════════════════════════════════

# Metro edges (BMRCL timetable, peak hours every 4 min)
# (from, to, minutes) — bidirectional
METRO_EDGES = [
    ("M_WHITEFIELD",   "M_MARATHAHALLI",  7,  "Purple Line"),
    ("M_MARATHAHALLI", "M_INDIRANAGAR",   8,  "Purple Line"),
    ("M_INDIRANAGAR",  "M_TRINITY",       4,  "Purple Line"),
    ("M_TRINITY",      "M_MGROAD",        3,  "Purple Line"),
    ("M_MGROAD",       "M_MAJESTIC",      5,  "Purple Line"),
    ("M_MAJESTIC",     "M_YESHWANTHPUR",  8,  "Green Line"),
    ("M_MAJESTIC",     "M_SILKBOARD",    18,  "Green Line"),   # under construction
    ("M_SILKBOARD",    "M_ECITY",        12,  "Green Line"),
]

# Drive edges (congestion-adjusted for off-peak; rush adds 60-80%)
DRIVE_EDGES = [
    ("HOME_WHITEFIELD", "P_WHITEFIELD",    3,  "drive"),
    ("HOME_WHITEFIELD", "M_WHITEFIELD",    5,  "drive"),
    ("HOME_WHITEFIELD", "HOME_HEBBAL",    55,  "drive"),  # ORR + NH44
    ("HOME_HEBBAL",     "OFFICE_MANYATA",  8,  "drive"),
    ("HOME_HEBBAL",     "M_HEBBAL",        6,  "drive"),
    ("HOME_JAYANAGAR",  "B_SILKBOARD",     8,  "drive"),
    ("HOME_JAYANAGAR",  "P_MAJESTIC",     12,  "drive"),
    ("P_WHITEFIELD",    "M_WHITEFIELD",    3,  "walk"),
    ("P_INDIRANAGAR",   "M_INDIRANAGAR",   4,  "walk"),
    ("P_MAJESTIC",      "M_MAJESTIC",      5,  "walk"),
    ("M_ECITY",         "OFFICE_ECITY",    8,  "drive"),
    ("M_MAJESTIC",      "OFFICE_KORAMA",  14,  "drive"),
    ("M_INDIRANAGAR",   "OFFICE_KORAMA",   9,  "drive"),
    ("B_SILKBOARD",     "OFFICE_KORAMA",   7,  "bus"),
    ("B_SILKBOARD",     "OFFICE_ECITY",   22,  "bus"),
    ("M_SILKBOARD",     "OFFICE_KORAMA",   6,  "walk"),
]

# Walk edges (< 800m, at 5 km/h = ~10 min/km)
WALK_EDGES = [
    ("M_WHITEFIELD",   "HOME_WHITEFIELD",   7,  "walk"),
    ("M_WHITEFIELD",   "P_WHITEFIELD",      2,  "walk"),
    ("M_INDIRANAGAR",  "P_INDIRANAGAR",     3,  "walk"),
    ("M_INDIRANAGAR",  "OFFICE_KORAMA",    12,  "walk"),
    ("M_MGROAD",       "M_TRINITY",         6,  "walk"),
    ("M_MAJESTIC",     "P_MAJESTIC",        4,  "walk"),
    ("M_ECITY",        "OFFICE_ECITY",      6,  "walk"),
    ("M_HEBBAL",       "OFFICE_MANYATA",   10,  "walk"),
    ("M_SILKBOARD",    "B_SILKBOARD",       2,  "walk"),
    ("B_KORAMANGALA",  "OFFICE_KORAMA",     5,  "walk"),
    ("HOME_JAYANAGAR", "B_SILKBOARD",      25,  "walk"),  # long but possible
]

# Transfer penalties (switching modes costs waiting time)
TRANSFER_PENALTY = {
    ("drive",  "walk"):   2,   # park and get out — 2 min
    ("drive",  "metro"):  5,   # park + walk to metro + wait
    ("drive",  "bus"):    4,   # park + walk to stop + wait
    ("walk",   "metro"):  3,   # walk to metro + wait
    ("walk",   "bus"):    4,   # walk to stop + wait
    ("metro",  "walk"):   1,   # exit metro
    ("metro",  "bus"):    4,   # exit metro + walk to bus
    ("bus",    "walk"):   1,   # alight bus
    ("bus",    "metro"):  4,   # alight + walk to metro
}


# ════════════════════════════════════════════════════════════════════════════════
# 3. GRAPH BUILDER
# Merges all four mode sub-graphs into one unified adjacency list.
# ════════════════════════════════════════════════════════════════════════════════

def build_multimodal_graph(congestion_factor: float = 1.0) -> dict:
    """
    Build the unified multi-modal graph.
    congestion_factor: 1.0 = off-peak, 2.0 = rush hour (drives 2× slower)
    """
    graph: dict[str, dict] = {loc: {} for loc in LOCATIONS}

    def add_edge(src, dst, mins, mode, line=None):
        if src not in graph:
            graph[src] = {}
        actual_mins = mins * congestion_factor if mode == "drive" else mins
        graph[src][dst] = {
            "minutes":  round(actual_mins, 1),
            "mode":     mode,
            "line":     line,
            "raw_mins": mins,
        }

    # Metro — bidirectional, not affected by road congestion
    for a, b, mins, line in METRO_EDGES:
        add_edge(a, b, mins, "metro", line)
        add_edge(b, a, mins, "metro", line)

    # Drive + walk from DRIVE_EDGES
    for a, b, mins, mode in DRIVE_EDGES:
        add_edge(a, b, mins, mode)

    # Walk — bidirectional
    for a, b, mins, mode in WALK_EDGES:
        add_edge(a, b, mins, mode)
        add_edge(b, a, mins, mode)

    return graph


# ════════════════════════════════════════════════════════════════════════════════
# 4. MULTI-MODAL A*
# Identical algorithm to Phase 1 — the graph structure does all the work.
# One addition: mode-switching penalty added when edge mode changes.
# ════════════════════════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1); dl = math.radians(lon2-lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def heuristic(node_id: str, goal_id: str) -> float:
    """Haversine distance / 40 km/h average → minutes lower bound."""
    s = LOCATIONS.get(node_id)
    g = LOCATIONS.get(goal_id)
    if not s or not g:
        return 0.0
    return (haversine_km(s["lat"], s["lon"], g["lat"], g["lon"]) / 40) * 60


def astar_multimodal(graph: dict, start: str, end: str,
                     allowed_modes: set[str] = None) -> dict:
    """
    A* on the multi-modal graph with transfer penalties.

    allowed_modes: optional set to restrict modes e.g. {"metro","walk"}
    """
    if allowed_modes is None:
        allowed_modes = {"drive", "metro", "bus", "walk"}

    t0  = time.perf_counter()
    INF = float("inf")

    g_cost  = {n: INF for n in LOCATIONS}
    g_cost[start] = 0.0
    parent: dict = {n: None for n in LOCATIONS}
    # heap: (f, g, node, current_mode)
    heap    = [(heuristic(start, end), 0.0, start, None)]
    visited = set()
    nv      = 0

    while heap:
        f, gc, node, cur_mode = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        nv += 1
        if node == end:
            break

        for nb, edge in graph.get(node, {}).items():
            if nb in visited:
                continue
            mode = edge["mode"]
            if mode not in allowed_modes:
                continue

            # Transfer penalty when switching modes
            penalty = 0.0
            if cur_mode and cur_mode != mode:
                penalty = TRANSFER_PENALTY.get((cur_mode, mode), 2.0)

            new_g = gc + edge["minutes"] + penalty
            if new_g < g_cost.get(nb, INF):
                g_cost[nb] = new_g
                parent[nb] = (node, edge, penalty)
                f_new = new_g + heuristic(nb, end)
                heapq.heappush(heap, (f_new, new_g, nb, mode))

    elapsed = (time.perf_counter() - t0) * 1000

    if g_cost.get(end, INF) == INF:
        return {"found": False, "nodes_visited": nv, "elapsed_ms": elapsed}

    # Reconstruct path
    path, segs = [], []
    node = end
    while node:
        path.append(node)
        entry = parent.get(node)
        if entry:
            prev, edge, penalty = entry
            segs.append({"from": prev, "to": node,
                         "edge": edge, "penalty": penalty})
            node = prev
        else:
            node = None
    path.reverse()
    segs.reverse()

    return {
        "found":         True,
        "total_minutes": round(g_cost[end], 1),
        "path":          path,
        "segments":      segs,
        "nodes_visited": nv,
        "elapsed_ms":    elapsed,
    }


# ════════════════════════════════════════════════════════════════════════════════
# 5. HUMAN-READABLE DIRECTIONS
# Merge consecutive same-mode segments, add emoji, format for display.
# ════════════════════════════════════════════════════════════════════════════════

MODE_EMOJI = {"drive": "🚗", "metro": "🚇", "bus": "🚌", "walk": "🚶"}
MODE_COLOR = {"drive": "yellow", "metro": "blue", "bus": "green", "walk": "dim"}

def build_directions(result: dict) -> list[dict]:
    """Merge consecutive same-mode steps into readable instructions."""
    if not result.get("found"):
        return []

    merged = []
    cur_mode = None
    cur_seg  = None

    for seg in result["segments"]:
        mode  = seg["edge"]["mode"]
        fname = LOCATIONS.get(seg["from"], {}).get("name", seg["from"])
        tname = LOCATIONS.get(seg["to"],   {}).get("name", seg["to"])

        if mode != cur_mode:
            if cur_seg:
                merged.append(cur_seg)
            cur_seg = {
                "mode":    mode,
                "from":    fname,
                "to":      tname,
                "minutes": seg["edge"]["minutes"],
                "penalty": seg["penalty"],
                "line":    seg["edge"].get("line"),
                "stops":   [fname, tname],
            }
            cur_mode = mode
        else:
            cur_seg["to"]      = tname
            cur_seg["minutes"] += seg["edge"]["minutes"]
            cur_seg["stops"].append(tname)

    if cur_seg:
        merged.append(cur_seg)

    return merged


def print_directions(directions: list, result: dict,
                     start_name: str, end_name: str):
    """Print Google Maps-style multi-modal directions."""
    console.print(Panel(
        f"  [bold white]{start_name}[/bold white]  →  [bold white]{end_name}[/bold white]\n\n"
        f"  [cyan]Total:[/cyan] [bold]{result['total_minutes']} min[/bold]   "
        f"[cyan]Modes:[/cyan] {len(set(d['mode'] for d in directions))}   "
        f"[cyan]Transfers:[/cyan] {sum(1 for d in directions if d['penalty'] > 0)}\n"
        f"  [dim]{result['nodes_visited']} nodes · {result['elapsed_ms']:.3f}ms[/dim]",
        border_style="blue",
        padding=(0, 1),
    ))

    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column("icon",    width=4)
    tbl.add_column("action",  min_width=44)
    tbl.add_column("time",    justify="right", width=7, style="dim")
    tbl.add_column("running", justify="right", width=8)

    running = 0.0
    for d in directions:
        running += d["minutes"]
        icon  = MODE_EMOJI.get(d["mode"], "?")
        color = MODE_COLOR.get(d["mode"], "white")
        line  = f" [{d['line']}]" if d.get("line") else ""
        n_stops = len(d["stops"]) - 1

        action = (
            f"[{color}]{d['mode'].title()}{line}[/{color}]  "
            f"[bold]{d['from']}[/bold] → [bold]{d['to']}[/bold]"
            + (f"  [dim]({n_stops} stop{'s' if n_stops != 1 else ''})[/dim]"
               if d["mode"] in ("metro","bus") and n_stops > 0 else "")
        )
        tbl.add_row(
            icon, action,
            f"{d['minutes']:.0f}m",
            f"[bold]{running:.0f}m[/bold]",
        )
        # Show transfer penalty
        if d["penalty"] > 0:
            tbl.add_row(
                "⏳",
                f"[dim]Transfer wait[/dim]",
                f"{d['penalty']:.0f}m",
                f"[dim]{running:.0f}m[/dim]",
            )
            running += d["penalty"]

    console.print(tbl)


# ════════════════════════════════════════════════════════════════════════════════
# 6. SCENARIO COMPARISONS
# ════════════════════════════════════════════════════════════════════════════════

def compare_scenarios(graph_off: dict, graph_rush: dict,
                      start: str, end: str):
    """Compare all-modes vs metro-only vs drive-only for rush + offpeak."""
    scenarios = [
        ("All modes (off-peak)",  graph_off,  {"drive","metro","bus","walk"}),
        ("All modes (rush hour)", graph_rush, {"drive","metro","bus","walk"}),
        ("Metro + walk only",     graph_off,  {"metro","walk"}),
        ("Drive only",            graph_off,  {"drive","walk"}),
        ("Bus + walk only",       graph_off,  {"bus","walk"}),
    ]

    tbl = Table(
        title=f"Scenario comparison: {LOCATIONS[start]['name']} → {LOCATIONS[end]['name']}",
        box=box.ROUNDED, header_style="bold cyan",
    )
    tbl.add_column("Scenario",     min_width=26)
    tbl.add_column("Time",         justify="right", width=8)
    tbl.add_column("Modes used",   min_width=22)
    tbl.add_column("Transfers",    justify="right", width=10)
    tbl.add_column("vs fastest",   justify="right", width=12)

    results = []
    for label, graph, modes in scenarios:
        r = astar_multimodal(graph, start, end, modes)
        results.append((label, r, modes))

    best_time = min(r["total_minutes"] for _, r, _ in results if r["found"])

    for label, r, modes in results:
        if not r["found"]:
            tbl.add_row(label, "[red]no route[/red]", "—", "—", "—")
            continue
        dirs      = build_directions(r)
        mode_used = " + ".join(dict.fromkeys(d["mode"] for d in dirs))
        xfers     = str(sum(1 for d in dirs if d["penalty"] > 0))
        delta     = r["total_minutes"] - best_time
        vs        = "[green]fastest[/green]" if delta == 0 else f"+{delta:.0f}m"
        tbl.add_row(label, f"{r['total_minutes']}m", mode_used, xfers, vs)

    console.print(tbl)


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Upgrade 4: Multi-Modal Routing\n"
        "[dim]Drive + Metro + Bus + Walk · One A* · Bengaluru[/dim]",
        border_style="blue",
    ))

    # Build graphs
    graph_off  = build_multimodal_graph(congestion_factor=1.0)
    graph_rush = build_multimodal_graph(congestion_factor=2.2)
    n_nodes = len(LOCATIONS)
    n_edges = sum(len(v) for v in graph_off.values())
    console.print(
        f"[green]✓[/green] Multi-modal graph: "
        f"{n_nodes} nodes · {n_edges} edges · 4 modes\n"
    )

    # ── Demo 1: Whitefield → Electronic City ──────────────────────────────────
    console.rule("[bold]Demo 1 — Whitefield → Electronic City (off-peak)[/bold]")
    r1 = astar_multimodal(graph_off, "HOME_WHITEFIELD", "OFFICE_ECITY")
    if r1["found"]:
        print_directions(build_directions(r1), r1, "Home (Whitefield)", "Electronic City")

    # ── Demo 2: Same route, rush hour ─────────────────────────────────────────
    console.rule("[bold]Demo 2 — Same route, rush hour (8am)[/bold]")
    r2 = astar_multimodal(graph_rush, "HOME_WHITEFIELD", "OFFICE_ECITY")
    if r2["found"]:
        print_directions(build_directions(r2), r2, "Home (Whitefield)", "Electronic City")

    # ── Demo 3: Hebbal → Koramangala IT hub ───────────────────────────────────
    console.rule("[bold]Demo 3 — Hebbal → Koramangala (off-peak)[/bold]")
    r3 = astar_multimodal(graph_off, "HOME_HEBBAL", "OFFICE_KORAMA")
    if r3["found"]:
        print_directions(build_directions(r3), r3, "Home (Hebbal)", "Koramangala")

    # ── Demo 4: Jayanagar → Manyata Tech Park ────────────────────────────────
    console.rule("[bold]Demo 4 — Jayanagar → Manyata Tech Park[/bold]")
    r4 = astar_multimodal(graph_off, "HOME_JAYANAGAR", "OFFICE_MANYATA")
    if r4["found"]:
        print_directions(build_directions(r4), r4, "Home (Jayanagar)", "Manyata Tech Park")

    # ── Demo 5: Full scenario comparison ─────────────────────────────────────
    console.rule("[bold]Demo 5 — Scenario comparison[/bold]")
    compare_scenarios(graph_off, graph_rush, "HOME_WHITEFIELD", "OFFICE_ECITY")

    # ── Concept summary ───────────────────────────────────────────────────────
    console.print(Panel(
        "[bold]Why multi-modal is still just one A* run[/bold]\n\n"
        "  Most people think you need:\n"
        "    Step 1: Find best drive route\n"
        "    Step 2: Find best metro route\n"
        "    Step 3: Compare and combine\n\n"
        "  That's wrong — and gives suboptimal results.\n\n"
        "  The correct approach:\n"
        "    Build ONE graph with all edge types labelled by mode.\n"
        "    Run A* once. The algorithm explores all combinations\n"
        "    simultaneously and finds the globally optimal mix.\n\n"
        "  Transfer penalties are just extra edge weights added\n"
        "  when the mode changes — no special logic needed.\n\n"
        "  [dim]This is how Google Maps, Apple Maps, and Citymapper work.\n"
        "  The same Dijkstra/A* runs over a multi-modal graph.[/dim]",
        title="Algorithm insight",
        border_style="dim",
    ))

    console.print(Panel(
        "[bold green]Upgrade 4 complete![/bold green]\n\n"
        "  Your system now handles:\n"
        "  🚗 Drive → park → 🚇 Metro → 🚶 Walk to office\n"
        "  🚶 Walk → 🚌 Bus → 🚶 Walk → 🚇 Metro → 🚶 Walk\n"
        "  🚗 Drive only (if that's faster off-peak)\n"
        "  Any combination A* finds optimal\n\n"
        "  [bold]The answer to your colleague's 'IT employees drive' objection:[/bold]\n"
        "  'My system handles that — it routes drive+metro+walk together\n"
        "  and tells you when driving part-way + taking metro is faster\n"
        "  than driving all the way. That's what Google Maps does.'",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
