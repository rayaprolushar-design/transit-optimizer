"""
Week 2 — SQLite Database Layer
Transit Optimizer | Phase 1

What this script does:
  1. Designs and creates a proper SQL schema (stops, routes, trips, stop_times)
  2. Loads all GTFS CSV data into SQLite with validation
  3. Creates indexes for fast lookups
  4. Runs 6 real SQL queries to explore the data
  5. Shows query execution time (so you see WHY indexes matter)

Run: python scripts/week2_database.py
"""

import sqlite3
import csv
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box

console = Console()

GTFS_PATH  = Path("data/gtfs")
DB_PATH    = Path("data/transit.db")


# ── 1. Schema Definition ────────────────────────────────────────────────────
#
# This is exactly what you'd learn in a DBMS course:
#   - Primary keys on every table
#   - Foreign keys to enforce relationships
#   - Correct data types (TEXT for IDs, REAL for coordinates, INTEGER for sequences)

SCHEMA_SQL = """
-- Drop tables if re-running (order matters due to foreign keys)
DROP TABLE IF EXISTS stop_times;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS routes;
DROP TABLE IF EXISTS stops;

-- Stops: every physical bus/metro stop
CREATE TABLE stops (
    stop_id    TEXT PRIMARY KEY,
    stop_name  TEXT NOT NULL,
    stop_lat   REAL NOT NULL,
    stop_lon   REAL NOT NULL
);

-- Routes: a named service (e.g. Route 5, MG Road to Yeshwanthpur)
CREATE TABLE routes (
    route_id         TEXT PRIMARY KEY,
    route_short_name TEXT NOT NULL,
    route_long_name  TEXT,
    route_type       INTEGER NOT NULL   -- 3 = Bus, 1 = Metro, 2 = Rail
);

-- Trips: one run of a route at a specific time
CREATE TABLE trips (
    trip_id      TEXT PRIMARY KEY,
    route_id     TEXT NOT NULL,
    service_id   TEXT NOT NULL,
    trip_headsign TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(route_id)
);

-- Stop Times: when a trip visits each stop (the biggest table)
CREATE TABLE stop_times (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id        TEXT NOT NULL,
    stop_id        TEXT NOT NULL,
    arrival_time   TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    stop_sequence  INTEGER NOT NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
    FOREIGN KEY (stop_id) REFERENCES stops(stop_id)
);
"""

# Indexes created AFTER loading data (faster bulk insert)
INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_stop_times_trip    ON stop_times(trip_id);
CREATE INDEX IF NOT EXISTS idx_stop_times_stop    ON stop_times(stop_id);
CREATE INDEX IF NOT EXISTS idx_stop_times_seq     ON stop_times(trip_id, stop_sequence);
CREATE INDEX IF NOT EXISTS idx_trips_route        ON trips(route_id);
"""


# ── 2. Database Setup ────────────────────────────────────────────────────────

def create_schema(conn: sqlite3.Connection):
    """Create all tables from the schema definition."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    console.print("[green]✓[/green] Schema created (stops, routes, trips, stop_times)")


# ── 3. Data Loading ──────────────────────────────────────────────────────────

def load_csv_to_table(conn: sqlite3.Connection, filename: str, table: str, columns: list[str]) -> int:
    """Generic loader: reads a GTFS CSV and inserts rows into a SQLite table."""
    filepath = GTFS_PATH / filename
    if not filepath.exists():
        console.print(f"[red]✗ Missing:[/red] {filename}")
        return 0

    placeholders = ", ".join(["?"] * len(columns))
    col_names    = ", ".join(columns)
    sql          = f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})"

    rows_loaded = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip whitespace from all values
            values = [row.get(col, "").strip() for col in columns]
            try:
                conn.execute(sql, values)
                rows_loaded += 1
            except sqlite3.IntegrityError:
                pass  # Skip duplicate primary keys

    conn.commit()
    return rows_loaded


def load_all_data(conn: sqlite3.Connection):
    """Load all four GTFS files into the database."""
    console.print("\n[bold]Loading GTFS data into SQLite...[/bold]")

    tables = [
        ("stops.txt",      "stops",      ["stop_id", "stop_name", "stop_lat", "stop_lon"]),
        ("routes.txt",     "routes",     ["route_id", "route_short_name", "route_long_name", "route_type"]),
        ("trips.txt",      "trips",      ["trip_id", "route_id", "service_id", "trip_headsign"]),
        ("stop_times.txt", "stop_times", ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]),
    ]

    for filename, table, columns in tables:
        n = load_csv_to_table(conn, filename, table, columns)
        console.print(f"  [green]✓[/green] {table:12s} → [bold]{n}[/bold] rows")


def create_indexes(conn: sqlite3.Connection):
    """Add indexes after bulk load for better performance."""
    conn.executescript(INDEX_SQL)
    conn.commit()
    console.print("[green]✓[/green] Indexes created on stop_times (trip_id, stop_id, sequence)")


# ── 4. SQL Queries ───────────────────────────────────────────────────────────
#
# These are real queries you'd write in a DBMS assignment.
# Each one teaches a different SQL concept.

def run_query(conn: sqlite3.Connection, title: str, sql: str, show_sql: bool = True) -> list:
    """Run a query, time it, and return results."""
    if show_sql:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        syntax = Syntax(sql.strip(), "sql", theme="monokai", line_numbers=False)
        console.print(syntax)

    start = time.perf_counter()
    cursor = conn.execute(sql)
    rows = cursor.fetchall()
    elapsed = (time.perf_counter() - start) * 1000

    console.print(f"[dim]→ {len(rows)} rows in {elapsed:.2f}ms[/dim]")
    return rows


def show_table(rows: list, headers: list, title: str = ""):
    """Display query results as a rich table."""
    table = Table(title=title, box=box.ROUNDED, header_style="bold magenta")
    for h in headers:
        table.add_column(h)
    for row in rows[:10]:  # Cap at 10 rows for readability
        table.add_row(*[str(v) for v in row])
    console.print(table)


def run_all_queries(conn: sqlite3.Connection):
    """Run 6 progressively complex SQL queries."""

    # ── Q1: Simple SELECT with ORDER BY ──────────────────────────────────────
    rows = run_query(conn,
        "Q1 — All stops ordered by name (SELECT + ORDER BY)",
        """
        SELECT stop_id, stop_name, stop_lat, stop_lon
        FROM   stops
        ORDER  BY stop_name
        LIMIT  8;
        """
    )
    show_table(rows, ["Stop ID", "Name", "Lat", "Lon"])

    # ── Q2: Filter with WHERE ─────────────────────────────────────────────────
    rows = run_query(conn,
        "Q2 — All bus routes only (WHERE filter)",
        """
        SELECT route_short_name, route_long_name
        FROM   routes
        WHERE  route_type = 3
        ORDER  BY route_short_name;
        """
    )
    show_table(rows, ["Route No.", "Name"])

    # ── Q3: JOIN two tables ───────────────────────────────────────────────────
    rows = run_query(conn,
        "Q3 — Stops on Route 5, in order (JOIN + ORDER BY)",
        """
        SELECT st.stop_sequence,
               s.stop_name,
               st.arrival_time
        FROM   stop_times  st
        JOIN   stops       s   ON s.stop_id  = st.stop_id
        JOIN   trips       t   ON t.trip_id  = st.trip_id
        JOIN   routes      r   ON r.route_id = t.route_id
        WHERE  r.route_short_name = '5'
          AND  t.trip_id = (
               SELECT trip_id FROM trips
               WHERE  route_id = (
                      SELECT route_id FROM routes
                      WHERE  route_short_name = '5'
                      LIMIT 1)
               LIMIT 1)
        ORDER  BY st.stop_sequence;
        """
    )
    show_table(rows, ["#", "Stop Name", "Arrival"])

    # ── Q4: GROUP BY + COUNT (aggregate) ─────────────────────────────────────
    rows = run_query(conn,
        "Q4 — How many times each stop is visited (GROUP BY + COUNT)",
        """
        SELECT s.stop_name,
               COUNT(*) AS visit_count
        FROM   stop_times st
        JOIN   stops      s  ON s.stop_id = st.stop_id
        GROUP  BY st.stop_id
        ORDER  BY visit_count DESC
        LIMIT  8;
        """
    )
    show_table(rows, ["Stop Name", "Visits"])

    # ── Q5: Subquery — find stops NOT on any route ────────────────────────────
    rows = run_query(conn,
        "Q5 — Stops with NO service (subquery with NOT IN)",
        """
        SELECT stop_id, stop_name
        FROM   stops
        WHERE  stop_id NOT IN (
               SELECT DISTINCT stop_id FROM stop_times
        );
        """
    )
    if rows:
        show_table(rows, ["Stop ID", "Stop Name"])
    else:
        console.print("[dim]  All stops have service — great network coverage![/dim]")

    # ── Q6: Multi-join — full trip schedule for a route ──────────────────────
    rows = run_query(conn,
        "Q6 — Complete timetable: route name + stop + time (3-table JOIN)",
        """
        SELECT r.route_short_name  AS route,
               t.trip_headsign     AS direction,
               s.stop_name         AS stop,
               st.arrival_time     AS arrives
        FROM   stop_times  st
        JOIN   stops       s  ON s.stop_id  = st.stop_id
        JOIN   trips       t  ON t.trip_id  = st.trip_id
        JOIN   routes      r  ON r.route_id = t.route_id
        WHERE  r.route_short_name = '12'
        ORDER  BY t.trip_id, st.stop_sequence;
        """
    )
    show_table(rows, ["Route", "Direction", "Stop", "Arrives"])


# ── 5. Index performance demo ─────────────────────────────────────────────────

def demo_index_benefit(conn: sqlite3.Connection):
    """Show concretely why indexes matter."""
    console.print("\n[bold cyan]Bonus — Why indexes matter[/bold cyan]")

    # Simulate a slow scan by looking up a stop without index hint
    sql = "SELECT COUNT(*) FROM stop_times WHERE stop_id = 'S001';"

    start = time.perf_counter()
    conn.execute(sql).fetchone()
    t1 = (time.perf_counter() - start) * 1000

    # With the index it's the same query — SQLite uses it automatically
    start = time.perf_counter()
    conn.execute(sql).fetchone()
    t2 = (time.perf_counter() - start) * 1000

    # Check index usage with EXPLAIN QUERY PLAN
    plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
    plan_text = "\n".join(str(row) for row in plan)

    console.print(f"  Query: [italic]{sql}[/italic]")
    console.print(f"  First run (cold):  [yellow]{t1:.3f}ms[/yellow]")
    console.print(f"  Second run (warm): [green]{t2:.3f}ms[/green]")
    console.print(f"  Query plan: [dim]{plan_text}[/dim]")
    console.print(
        "  [dim]On a dataset with 100,000 rows, a full table scan = ~50ms, "
        "indexed lookup = ~0.1ms[/dim]"
    )


# ── 6. DB Stats ───────────────────────────────────────────────────────────────

def print_db_stats(conn: sqlite3.Connection):
    """Show final database statistics."""
    tables = ["stops", "routes", "trips", "stop_times"]

    stat_table = Table(title="Database Summary", box=box.ROUNDED, header_style="bold blue")
    stat_table.add_column("Table")
    stat_table.add_column("Rows", justify="right")
    stat_table.add_column("Columns", justify="right")

    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        cols  = conn.execute(f"PRAGMA table_info({t})").fetchall()
        stat_table.add_row(t, str(count), str(len(cols)))

    console.print(stat_table)

    # DB file size
    db_size = DB_PATH.stat().st_size / 1024
    console.print(f"[dim]Database file: {DB_PATH} ({db_size:.1f} KB)[/dim]")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 2: SQLite Database\n"
        "[dim]Phase 1 | SmartCity Project[/dim]",
        border_style="blue",
    ))

    # Connect (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK constraints
    console.print(f"\n[green]✓[/green] Connected to [bold]{DB_PATH}[/bold]")

    # Build DB
    console.rule("[bold]Step 1 — Create Schema[/bold]")
    create_schema(conn)

    console.rule("[bold]Step 2 — Load Data[/bold]")
    load_all_data(conn)

    console.rule("[bold]Step 3 — Create Indexes[/bold]")
    create_indexes(conn)

    console.rule("[bold]Step 4 — Database Stats[/bold]")
    print_db_stats(conn)

    console.rule("[bold]Step 5 — SQL Queries[/bold]")
    run_all_queries(conn)

    demo_index_benefit(conn)

    conn.close()

    console.print(Panel(
        "[bold green]Week 2 complete![/bold green]\n\n"
        "You now have [bold]transit.db[/bold] — a real SQLite database with:\n"
        "  • 4 tables with proper schema and foreign keys\n"
        "  • Indexes on the busiest table (stop_times)\n"
        "  • 6 SQL queries: SELECT, WHERE, JOIN, GROUP BY, subqueries\n\n"
        "Next up → [bold]Week 3:[/bold] Build the transit graph from this data.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
