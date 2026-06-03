"""
Week 4 — Dijkstra's Algorithm
Transit Optimizer | Phase 1

What this script does:
  1. Loads the transit graph from data/graph.json (built in Week 3)
  2. Implements Dijkstra's algorithm FROM SCRATCH using a min-heap
  3. Finds the shortest (fastest) path between any two stops
  4. Reconstructs the full human-readable route with step-by-step directions
  5. Benchmarks the algorithm on multiple stop pairs
  6. Shows WHY Dijkstra works — what the priority queue is doing at each step

Key CS concepts covered:
  - Priority queue / min-heap (heapq)
  - Greedy algorithm design
  - Relaxation of edges
  - Path reconstruction via parent tracking
  - Time complexity: O((V + E) log V)

Run: python scripts/week4_dijkstra.py
"""

import json
import heapq
import time
from pathlib import Path
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box

console = Console()

GRAPH_PATH = Path("data/graph.json")


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class RouteResult:
    """The result of a Dijkstra search."""
    found:        bool
    start_name:   str
    end_name:     str
    total_minutes: int
    path:         list[str]          # ordered list of stop_ids
    steps:        list[dict]         # human-readable directions
    nodes_visited: int               # how much of the graph was explored
    elapsed_ms:   float


# ── Core Dijkstra implementation ─────────────────────────────────────────────
#
# The algorithm in plain English:
#   1. Start at source. Distance to source = 0, everything else = infinity.
#   2. Use a min-heap (priority queue) — always process the CHEAPEST node next.
#   3. For the current node, look at all neighbours.
#   4. If going through current node reaches a neighbour cheaper → update it.
#      (This is called "relaxing" an edge.)
#   5. Repeat until we pop the destination from the heap, or heap is empty.
#
# Why a min-heap?
#   Without it we'd scan all nodes to find the minimum each time → O(V²).
#   With heapq we get O(log V) per pop → total O((V+E) log V).

def dijkstra(graph: dict, stops: dict, start_id: str, end_id: str) -> RouteResult:
    """
    Find the shortest path from start_id to end_id using Dijkstra's algorithm.

    Args:
        graph:    adjacency list  {stop_id: {neighbour_id: {minutes, route, trips}}}
        stops:    stop metadata   {stop_id: {name, lat, lon}}
        start_id: source stop ID
        end_id:   destination stop ID

    Returns:
        RouteResult with path, steps, and performance data
    """
    t_start = time.perf_counter()

    # ── Initialisation ────────────────────────────────────────────────────────
    # dist[node] = best known travel time from start to node (minutes)
    dist = {stop: float("inf") for stop in stops}
    dist[start_id] = 0

    # parent[node] = (previous_node, route_used)  — for path reconstruction
    parent: dict[str, tuple[str, str] | None] = {stop: None for stop in stops}

    # Min-heap entries: (cost, stop_id)
    # Python's heapq is a MIN-heap — smallest cost is always at index 0
    heap = [(0, start_id)]

    visited = set()      # nodes whose shortest path is finalised
    nodes_visited = 0

    # ── Main loop ─────────────────────────────────────────────────────────────
    while heap:
        current_cost, current_node = heapq.heappop(heap)

        # Skip if we've already finalised this node
        # (stale entries remain in heap after a shorter path is found)
        if current_node in visited:
            continue
        visited.add(current_node)
        nodes_visited += 1

        # ✓ Reached destination — stop early
        if current_node == end_id:
            break

        # ── Edge relaxation ───────────────────────────────────────────────────
        for neighbour, edge in graph.get(current_node, {}).items():
            if neighbour in visited:
                continue

            new_cost = current_cost + edge["minutes"]

            # Found a cheaper path to neighbour → update and push to heap
            if new_cost < dist.get(neighbour, float("inf")):
                dist[neighbour] = new_cost
                parent[neighbour] = (current_node, edge["route"])
                heapq.heappush(heap, (new_cost, neighbour))

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    # ── Check if destination was reached ─────────────────────────────────────
    if dist.get(end_id, float("inf")) == float("inf"):
        return RouteResult(
            found=False,
            start_name=stops.get(start_id, {}).get("name", start_id),
            end_name=stops.get(end_id, {}).get("name", end_id),
            total_minutes=0,
            path=[],
            steps=[],
            nodes_visited=nodes_visited,
            elapsed_ms=elapsed_ms,
        )

    # ── Path reconstruction ───────────────────────────────────────────────────
    # Walk backwards from end → start using parent pointers
    path = []
    node = end_id
    while node is not None:
        path.append(node)
        entry = parent.get(node)
        node = entry[0] if entry else None
    path.reverse()   # now goes start → end

    # ── Build human-readable steps ────────────────────────────────────────────
    steps = []
    for i in range(len(path) - 1):
        from_id  = path[i]
        to_id    = path[i + 1]
        edge     = graph.get(from_id, {}).get(to_id, {})
        steps.append({
            "from":    stops.get(from_id, {}).get("name", from_id),
            "to":      stops.get(to_id,   {}).get("name", to_id),
            "route":   edge.get("route", "?"),
            "minutes": edge.get("minutes", 0),
        })

    return RouteResult(
        found=True,
        start_name=stops.get(start_id, {}).get("name", start_id),
        end_name=stops.get(end_id,   {}).get("name", end_id),
        total_minutes=dist[end_id],
        path=path,
        steps=steps,
        nodes_visited=nodes_visited,
        elapsed_ms=elapsed_ms,
    )


# ── Display helpers ───────────────────────────────────────────────────────────

def print_result(result: RouteResult):
    """Print a single Dijkstra result with full directions."""
    if not result.found:
        console.print(Panel(
            f"[red]No route found[/red] from [bold]{result.start_name}[/bold] "
            f"to [bold]{result.end_name}[/bold]\n"
            f"[dim]These stops may not be connected in the current graph.[/dim]",
            border_style="red",
        ))
        return

    # Header
    console.print(Panel(
        f"[bold green]Route found![/bold green]  "
        f"[bold]{result.start_name}[/bold] → [bold]{result.end_name}[/bold]\n"
        f"[cyan]Total time:[/cyan] {result.total_minutes} min   "
        f"[cyan]Stops:[/cyan] {len(result.path)}   "
        f"[cyan]Algorithm:[/cyan] Dijkstra   "
        f"[dim]({result.nodes_visited} nodes visited in {result.elapsed_ms:.3f}ms)[/dim]",
        border_style="green",
    ))

    # Step-by-step directions
    table = Table(box=box.SIMPLE, header_style="bold magenta", show_header=True)
    table.add_column("Step", justify="right", style="dim", width=5)
    table.add_column("From",          style="bold",         min_width=16)
    table.add_column("To",            style="bold",         min_width=16)
    table.add_column("Route",         justify="center",     width=8)
    table.add_column("Time",          justify="right",      width=8)
    table.add_column("Running total", justify="right",      width=14)

    running = 0
    for i, step in enumerate(result.steps, 1):
        running += step["minutes"]
        table.add_row(
            str(i),
            step["from"],
            step["to"],
            f"Rt. {step['route']}",
            f"{step['minutes']} min",
            f"{running} min",
        )

    console.print(table)


# ── Trace: show the heap step by step ────────────────────────────────────────
#
# This is the most educational part — watch Dijkstra's "thinking" live.

def dijkstra_traced(graph: dict, stops: dict, start_id: str, end_id: str, max_steps: int = 10):
    """Run Dijkstra with step-by-step heap trace for learning."""
    console.print(f"\n[bold]Heap trace:[/bold] [dim](first {max_steps} steps)[/dim]")
    console.print(f"[dim]Format: pop (cost, stop) → relax neighbours → push cheaper paths[/dim]\n")

    dist   = {stop: float("inf") for stop in stops}
    dist[start_id] = 0
    parent = {stop: None for stop in stops}
    heap   = [(0, start_id)]
    visited = set()
    step   = 0

    trace_table = Table(box=box.SIMPLE, header_style="bold cyan")
    trace_table.add_column("Step",    justify="right", width=5)
    trace_table.add_column("Popped",                   min_width=18)
    trace_table.add_column("Cost",    justify="right", width=6)
    trace_table.add_column("Relaxed neighbours")

    while heap and step < max_steps:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        step += 1

        relaxed = []
        for nb, edge in graph.get(node, {}).items():
            new_cost = cost + edge["minutes"]
            if new_cost < dist.get(nb, float("inf")):
                dist[nb] = new_cost
                parent[nb] = (node, edge["route"])
                heapq.heappush(heap, (new_cost, nb))
                nb_name = stops.get(nb, {}).get("name", nb)
                relaxed.append(f"{nb_name}={new_cost}m")

        node_name = stops.get(node, {}).get("name", node)
        done = "[green]✓ DEST[/green]" if node == end_id else ""
        trace_table.add_row(
            str(step),
            node_name,
            str(cost),
            ", ".join(relaxed) if relaxed else "[dim]terminal[/dim]",
        )
        if node == end_id:
            break

    console.print(trace_table)


# ── Benchmark multiple routes ─────────────────────────────────────────────────

def benchmark(graph: dict, stops: dict, pairs: list[tuple[str, str]]):
    """Run Dijkstra on multiple stop pairs and show a comparison table."""
    table = Table(
        title="Route Benchmark",
        box=box.ROUNDED,
        header_style="bold blue",
    )
    table.add_column("From",            min_width=14)
    table.add_column("To",              min_width=14)
    table.add_column("Time",            justify="right", width=8)
    table.add_column("Stops",           justify="right", width=7)
    table.add_column("Nodes visited",   justify="right", width=14)
    table.add_column("Speed",           justify="right", width=10)

    for start_id, end_id in pairs:
        r = dijkstra(graph, stops, start_id, end_id)
        if r.found:
            table.add_row(
                r.start_name,
                r.end_name,
                f"{r.total_minutes} min",
                str(len(r.path)),
                str(r.nodes_visited),
                f"{r.elapsed_ms:.3f}ms",
            )
        else:
            table.add_row(
                stops.get(start_id, {}).get("name", start_id),
                stops.get(end_id,   {}).get("name", end_id),
                "[red]no route[/red]", "-", "-", "-",
            )

    console.print(table)


# ── Find all reachable stops with distances ───────────────────────────────────

def all_distances(graph: dict, stops: dict, start_id: str):
    """Run Dijkstra once to find travel time from start to ALL stops."""
    dist   = {stop: float("inf") for stop in stops}
    dist[start_id] = 0
    heap   = [(0, start_id)]
    visited = set()

    while heap:
        cost, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        for nb, edge in graph.get(node, {}).items():
            new_cost = cost + edge["minutes"]
            if new_cost < dist.get(nb, float("inf")):
                dist[nb] = new_cost
                heapq.heappush(heap, (new_cost, nb))

    # Return reachable stops sorted by distance
    reachable = [
        (stop_id, d, stops.get(stop_id, {}).get("name", stop_id))
        for stop_id, d in dist.items()
        if d < float("inf") and stop_id != start_id
    ]
    return sorted(reachable, key=lambda x: x[1])


def print_all_distances(graph: dict, stops: dict, start_id: str):
    """Show travel times from one stop to all others."""
    start_name = stops.get(start_id, {}).get("name", start_id)
    reachable = all_distances(graph, stops, start_id)

    table = Table(
        title=f"All reachable stops from {start_name}",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("Stop")
    table.add_column("Travel time", justify="right")
    table.add_column("Bar")

    for stop_id, mins, name in reachable:
        bar_len = min(int(mins * 1.5), 30)
        bar = "█" * bar_len
        table.add_row(name, f"{mins} min", f"[cyan]{bar}[/cyan]")

    console.print(table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 4: Dijkstra's Algorithm\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Load graph
    console.print(f"\n[bold]Loading graph from {GRAPH_PATH}...[/bold]")
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    graph = data["graph"]
    stops = data["stops"]
    console.print(f"[green]✓[/green] Graph loaded: {len(stops)} stops, "
                  f"{sum(len(v) for v in graph.values())} edges\n")

    # ── Demo 1: Single route with full trace ──────────────────────────────────
    console.rule("[bold]Demo 1 — MG Road → BTM Layout[/bold]")
    result = dijkstra(graph, stops, "S001", "S007")
    print_result(result)
    dijkstra_traced(graph, stops, "S001", "S007")

    # ── Demo 2: Another route ─────────────────────────────────────────────────
    console.rule("[bold]Demo 2 — Indiranagar → Majestic[/bold]")
    result2 = dijkstra(graph, stops, "S004", "S010")
    print_result(result2)

    # ── Demo 3: No route (isolated stop) ─────────────────────────────────────
    console.rule("[bold]Demo 3 — Rajajinagar → Whitefield (isolated stop)[/bold]")
    result3 = dijkstra(graph, stops, "S011", "S015")
    print_result(result3)

    # ── Demo 4: All distances from MG Road ────────────────────────────────────
    console.rule("[bold]Demo 4 — All reachable stops from MG Road[/bold]")
    print_all_distances(graph, stops, "S001")

    # ── Demo 5: Benchmark 5 routes ───────────────────────────────────────────
    console.rule("[bold]Demo 5 — Benchmark: 5 routes[/bold]")
    benchmark(graph, stops, [
        ("S001", "S007"),   # MG Road → BTM Layout
        ("S001", "S012"),   # MG Road → Yeshwanthpur
        ("S004", "S010"),   # Indiranagar → Majestic
        ("S013", "S018"),   # Hebbal → Electronic City
        ("S011", "S017"),   # Rajajinagar → HSR Layout
    ])

    # ── Complexity reminder ───────────────────────────────────────────────────
    console.print(Panel(
        "[bold]Why is Dijkstra O((V+E) log V)?[/bold]\n\n"
        "  • Each node is popped from the heap once          → O(V log V)\n"
        "  • Each edge causes at most one heap push           → O(E log V)\n"
        "  • Total: O((V + E) log V)\n\n"
        "  For our graph: V=20, E=30  →  negligible.\n"
        "  For Delhi Metro: V=256, E≈600  →  still under 1ms.\n"
        "  For all India roads: V=10M, E=25M  →  ~2 seconds.\n\n"
        "  [dim]A* (Week 5) reduces nodes visited further using a heuristic.[/dim]",
        title="Complexity",
        border_style="dim",
    ))

    console.print(Panel(
        "[bold green]Week 4 complete![/bold green]\n\n"
        "You've implemented Dijkstra's algorithm from scratch:\n"
        "  • Min-heap (heapq) for O(log V) priority queue operations\n"
        "  • Edge relaxation — the core insight of the algorithm\n"
        "  • Parent tracking for full path reconstruction\n"
        "  • Early termination once destination is reached\n"
        "  • Benchmarked across multiple real stop pairs\n\n"
        "Next up → [bold]Week 5:[/bold] A* algorithm with Haversine heuristic.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
