"""
Week 1 — GTFS Data Explorer
Transit Optimizer | Phase 1

What this script does:
  - Loads all GTFS files (stops, routes, trips, stop_times)
  - Prints stats about the transit network
  - Shows sample data from each file
  - Gives you a feel for the data before we build the graph

Run: python scripts/week1_explore.py
"""

import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text

console = Console()

GTFS_PATH = Path("data/gtfs")


# ── 1. Load all GTFS files ──────────────────────────────────────────────────

def load_gtfs(path: Path) -> dict:
    """Load all GTFS CSV files into pandas DataFrames."""
    files = {
        "stops":      "stops.txt",
        "routes":     "routes.txt",
        "trips":      "trips.txt",
        "stop_times": "stop_times.txt",
    }
    data = {}
    for key, filename in files.items():
        filepath = path / filename
        if filepath.exists():
            data[key] = pd.read_csv(filepath, dtype=str)
            # Strip whitespace from all string columns
            data[key] = data[key].apply(lambda col: col.str.strip() if col.dtype == "object" else col)
        else:
            console.print(f"[red]Missing file:[/red] {filename}")
    return data


# ── 2. Print network summary ─────────────────────────────────────────────────

def print_summary(data: dict):
    """Print a high-level overview of the transit network."""
    stops      = data["stops"]
    routes     = data["routes"]
    trips      = data["trips"]
    stop_times = data["stop_times"]

    # Stat cards
    stats = [
        Panel(f"[bold blue]{len(stops)}[/bold blue]\n[dim]Total Stops[/dim]",       expand=True),
        Panel(f"[bold green]{len(routes)}[/bold green]\n[dim]Routes[/dim]",          expand=True),
        Panel(f"[bold yellow]{len(trips)}[/bold yellow]\n[dim]Trips[/dim]",          expand=True),
        Panel(f"[bold magenta]{len(stop_times)}[/bold magenta]\n[dim]Stop Events[/dim]", expand=True),
    ]
    console.print(Columns(stats))


# ── 3. Show stops table ───────────────────────────────────────────────────────

def print_stops(stops: pd.DataFrame, n: int = 8):
    """Display the first n stops in a formatted table."""
    table = Table(title="Sample Stops", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Stop ID",   style="dim")
    table.add_column("Name",      style="bold")
    table.add_column("Latitude",  justify="right")
    table.add_column("Longitude", justify="right")

    for _, row in stops.head(n).iterrows():
        table.add_row(
            row["stop_id"],
            row["stop_name"],
            row["stop_lat"],
            row["stop_lon"],
        )
    console.print(table)


# ── 4. Show routes table ──────────────────────────────────────────────────────

def print_routes(routes: pd.DataFrame):
    """Display all routes."""
    table = Table(title="All Routes", box=box.ROUNDED, header_style="bold green")
    table.add_column("Route ID", style="dim")
    table.add_column("Number",   style="bold yellow")
    table.add_column("Name",     style="bold")
    table.add_column("Type",     justify="center")

    type_map = {"0": "Tram", "1": "Metro", "2": "Rail", "3": "Bus", "4": "Ferry"}

    for _, row in routes.iterrows():
        rtype = type_map.get(str(row["route_type"]), "Unknown")
        table.add_row(
            row["route_id"],
            row["route_short_name"],
            row["route_long_name"],
            rtype,
        )
    console.print(table)


# ── 5. Show a single route's stop sequence ────────────────────────────────────

def print_route_stops(data: dict, route_id: str):
    """Show the ordered stops for a specific route."""
    trips      = data["trips"]
    stop_times = data["stop_times"]
    stops      = data["stops"]
    routes     = data["routes"]

    # Get route name
    route_row = routes[routes["route_id"] == route_id]
    if route_row.empty:
        console.print(f"[red]Route {route_id} not found[/red]")
        return
    route_name = route_row.iloc[0]["route_long_name"]
    route_num  = route_row.iloc[0]["route_short_name"]

    # Get one trip for this route
    route_trips = trips[trips["route_id"] == route_id]
    if route_trips.empty:
        return
    trip_id = route_trips.iloc[0]["trip_id"]

    # Get stop sequence for that trip
    sequence = stop_times[stop_times["trip_id"] == trip_id].sort_values("stop_sequence")
    sequence = sequence.merge(stops[["stop_id", "stop_name"]], on="stop_id")

    table = Table(
        title=f"Route {route_num}: {route_name}",
        box=box.SIMPLE_HEAVY,
        header_style="bold magenta",
    )
    table.add_column("#",           justify="right", style="dim")
    table.add_column("Stop",        style="bold")
    table.add_column("Arrival",     justify="right")
    table.add_column("Departure",   justify="right")

    for _, row in sequence.iterrows():
        table.add_row(
            str(row["stop_sequence"]),
            row["stop_name"],
            row["arrival_time"],
            row["departure_time"],
        )
    console.print(table)


# ── 6. Fun facts about the network ───────────────────────────────────────────

def print_fun_facts(data: dict):
    """Compute interesting stats about the network."""
    stops      = data["stops"]
    stop_times = data["stop_times"]
    trips      = data["trips"]
    routes     = data["routes"]

    # Most visited stop
    visits = stop_times["stop_id"].value_counts()
    top_stop_id = visits.idxmax()
    top_stop_name = stops[stops["stop_id"] == top_stop_id]["stop_name"].values[0]
    top_count = visits.max()

    # Average stops per trip
    avg_stops = stop_times.groupby("trip_id").size().mean()

    # Trips per route
    trips_per_route = trips.groupby("route_id").size()
    busiest_route_id = trips_per_route.idxmax()
    busiest_route_name = routes[routes["route_id"] == busiest_route_id]["route_short_name"].values[0]

    facts = Table(title="Network Insights", box=box.ROUNDED, header_style="bold yellow")
    facts.add_column("Insight",  style="bold")
    facts.add_column("Value",    style="cyan")

    facts.add_row("Most visited stop",     f"{top_stop_name} ({top_count} events)")
    facts.add_row("Avg stops per trip",    f"{avg_stops:.1f}")
    facts.add_row("Busiest route",         f"Route {busiest_route_name}")
    facts.add_row("Unique stops served",   str(stop_times["stop_id"].nunique()))
    facts.add_row("Total stop events",     str(len(stop_times)))

    console.print(facts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 1: GTFS Explorer\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Load data
    console.print("\n[bold]Loading GTFS files...[/bold]")
    data = load_gtfs(GTFS_PATH)

    if not data:
        console.print("[red]No GTFS data found. Check data/gtfs/ folder.[/red]")
        return

    console.print(f"[green]✓ Loaded {len(data)} GTFS files[/green]\n")

    # Summary
    console.rule("[bold]Network Summary[/bold]")
    print_summary(data)

    # Stops
    console.rule("[bold]Stops (first 8)[/bold]")
    print_stops(data["stops"])

    # Routes
    console.rule("[bold]Routes[/bold]")
    print_routes(data["routes"])

    # One route drill-down
    console.rule("[bold]Sample Route Detail — Route R001[/bold]")
    print_route_stops(data, "R001")

    # Fun facts
    console.rule("[bold]Network Insights[/bold]")
    print_fun_facts(data)

    console.print(Panel(
        "[bold green]Week 1 complete![/bold green]\n\n"
        "You've loaded and explored real GTFS transit data.\n"
        "Next up → [bold]Week 2:[/bold] Load this into SQLite and write SQL queries.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
