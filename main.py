"""
main.py — Transit Optimizer CLI
Week 7–8 | Phase 1 | SmartCity Project

Usage examples:
  python main.py --from "MG Road" --to "HSR Layout"
  python main.py --from "MG Road" --to "HSR Layout" --algorithm dijkstra
  python main.py --from "MG Road" --to "HSR Layout" --no-transfers
  python main.py --list-stops
  python main.py --list-stops --filter "road"
  python main.py --stats

What this file does:
  1. Parses CLI arguments with click (argparse alternative, cleaner syntax)
  2. Loads graph_with_transfers.json (built in Week 6)
  3. Fuzzy-matches stop names so users don't need exact IDs
  4. Runs Dijkstra or A* based on --algorithm flag
  5. Prints beautiful rich terminal output with directions
  6. Logs every query to logs/queries.log (OS file I/O concept)

Key CS concepts covered:
  - CLI design with click
  - Fuzzy string matching
  - File I/O and logging
  - Modular code organisation (router.py imported here)
"""

import click
import json
import logging
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box

# Import our own modules
from scripts.router import find_route, build_directions
from scripts.search  import fuzzy_find_stop

console = Console()

GRAPH_PATH       = Path("data/graph_with_transfers.json")
GRAPH_NOTRANS    = Path("data/graph.json")
LOG_PATH         = Path("logs/queries.log")

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_graph(use_transfers: bool) -> dict:
    path = GRAPH_PATH if use_transfers else GRAPH_NOTRANS
    if not path.exists():
        console.print(f"[red]Graph file not found:[/red] {path}")
        console.print("[dim]Run: python scripts/week3_graph.py  and  python scripts/week6_transfers.py[/dim]")
        raise SystemExit(1)
    with open(path) as f:
        return json.load(f)


def print_directions(directions: list, total_min: float, start: str, end: str,
                     algorithm: str, nodes_visited: int, elapsed_ms: float):
    """Render the full route with rich formatting."""

    # ── Header ────────────────────────────────────────────────────────────────
    transfers = sum(1 for d in directions if d["type"] == "walk")
    segments  = len(directions)

    console.print()
    console.print(Panel(
        f"  [bold white]{start}[/bold white]  [dim]→[/dim]  [bold white]{end}[/bold white]\n\n"
        f"  [cyan]Total time:[/cyan]  [bold]{total_min:.0f} min[/bold]   "
        f"[cyan]Segments:[/cyan] {segments}   "
        f"[cyan]Transfers:[/cyan] {transfers}\n"
        f"  [dim]Algorithm: {algorithm.upper()}  |  "
        f"{nodes_visited} nodes visited  |  {elapsed_ms:.3f}ms[/dim]",
        border_style="blue",
        padding=(0, 1),
    ))

    # ── Step-by-step directions ───────────────────────────────────────────────
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("icon",    width=3)
    table.add_column("action",  min_width=42)
    table.add_column("time",    justify="right", width=7, style="dim")
    table.add_column("total",   justify="right", width=8)

    running = 0
    for i, d in enumerate(directions):
        running += d["minutes"]
        if d["type"] == "walk":
            icon   = "🚶"
            dist_m = int(d.get("dist_km", 0) * 1000)
            action = (f"[yellow]Walk[/yellow]  "
                      f"[bold]{d['from']}[/bold] → [bold]{d['to']}[/bold]"
                      f"  [dim]{dist_m}m[/dim]")
        else:
            icon   = "🚌"
            stops  = d.get("stops", 1)
            action = (f"[blue]Route {d['route']:>3}[/blue]  "
                      f"[bold]{d['from']}[/bold] → [bold]{d['to']}[/bold]"
                      f"  [dim]{stops} stop{'s' if stops != 1 else ''}[/dim]")

        table.add_row(
            icon,
            action,
            f"{d['minutes']:.0f}m",
            f"[bold]{running:.0f}m[/bold]",
        )

        # Separator after walk legs (boarding a new vehicle)
        if d["type"] == "walk" and i < len(directions) - 1:
            table.add_row("", "[dim]─────────────────────────────────────────[/dim]", "", "")

    console.print(table)
    console.print()


def print_no_route(start: str, end: str):
    console.print(Panel(
        f"[red]No route found[/red] from [bold]{start}[/bold] to [bold]{end}[/bold]\n\n"
        "[dim]These stops may not be connected in the current graph.\n"
        "Try --no-transfers to check base connectivity, or --list-stops to verify stop names.[/dim]",
        border_style="red",
    ))


def log_query(frm: str, to: str, algorithm: str, found: bool,
              total_min: float, elapsed_ms: float):
    status = f"{total_min:.0f}min" if found else "NO_ROUTE"
    logging.info(f"from={frm!r:20} to={to!r:20} algo={algorithm} "
                 f"result={status} speed={elapsed_ms:.3f}ms")


# ── CLI commands ──────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--from",    "from_stop",  default=None, help="Origin stop name")
@click.option("--to",      "to_stop",    default=None, help="Destination stop name")
@click.option("--algorithm", default="astar",
              type=click.Choice(["astar", "dijkstra"], case_sensitive=False),
              help="Routing algorithm (default: astar)")
@click.option("--no-transfers", is_flag=True, default=False,
              help="Disable walking transfer edges")
@click.option("--list-stops",   is_flag=True, default=False,
              help="List all available stops")
@click.option("--filter",  "name_filter", default=None,
              help="Filter stop list by keyword")
@click.option("--stats",   is_flag=True, default=False,
              help="Show graph statistics")
def cli(ctx, from_stop, to_stop, algorithm, no_transfers,
        list_stops, name_filter, stats):
    """
    Transit Optimizer — fastest route between any two bus/metro stops.

    \b
    Examples:
      python main.py --from "MG Road" --to "HSR Layout"
      python main.py --from "majestic" --to "silk board" --algorithm dijkstra
      python main.py --list-stops --filter "metro"
      python main.py --stats
    """

    data = load_graph(use_transfers=not no_transfers)
    graph = data["graph"]
    stops = data["stops"]

    # ── --stats ───────────────────────────────────────────────────────────────
    if stats:
        n_transit = sum(
            1 for nbrs in graph.values()
            for e in nbrs.values() if e.get("route") != "WALK"
        )
        n_walk = sum(
            1 for nbrs in graph.values()
            for e in nbrs.values() if e.get("route") == "WALK"
        )
        t = Table(title="Graph Stats", box=box.ROUNDED, header_style="bold cyan")
        t.add_column("Metric")
        t.add_column("Value", justify="right", style="bold")
        t.add_row("Total stops",       str(len(stops)))
        t.add_row("Transit edges",     str(n_transit))
        t.add_row("Walk edges",        str(n_walk))
        t.add_row("Total edges",       str(n_transit + n_walk))
        t.add_row("Transfers enabled", "No" if no_transfers else "Yes")
        t.add_row("Log file",          str(LOG_PATH))
        console.print(t)
        return

    # ── --list-stops ──────────────────────────────────────────────────────────
    if list_stops:
        t = Table(title="Available Stops", box=box.ROUNDED, header_style="bold green")
        t.add_column("ID",   style="dim", width=6)
        t.add_column("Name", style="bold")
        t.add_column("Lat",  justify="right", style="dim")
        t.add_column("Lon",  justify="right", style="dim")

        for sid, s in sorted(stops.items(), key=lambda x: x[1]["name"]):
            name = s["name"]
            if name_filter and name_filter.lower() not in name.lower():
                continue
            t.add_row(sid, name, str(s["lat"]), str(s["lon"]))
        console.print(t)
        return

    # ── --from / --to routing ─────────────────────────────────────────────────
    if not from_stop or not to_stop:
        console.print(ctx.get_help())
        return

    # Fuzzy match stop names
    start_id, start_name, start_score = fuzzy_find_stop(from_stop, stops)
    end_id,   end_name,   end_score   = fuzzy_find_stop(to_stop,   stops)

    if not start_id:
        console.print(f"[red]Stop not found:[/red] '{from_stop}'")
        console.print("[dim]Use --list-stops to see all available stops.[/dim]")
        return
    if not end_id:
        console.print(f"[red]Stop not found:[/red] '{to_stop}'")
        console.print("[dim]Use --list-stops to see all available stops.[/dim]")
        return

    # Warn if fuzzy match wasn't confident
    if start_score < 90:
        console.print(f"[dim]Matched '[yellow]{from_stop}[/yellow]' → '{start_name}'[/dim]")
    if end_score < 90:
        console.print(f"[dim]Matched '[yellow]{to_stop}[/yellow]' → '{end_name}'[/dim]")

    if start_id == end_id:
        console.print(f"[yellow]Start and destination are the same stop:[/yellow] {start_name}")
        return

    # Run router
    result = find_route(graph, stops, start_id, end_id, algorithm)

    # Log the query
    log_query(start_name, end_name, algorithm,
              result["found"],
              result.get("total_minutes", 0),
              result["elapsed_ms"])

    if not result["found"]:
        print_no_route(start_name, end_name)
        return

    directions = build_directions(result, stops)
    print_directions(
        directions,
        result["total_minutes"],
        start_name, end_name,
        algorithm,
        result["nodes_visited"],
        result["elapsed_ms"],
    )


if __name__ == "__main__":
    cli()
