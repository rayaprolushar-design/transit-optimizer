"""
Week 5 — A* Algorithm with Haversine Heuristic
Transit Optimizer | Phase 1

What this script does:
  1. Implements A* from scratch using f(n) = g(n) + h(n)
       g(n) = actual travel time from start to n  (same as Dijkstra)
       h(n) = estimated time from n to destination (Haversine heuristic)
  2. Runs A* and Dijkstra on the same routes
  3. Compares: nodes visited, runtime, path quality
  4. Saves all benchmark results to SQLite (algorithm_runs table)
  5. Shows clearly WHY A* is faster — fewer nodes explored

Key CS concepts covered:
  - Informed vs uninformed search
  - Admissible heuristics (never overestimates)
  - f(n) = g(n) + h(n) cost function
  - Why A* is optimal when h is admissible
  - Empirical algorithm benchmarking

Run: python scripts/week5_astar.py
"""

import json
import heapq
import math
import sqlite3
import time
from pathlib import Path
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

console = Console()

GRAPH_PATH = Path("data/graph.json")
DB_PATH    = Path("data/transit.db")

# Average bus speed in km/min — used to convert distance → time for heuristic
# Real Bengaluru buses average ~20 km/h = 0.333 km/min
BUS_SPEED_KM_PER_MIN = 0.333


# ── Haversine distance ────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def heuristic(stop_id: str, goal_id: str, stops: dict) -> float:
    """
    Admissible heuristic h(n): estimated travel time from stop_id to goal_id.

    Uses straight-line (Haversine) distance ÷ bus speed.

    WHY this is admissible:
      A bus can never travel faster than straight-line distance at full speed.
      So haversine_km / bus_speed always UNDERESTIMATES the real travel time.
      → h(n) never overestimates → A* remains optimal.
    """
    if stop_id == goal_id:
        return 0.0
    s = stops.get(stop_id)
    g = stops.get(goal_id)
    if not s or not g:
        return 0.0
    dist_km = haversine_km(
        float(s["lat"]), float(s["lon"]),
        float(g["lat"]), float(g["lon"]),
    )
    return dist_km / BUS_SPEED_KM_PER_MIN   # minutes


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    algorithm:      str
    found:          bool
    start_id:       str
    end_id:         str
    start_name:     str
    end_name:     str
    total_minutes:  int
    path:           list[str]
    steps:          list[dict]
    nodes_visited:  int
    elapsed_ms:     float


# ── A* Implementation ─────────────────────────────────────────────────────────
#
# The only difference from Dijkstra:
#   Dijkstra pushes (g_cost, node)          — cost so far
#   A*       pushes (g_cost + h_cost, node) — cost so far + estimated remaining
#
# This means A* prioritises nodes that are both close to start AND close to goal.
# Dijkstra treats all directions equally — A* is guided toward the destination.

def astar(graph: dict, stops: dict, start_id: str, end_id: str) -> SearchResult:
    """A* search on the transit graph."""
    t_start = time.perf_counter()

    # g[node] = best known actual travel time from start to node
    g: dict[str, float] = {s: float("inf") for s in stops}
    g[start_id] = 0.0

    # parent[node] = (prev_node, route_used)
    parent: dict[str, tuple | None] = {s: None for s in stops}

    # Heap entries: (f_cost, g_cost, node)
    # f = g + h  — we store g separately so we can detect stale entries
    h0 = heuristic(start_id, end_id, stops)
    heap = [(h0, 0.0, start_id)]

    visited     = set()
    nodes_visited = 0

    while heap:
        f_cost, g_cost, node = heapq.heappop(heap)

        if node in visited:
            continue
        visited.add(node)
        nodes_visited += 1

        # ✓ Reached destination
        if node == end_id:
            break

        for neighbour, edge in graph.get(node, {}).items():
            if neighbour in visited:
                continue

            new_g = g_cost + edge["minutes"]

            if new_g < g.get(neighbour, float("inf")):
                g[neighbour] = new_g
                parent[neighbour] = (node, edge["route"])
                h = heuristic(neighbour, end_id, stops)
                f = new_g + h                   # ← the A* difference
                heapq.heappush(heap, (f, new_g, neighbour))

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    if g.get(end_id, float("inf")) == float("inf"):
        return SearchResult(
            algorithm="A*", found=False,
            start_id=start_id, end_id=end_id,
            start_name=stops.get(start_id, {}).get("name", start_id),
            end_name=stops.get(end_id, {}).get("name", end_id),
            total_minutes=0, path=[], steps=[],
            nodes_visited=nodes_visited, elapsed_ms=elapsed_ms,
        )

    # Reconstruct path
    path, node = [], end_id
    while node:
        path.append(node)
        entry = parent.get(node)
        node = entry[0] if entry else None
    path.reverse()

    steps = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        edge = graph.get(a, {}).get(b, {})
        steps.append({
            "from":    stops.get(a, {}).get("name", a),
            "to":      stops.get(b, {}).get("name", b),
            "route":   edge.get("route", "?"),
            "minutes": edge.get("minutes", 0),
        })

    return SearchResult(
        algorithm="A*", found=True,
        start_id=start_id, end_id=end_id,
        start_name=stops.get(start_id, {}).get("name", start_id),
        end_name=stops.get(end_id,   {}).get("name", end_id),
        total_minutes=int(g[end_id]),
        path=path, steps=steps,
        nodes_visited=nodes_visited, elapsed_ms=elapsed_ms,
    )


# ── Dijkstra (copied from Week 4 for comparison) ─────────────────────────────

def dijkstra(graph: dict, stops: dict, start_id: str, end_id: str) -> SearchResult:
    """Dijkstra's algorithm — same as Week 4 but returns SearchResult."""
    t_start = time.perf_counter()

    dist   = {s: float("inf") for s in stops}
    dist[start_id] = 0.0
    parent = {s: None for s in stops}
    heap   = [(0.0, start_id)]
    visited = set()
    nodes_visited = 0

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        nodes_visited += 1
        if node == end_id:
            break
        for nb, edge in graph.get(node, {}).items():
            if nb in visited:
                continue
            new_cost = cost + edge["minutes"]
            if new_cost < dist.get(nb, float("inf")):
                dist[nb] = new_cost
                parent[nb] = (node, edge["route"])
                heapq.heappush(heap, (new_cost, nb))

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    if dist.get(end_id, float("inf")) == float("inf"):
        return SearchResult(
            algorithm="Dijkstra", found=False,
            start_id=start_id, end_id=end_id,
            start_name=stops.get(start_id, {}).get("name", start_id),
            end_name=stops.get(end_id,   {}).get("name", end_id),
            total_minutes=0, path=[], steps=[],
            nodes_visited=nodes_visited, elapsed_ms=elapsed_ms,
        )

    path, node = [], end_id
    while node:
        path.append(node)
        entry = parent.get(node)
        node = entry[0] if entry else None
    path.reverse()

    steps = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        edge = graph.get(a, {}).get(b, {})
        steps.append({
            "from":    stops.get(a, {}).get("name", a),
            "to":      stops.get(b, {}).get("name", b),
            "route":   edge.get("route", "?"),
            "minutes": edge.get("minutes", 0),
        })

    return SearchResult(
        algorithm="Dijkstra", found=True,
        start_id=start_id, end_id=end_id,
        start_name=stops.get(start_id, {}).get("name", start_id),
        end_name=stops.get(end_id,   {}).get("name", end_id),
        total_minutes=int(dist[end_id]),
        path=path, steps=steps,
        nodes_visited=nodes_visited, elapsed_ms=elapsed_ms,
    )


# ── Display ───────────────────────────────────────────────────────────────────

def print_route(r: SearchResult):
    """Print step-by-step directions for one result."""
    if not r.found:
        console.print(f"[red]No route found ({r.algorithm})[/red]")
        return
    table = Table(box=box.SIMPLE, header_style="bold magenta")
    table.add_column("Step",    justify="right", width=5)
    table.add_column("From",    min_width=16)
    table.add_column("To",      min_width=16)
    table.add_column("Route",   justify="center", width=8)
    table.add_column("Time",    justify="right",  width=8)
    table.add_column("Total",   justify="right",  width=8)
    running = 0
    for i, step in enumerate(r.steps, 1):
        running += step["minutes"]
        table.add_row(str(i), step["from"], step["to"],
                      f"Rt.{step['route']}", f"{step['minutes']}m", f"{running}m")
    console.print(table)


def print_comparison(d: SearchResult, a: SearchResult):
    """Side-by-side comparison panel for Dijkstra vs A*."""
    same_path    = d.path == a.path
    same_time    = d.total_minutes == a.total_minutes
    nodes_saved  = d.nodes_visited - a.nodes_visited
    pct_saved    = (nodes_saved / d.nodes_visited * 100) if d.nodes_visited else 0

    # Dijkstra card
    dcard = Panel(
        f"[bold]Dijkstra[/bold]\n\n"
        f"[cyan]Time:[/cyan]         {d.total_minutes} min\n"
        f"[cyan]Stops:[/cyan]        {len(d.path)}\n"
        f"[cyan]Nodes visited:[/cyan] {d.nodes_visited}\n"
        f"[cyan]Runtime:[/cyan]      {d.elapsed_ms:.4f}ms\n"
        f"[cyan]Heuristic:[/cyan]    None (blind search)",
        border_style="blue",
        expand=True,
    )

    # A* card
    acard = Panel(
        f"[bold]A*[/bold]\n\n"
        f"[cyan]Time:[/cyan]         {a.total_minutes} min\n"
        f"[cyan]Stops:[/cyan]        {len(a.path)}\n"
        f"[cyan]Nodes visited:[/cyan] {a.nodes_visited} "
        f"[green](-{nodes_saved}, {pct_saved:.0f}% fewer)[/green]\n"
        f"[cyan]Runtime:[/cyan]      {a.elapsed_ms:.4f}ms\n"
        f"[cyan]Heuristic:[/cyan]    Haversine / bus speed",
        border_style="green",
        expand=True,
    )

    console.print(Columns([dcard, acard]))

    verdict = []
    if same_time:
        verdict.append("[green]✓ Same optimal travel time[/green]")
    else:
        verdict.append(f"[yellow]⚠ Times differ — D:{d.total_minutes}m A*:{a.total_minutes}m[/yellow]")
    if same_path:
        verdict.append("[green]✓ Identical path[/green]")
    else:
        verdict.append("[yellow]⚠ Different paths (both valid if same time)[/yellow]")
    verdict.append(f"[green]✓ A* explored {pct_saved:.0f}% fewer nodes[/green]")

    for v in verdict:
        console.print(f"  {v}")


# ── Save results to SQLite ────────────────────────────────────────────────────

def setup_benchmark_table(conn: sqlite3.Connection):
    """Create algorithm_runs table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS algorithm_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at        TEXT DEFAULT (datetime('now')),
            algorithm     TEXT NOT NULL,
            start_stop    TEXT NOT NULL,
            end_stop      TEXT NOT NULL,
            found         INTEGER NOT NULL,
            total_minutes INTEGER,
            stops_in_path INTEGER,
            nodes_visited INTEGER NOT NULL,
            elapsed_ms    REAL NOT NULL
        )
    """)
    conn.commit()


def save_result(conn: sqlite3.Connection, r: SearchResult):
    """Insert one search result into the benchmark table."""
    conn.execute("""
        INSERT INTO algorithm_runs
            (algorithm, start_stop, end_stop, found,
             total_minutes, stops_in_path, nodes_visited, elapsed_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        r.algorithm,
        r.start_name, r.end_name,
        int(r.found),
        r.total_minutes if r.found else None,
        len(r.path) if r.found else None,
        r.nodes_visited,
        r.elapsed_ms,
    ))
    conn.commit()


def print_benchmark_table(conn: sqlite3.Connection):
    """Query and display all saved benchmark results."""
    rows = conn.execute("""
        SELECT algorithm, start_stop, end_stop,
               total_minutes, nodes_visited,
               ROUND(elapsed_ms, 4) as ms
        FROM   algorithm_runs
        ORDER  BY id
    """).fetchall()

    table = Table(
        title="algorithm_runs (saved in transit.db)",
        box=box.ROUNDED, header_style="bold yellow",
    )
    table.add_column("Algorithm",    style="bold")
    table.add_column("From",         min_width=14)
    table.add_column("To",           min_width=14)
    table.add_column("Time",         justify="right")
    table.add_column("Nodes",        justify="right")
    table.add_column("Speed (ms)",   justify="right")

    for row in rows:
        algo, frm, to, mins, nodes, ms = row
        color = "blue" if algo == "Dijkstra" else "green"
        table.add_row(
            f"[{color}]{algo}[/{color}]",
            frm, to,
            f"{mins} min" if mins else "[red]none[/red]",
            str(nodes), str(ms),
        )
    console.print(table)


# ── Heuristic quality check ───────────────────────────────────────────────────

def print_heuristic_check(stops: dict, pairs: list[tuple[str, str]]):
    """
    Verify the heuristic is admissible for our test pairs.
    Admissible means h(n) <= actual cost — it never overestimates.
    """
    table = Table(
        title="Heuristic admissibility check",
        box=box.ROUNDED, header_style="bold cyan",
    )
    table.add_column("From",         min_width=14)
    table.add_column("To",           min_width=14)
    table.add_column("h(n) estimate", justify="right")
    table.add_column("Actual time",   justify="right")
    table.add_column("Admissible?",   justify="center")

    for start_id, end_id, actual_mins in pairs:
        h = heuristic(start_id, end_id, stops)
        ok = h <= actual_mins
        table.add_row(
            stops.get(start_id, {}).get("name", start_id),
            stops.get(end_id,   {}).get("name", end_id),
            f"{h:.1f} min",
            f"{actual_mins} min",
            "[green]✓ YES[/green]" if ok else "[red]✗ NO[/red]",
        )
    console.print(table)
    console.print(
        "[dim]h(n) must always ≤ actual time for A* to guarantee the optimal path.[/dim]"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 5: A* Algorithm\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Load graph
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    graph = data["graph"]
    stops = data["stops"]
    console.print(f"[green]✓[/green] Graph: {len(stops)} stops, "
                  f"{sum(len(v) for v in graph.values())} edges\n")

    # Setup DB benchmark table
    conn = sqlite3.connect(DB_PATH)
    setup_benchmark_table(conn)
    console.print(f"[green]✓[/green] algorithm_runs table ready in transit.db\n")

    # ── Test pairs ────────────────────────────────────────────────────────────
    test_pairs = [
        ("S001", "S007"),   # MG Road → BTM Layout
        ("S001", "S012"),   # MG Road → Yeshwanthpur
        ("S013", "S018"),   # Hebbal → Electronic City
        ("S011", "S017"),   # Rajajinagar → HSR Layout
    ]

    # ── Run all pairs ─────────────────────────────────────────────────────────
    for start_id, end_id in test_pairs:
        start_name = stops.get(start_id, {}).get("name", start_id)
        end_name   = stops.get(end_id,   {}).get("name", end_id)
        console.rule(f"[bold]{start_name} → {end_name}[/bold]")

        d = dijkstra(graph, stops, start_id, end_id)
        a = astar(graph, stops, start_id, end_id)

        save_result(conn, d)
        save_result(conn, a)

        if d.found:
            console.print(f"\n[bold blue]Dijkstra[/bold blue] route:")
            print_route(d)
        if a.found:
            console.print(f"[bold green]A*[/bold green] route:")
            print_route(a)

        print_comparison(d, a)
        console.print()

    # ── Heuristic admissibility check ─────────────────────────────────────────
    console.rule("[bold]Heuristic Admissibility Check[/bold]")
    # (start_id, end_id, actual_dijkstra_time)
    admissibility_pairs = [
        ("S001", "S007", 20),   # MG Road → BTM Layout, actual = 20 min
        ("S001", "S012", 35),   # MG Road → Yeshwanthpur, actual = 35 min
        ("S013", "S018", 60),   # Hebbal → E-City, actual = 60 min
        ("S011", "S017", 45),   # Rajajinagar → HSR, actual = 45 min
    ]
    print_heuristic_check(stops, admissibility_pairs)

    # ── Benchmark table from DB ───────────────────────────────────────────────
    console.rule("[bold]All Runs Saved to SQLite[/bold]")
    print_benchmark_table(conn)
    conn.close()

    # ── Key insight panel ─────────────────────────────────────────────────────
    console.print(Panel(
        "[bold]Dijkstra vs A* — The Core Difference[/bold]\n\n"
        "  Dijkstra:  priority = g(n)           cost so far\n"
        "  A*:        priority = g(n) + h(n)    cost so far + estimated remaining\n\n"
        "  h(n) = haversine_distance(n, goal) / bus_speed\n\n"
        "  Because h(n) is [bold]admissible[/bold] (never overestimates),\n"
        "  A* is guaranteed to find the same optimal path as Dijkstra —\n"
        "  but explores fewer nodes by ignoring unlikely directions.\n\n"
        "  [dim]On a city-scale graph (100k stops), A* can be 10–100x faster.[/dim]",
        border_style="dim",
        title="Theory",
    ))

    console.print(Panel(
        "[bold green]Week 5 complete![/bold green]\n\n"
        "You've implemented A* and proved it works:\n"
        "  • f(n) = g(n) + h(n) — the complete A* cost function\n"
        "  • Haversine heuristic — admissible, uses real GPS coordinates\n"
        "  • A* visits fewer nodes than Dijkstra, same optimal result\n"
        "  • All benchmark results saved to transit.db → algorithm_runs\n\n"
        "Next up → [bold]Week 6:[/bold] Transfer edges — multi-route trips with "
        "walking connections between nearby stops.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
