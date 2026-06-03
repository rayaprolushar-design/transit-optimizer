"""
Week 3 — Transit Graph Builder
Transit Optimizer | Phase 1

What this script does:
  1. Reads stop_times from transit.db
  2. Builds a weighted directed graph (adjacency list)
     - Nodes  = bus stops (stop_id)
     - Edges  = direct connections between consecutive stops on a trip
     - Weight = travel time in minutes
  3. Computes graph statistics (nodes, edges, degree distribution)
  4. Finds neighbours of any stop
  5. Detects isolated stops and strongly connected components
  6. Saves the graph to data/graph.json for use in Week 4 (Dijkstra)

Key CS concepts covered:
  - Graph representation (adjacency list vs matrix)
  - Directed vs undirected graphs
  - Edge weights
  - Degree of a node (in-degree, out-degree)
  - BFS for reachability

Run: python scripts/week3_graph.py
"""

import sqlite3
import json
import math
import time
from pathlib import Path
from collections import defaultdict, deque
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import box

console = Console()

DB_PATH    = Path("data/transit.db")
GRAPH_PATH = Path("data/graph.json")


# ── Helper: parse "HH:MM:SS" → total minutes ────────────────────────────────

def time_to_minutes(t: str) -> int:
    """Convert GTFS time string to minutes since midnight.
    
    GTFS allows times past midnight e.g. '25:30:00' for next-day trips.
    """
    parts = t.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 60 + m + s // 60


# ── Helper: Haversine distance ────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points in kilometres.
    
    Used later for A* heuristic and transfer edge detection.
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── 1. Load stop metadata from DB ────────────────────────────────────────────

def load_stops(conn: sqlite3.Connection) -> dict:
    """Return {stop_id: {name, lat, lon}} for all stops."""
    rows = conn.execute(
        "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops"
    ).fetchall()
    return {
        row[0]: {"name": row[1], "lat": float(row[2]), "lon": float(row[3])}
        for row in rows
    }


# ── 2. Load trip sequences from DB ───────────────────────────────────────────

def load_trip_sequences(conn: sqlite3.Connection) -> dict:
    """Return {trip_id: [(stop_id, arrival_minutes), ...]} sorted by sequence."""
    rows = conn.execute("""
        SELECT   st.trip_id,
                 st.stop_id,
                 st.arrival_time,
                 st.stop_sequence,
                 r.route_short_name
        FROM     stop_times st
        JOIN     trips      t  ON t.trip_id  = st.trip_id
        JOIN     routes     r  ON r.route_id = t.route_id
        ORDER BY st.trip_id, st.stop_sequence
    """).fetchall()

    trips = defaultdict(list)
    for trip_id, stop_id, arrival_time, seq, route_name in rows:
        trips[trip_id].append({
            "stop_id":  stop_id,
            "arrival":  time_to_minutes(arrival_time),
            "sequence": int(seq),
            "route":    route_name,
        })
    return dict(trips)


# ── 3. Build the graph ────────────────────────────────────────────────────────
#
# Graph structure (adjacency list):
#   graph[stop_a][stop_b] = {
#       "minutes":    travel time in minutes (edge weight),
#       "route":      route short name (e.g. "5"),
#       "trips":      how many trips use this edge (frequency),
#   }
#
# Why adjacency list and not adjacency matrix?
#   - Transit graphs are SPARSE: 1000 stops but only ~3000 edges
#   - Matrix would be 1000×1000 = 1,000,000 cells, mostly empty
#   - Adjacency list uses only O(V + E) space

def build_graph(trips: dict, stops: dict) -> dict:
    """Build weighted directed adjacency list from trip sequences."""

    # graph[from_stop][to_stop] = edge data
    graph: dict[str, dict[str, dict]] = defaultdict(dict)

    for trip_id, sequence in trips.items():
        # Walk consecutive stop pairs in this trip
        for i in range(len(sequence) - 1):
            a = sequence[i]
            b = sequence[i + 1]

            from_stop = a["stop_id"]
            to_stop   = b["stop_id"]
            travel_min = b["arrival"] - a["arrival"]

            # Edge already exists — keep minimum travel time, increment frequency
            if to_stop in graph[from_stop]:
                existing = graph[from_stop][to_stop]
                existing["minutes"] = min(existing["minutes"], travel_min)
                existing["trips"]  += 1
            else:
                graph[from_stop][to_stop] = {
                    "minutes": max(travel_min, 1),  # floor at 1 min
                    "route":   a["route"],
                    "trips":   1,
                }

    return dict(graph)


# ── 4. Graph statistics ───────────────────────────────────────────────────────

def compute_stats(graph: dict, stops: dict) -> dict:
    """Compute key graph metrics."""
    all_nodes  = set(stops.keys())
    graph_nodes = set(graph.keys())

    # Collect all edges
    edges = []
    for src, neighbours in graph.items():
        for dst, data in neighbours.items():
            edges.append((src, dst, data["minutes"]))

    # Degree (out-degree per node)
    out_degrees = {node: len(neighbours) for node, neighbours in graph.items()}

    # In-degree
    in_deg: dict[str, int] = defaultdict(int)
    for neighbours in graph.values():
        for dst in neighbours:
            in_deg[dst] += 1

    # Edge weight stats
    weights = [e[2] for e in edges]
    avg_weight = sum(weights) / len(weights) if weights else 0
    min_weight = min(weights) if weights else 0
    max_weight = max(weights) if weights else 0

    # Isolated nodes (in stops table but no edges)
    isolated = all_nodes - graph_nodes

    return {
        "total_stops":    len(all_nodes),
        "graph_nodes":    len(graph_nodes),
        "total_edges":    len(edges),
        "isolated_stops": list(isolated),
        "avg_out_degree": sum(out_degrees.values()) / len(out_degrees) if out_degrees else 0,
        "max_out_degree": max(out_degrees.values()) if out_degrees else 0,
        "avg_travel_min": round(avg_weight, 1),
        "min_travel_min": min_weight,
        "max_travel_min": max_weight,
        "out_degrees":    out_degrees,
        "in_degrees":     dict(in_deg),
    }


def print_stats(stats: dict, stops: dict):
    """Display graph stats as rich tables."""

    # Summary panel
    t = Table(title="Graph Statistics", box=box.ROUNDED, header_style="bold cyan")
    t.add_column("Metric")
    t.add_column("Value", justify="right", style="bold")

    t.add_row("Total stops (nodes)",    str(stats["total_stops"]))
    t.add_row("Stops in graph",         str(stats["graph_nodes"]))
    t.add_row("Connections (edges)",    str(stats["total_edges"]))
    t.add_row("Avg out-degree",         f"{stats['avg_out_degree']:.1f}")
    t.add_row("Max out-degree",         str(stats["max_out_degree"]))
    t.add_row("Avg travel time",        f"{stats['avg_travel_min']} min")
    t.add_row("Shortest edge",          f"{stats['min_travel_min']} min")
    t.add_row("Longest edge",           f"{stats['max_travel_min']} min")
    t.add_row("Isolated stops",         str(len(stats["isolated_stops"])))
    console.print(t)

    # Top 5 most connected stops
    top = sorted(stats["out_degrees"].items(), key=lambda x: x[1], reverse=True)[:5]
    hub_table = Table(title="Top 5 Hub Stops (highest out-degree)", box=box.ROUNDED, header_style="bold green")
    hub_table.add_column("Stop")
    hub_table.add_column("Outgoing connections", justify="right")
    hub_table.add_column("Incoming connections", justify="right")

    for stop_id, out_deg in top:
        name    = stops[stop_id]["name"] if stop_id in stops else stop_id
        in_deg  = stats["in_degrees"].get(stop_id, 0)
        hub_table.add_row(name, str(out_deg), str(in_deg))

    console.print(hub_table)

    # Isolated stops (no outgoing edges)
    if stats["isolated_stops"]:
        iso_table = Table(title="Isolated Stops (no outgoing edges)", box=box.ROUNDED, header_style="bold red")
        iso_table.add_column("Stop ID")
        iso_table.add_column("Name")
        for sid in stats["isolated_stops"]:
            iso_table.add_row(sid, stops.get(sid, {}).get("name", "?"))
        console.print(iso_table)
    else:
        console.print("[green]✓ No isolated stops — all stops have outgoing connections[/green]")


# ── 5. Show neighbours of a stop ──────────────────────────────────────────────

def print_neighbours(graph: dict, stops: dict, stop_id: str):
    """Show all direct connections from a given stop."""
    if stop_id not in graph:
        console.print(f"[red]Stop {stop_id} has no outgoing edges[/red]")
        return

    stop_name = stops.get(stop_id, {}).get("name", stop_id)
    neighbours = graph[stop_id]

    t = Table(
        title=f"Neighbours of '{stop_name}' ({stop_id})",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    t.add_column("To Stop")
    t.add_column("Route", justify="center")
    t.add_column("Travel time", justify="right")
    t.add_column("Frequency",  justify="right")

    for dst, data in sorted(neighbours.items(), key=lambda x: x[1]["minutes"]):
        dst_name = stops.get(dst, {}).get("name", dst)
        t.add_row(dst_name, data["route"], f"{data['minutes']} min", f"{data['trips']} trips")

    console.print(t)


# ── 6. BFS reachability ───────────────────────────────────────────────────────

def bfs_reachable(graph: dict, stops: dict, start_id: str) -> list[str]:
    """BFS from a start stop — returns all reachable stop IDs.
    
    This answers: 'Which stops can I reach from here at all?'
    Dijkstra answers: 'What is the FASTEST way to reach each stop?'
    """
    visited = set()
    queue   = deque([start_id])
    visited.add(start_id)

    while queue:
        node = queue.popleft()
        for neighbour in graph.get(node, {}):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

    return list(visited)


def print_reachability(graph: dict, stops: dict, start_id: str):
    """Show BFS reachability from a start stop."""
    start_name = stops.get(start_id, {}).get("name", start_id)

    t_start = time.perf_counter()
    reachable = bfs_reachable(graph, stops, start_id)
    elapsed   = (time.perf_counter() - t_start) * 1000

    total = len(stops)
    pct   = len(reachable) / total * 100

    console.print(
        f"\nFrom [bold]{start_name}[/bold]: "
        f"can reach [bold green]{len(reachable)}[/bold green] / {total} stops "
        f"({pct:.0f}%) in [dim]{elapsed:.2f}ms[/dim]"
    )

    # Show a sample of reachable stops
    sample = [stops[s]["name"] for s in reachable if s != start_id][:8]
    console.print(f"[dim]Sample: {', '.join(sample)}...[/dim]")


# ── 7. Save graph to JSON ─────────────────────────────────────────────────────

def save_graph(graph: dict, stops: dict):
    """Persist graph and stop metadata to disk for Week 4 (Dijkstra)."""
    payload = {
        "stops": stops,
        "graph": graph,
    }
    with open(GRAPH_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    size_kb = GRAPH_PATH.stat().st_size / 1024
    console.print(f"[green]✓[/green] Graph saved to [bold]{GRAPH_PATH}[/bold] ({size_kb:.1f} KB)")


# ── 8. Visualise a small subgraph ─────────────────────────────────────────────

def print_adjacency_sample(graph: dict, stops: dict, n: int = 4):
    """Print the adjacency list for the first n nodes, textually."""
    console.print(f"\n[bold]Adjacency list (first {n} nodes):[/bold]")
    console.print("[dim]Format: stop → [neighbour (Xmin via RouteY), ...][/dim]\n")

    for stop_id in list(graph.keys())[:n]:
        name = stops.get(stop_id, {}).get("name", stop_id)
        edges = []
        for dst, data in graph[stop_id].items():
            dst_name = stops.get(dst, {}).get("name", dst)
            edges.append(f"[cyan]{dst_name}[/cyan] [dim]({data['minutes']}min via Rt.{data['route']})[/dim]")
        console.print(f"  [bold]{name}[/bold] → {', '.join(edges)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 3: Graph Builder\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Connect to DB
    conn = sqlite3.connect(DB_PATH)
    console.print(f"\n[green]✓[/green] Connected to [bold]{DB_PATH}[/bold]")

    # Step 1: load data
    console.rule("[bold]Step 1 — Load stop metadata[/bold]")
    stops = load_stops(conn)
    console.print(f"[green]✓[/green] Loaded [bold]{len(stops)}[/bold] stops")

    console.rule("[bold]Step 2 — Load trip sequences[/bold]")
    trips = load_trip_sequences(conn)
    console.print(f"[green]✓[/green] Loaded [bold]{len(trips)}[/bold] trips")
    conn.close()

    # Step 2: build graph
    console.rule("[bold]Step 3 — Build adjacency list[/bold]")
    t0    = time.perf_counter()
    graph = build_graph(trips, stops)
    elapsed = (time.perf_counter() - t0) * 1000

    total_edges = sum(len(v) for v in graph.values())
    console.print(
        f"[green]✓[/green] Graph built in [bold]{elapsed:.1f}ms[/bold] — "
        f"[bold]{len(graph)}[/bold] nodes, [bold]{total_edges}[/bold] edges"
    )

    # Step 3: show adjacency sample
    console.rule("[bold]Step 4 — Adjacency list preview[/bold]")
    print_adjacency_sample(graph, stops)

    # Step 4: stats
    console.rule("[bold]Step 5 — Graph statistics[/bold]")
    stats = compute_stats(graph, stops)
    print_stats(stats, stops)

    # Step 5: neighbours of a specific stop
    console.rule("[bold]Step 6 — Neighbours of MG Road (S001)[/bold]")
    print_neighbours(graph, stops, "S001")

    # Step 6: BFS reachability
    console.rule("[bold]Step 7 — BFS reachability from MG Road[/bold]")
    print_reachability(graph, stops, "S001")

    console.print()
    console.rule("[bold]Step 8 — BFS reachability from Whitefield[/bold]")
    print_reachability(graph, stops, "S015")

    # Step 7: save
    console.rule("[bold]Step 9 — Save graph[/bold]")
    save_graph(graph, stops)

    console.print(Panel(
        "[bold green]Week 3 complete![/bold green]\n\n"
        "You've built a real weighted directed graph from transit data:\n"
        "  • Nodes  = bus stops loaded from SQLite\n"
        "  • Edges  = travel times between consecutive stops\n"
        "  • Weights = minutes of travel\n"
        "  • BFS confirms which stops are reachable from any start\n\n"
        "Graph saved to [bold]data/graph.json[/bold]\n\n"
        "Next up → [bold]Week 4:[/bold] Dijkstra's algorithm on this graph.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
