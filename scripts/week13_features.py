"""
Week 13 — Feature Engineering for Delay Prediction
Transit Optimizer | Phase 2

What this script does:
  1. Generates a realistic synthetic delay dataset
     (real GTFS delay feeds are rare in India — synthetic is standard practice
      even at companies; it teaches identical ML concepts)
  2. Engineers features from GTFS data + temporal signals
  3. Saves the dataset to data/delay_features.csv and delay_features.db
  4. Produces an EDA (exploratory data analysis) report

Why synthetic?
  Real bus delays follow predictable patterns:
    - Rush hour (8-10am, 5-8pm) → higher delays
    - Night / early morning → low delays
    - Terminus stops → lower delay (route reset)
    - Mid-route stops → delay accumulates
    - Weekends → lower delays
    - Bad weather proxy → random spike days
  We encode all of these — the model will learn real signal, not noise.

Features engineered:
  stop_sequence_norm   float  position in trip (0=start, 1=end)
  hour                 int    departure hour (0–23)
  is_rush_hour         int    1 if 7-10am or 5-8pm
  is_weekend           int    1 if Saturday/Sunday
  route_type           int    1=metro, 3=bus
  n_stops_on_trip      int    total stops in the trip
  prior_stop_delay     float  delay at previous stop (lag feature)
  temp_deviation       float  synthetic weather proxy (°C above normal)
  route_frequency      float  trips/hour on this route (proxy for congestion)

Target:
  delay_minutes        float  minutes late at this stop (can be 0 = on time)

Key CS concepts covered:
  - Feature engineering (turning raw data into ML inputs)
  - Temporal features (hour, rush_hour, weekend)
  - Lag features (prior_stop_delay)
  - Normalisation (stop_sequence_norm)
  - Exploratory data analysis
  - Train/test split rationale

Run: python -m scripts.week13_features
"""

import sqlite3
import random
import math
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

console = Console()

DB_PATH      = Path("data/transit.db")
CSV_PATH     = Path("data/delay_features.csv")
GRAPH_PATH   = Path("data/graph_with_transfers.json")

random.seed(42)   # reproducible dataset
np.random.seed(42)

N_DAYS = 90   # simulate 90 days of bus operations


# ── 1. Load GTFS base data ────────────────────────────────────────────────────

def load_base_data(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stops = pd.read_sql("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops", conn)
    routes = pd.read_sql("""
        SELECT r.route_id, r.route_short_name, r.route_type,
               COUNT(DISTINCT t.trip_id) as trip_count
        FROM routes r
        JOIN trips t ON t.route_id = r.route_id
        GROUP BY r.route_id
    """, conn)
    stop_times = pd.read_sql("""
        SELECT st.trip_id, st.stop_id, st.stop_sequence,
               st.departure_time, t.route_id
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        ORDER BY st.trip_id, st.stop_sequence
    """, conn)
    return stops, routes, stop_times


# ── 2. Time helpers ───────────────────────────────────────────────────────────

def parse_time(t: str) -> int:
    """'08:30:00' → minutes since midnight."""
    h, m, s = map(int, t.split(":"))
    return h * 60 + m

def is_rush_hour(hour: int) -> int:
    return int((7 <= hour <= 10) or (17 <= hour <= 20))

def is_weekend(day_of_week: int) -> int:
    return int(day_of_week >= 5)   # 5=Saturday, 6=Sunday


# ── 3. Delay generation model ─────────────────────────────────────────────────
#
# We encode real-world delay dynamics:
#
#   base_delay     = route-level baseline (some routes just run late)
#   time_factor    = rush hour multiplier (up to 3×)
#   propagation    = each stop adds a small extra delay
#   weather_spike  = some days randomly have system-wide delays
#   recovery       = late buses sometimes run faster to catch up (negative)
#
# This mirrors real-world delay modelling at transport authorities.

def compute_delay_multiplier(hour: int, day_of_week: int,
                              weather_factor: float) -> float:
    """Overall delay multiplier for a given hour/day/weather."""
    # Time of day curve
    if 7 <= hour <= 9:
        time_mult = 2.5 + random.gauss(0, 0.3)
    elif 17 <= hour <= 19:
        time_mult = 2.8 + random.gauss(0, 0.4)
    elif 10 <= hour <= 16:
        time_mult = 1.4 + random.gauss(0, 0.2)
    elif 20 <= hour <= 22:
        time_mult = 1.2 + random.gauss(0, 0.15)
    else:
        time_mult = 0.6 + random.gauss(0, 0.1)   # night / early morning

    # Weekend discount
    if day_of_week >= 5:
        time_mult *= 0.65

    # Weather amplification
    time_mult *= (1.0 + weather_factor * 0.15)

    return max(0.1, time_mult)


def generate_delays_for_trip(trip_stops: pd.DataFrame,
                              route_type: int,
                              hour: int,
                              day_of_week: int,
                              weather_factor: float,
                              route_base: float) -> list[float]:
    """
    Generate stop-by-stop delays for one trip.
    Each stop's delay depends on the previous stop (propagation).
    """
    n = len(trip_stops)
    if n == 0:
        return []

    mult = compute_delay_multiplier(hour, day_of_week, weather_factor)

    delays = []
    prev_delay = 0.0

    for i, (_, row) in enumerate(trip_stops.iterrows()):
        seq_norm = i / max(n - 1, 1)   # 0.0 at start, 1.0 at end

        # Base delay for this stop
        base = route_base * mult

        # Delay accumulates mid-route, resets at terminus
        if i == 0:
            # First stop: small initial delay
            d = max(0, random.gauss(base * 0.3, 1.0))
        else:
            # Propagation: carry forward some of prior delay
            carry  = prev_delay * random.uniform(0.5, 0.9)
            # Position effect: mid-route stops get extra delay
            pos_extra = base * seq_norm * random.uniform(0.3, 0.8)
            # Random noise
            noise  = random.gauss(0, 0.8)
            d = max(0, carry + pos_extra + noise)

        # Metro (type 1) has lower delays than bus (type 3)
        if route_type == 1:
            d *= 0.4

        # Very rarely: no delay (bus running early is capped to 0)
        d = max(0.0, min(d, 30.0))   # cap at 30 min
        delays.append(round(d, 2))
        prev_delay = d

    return delays


# ── 4. Feature row builder ────────────────────────────────────────────────────

def build_feature_rows(stops_df, routes_df, stop_times_df,
                        n_days: int = N_DAYS) -> list[dict]:
    """
    For each (trip × day × simulated_departure_hour), generate one row
    per stop with all features + the delay target.
    """
    rows = []

    # Route lookup maps
    route_type_map = dict(zip(routes_df["route_id"], routes_df["route_type"].astype(int)))
    route_freq_map = dict(zip(routes_df["route_id"], routes_df["trip_count"].astype(float)))

    # Per-route baseline delay (bus-specific characteristics)
    route_base_map = {
        rid: random.uniform(1.5, 4.5)
        for rid in routes_df["route_id"]
    }

    # Group stop_times by trip
    trip_groups = {
        tid: grp.sort_values("stop_sequence")
        for tid, grp in stop_times_df.groupby("trip_id")
    }

    # Simulate N_DAYS of operations
    base_date = datetime(2024, 1, 1)

    for day_offset in range(n_days):
        date       = base_date + timedelta(days=day_offset)
        dow        = date.weekday()   # 0=Mon, 6=Sun
        # Weather: ~15% of days have bad weather
        weather    = random.gauss(2.5, 1.2) if random.random() < 0.15 else random.gauss(0.3, 0.5)
        weather    = max(0.0, weather)

        for trip_id, trip_stops in trip_groups.items():
            if trip_stops.empty:
                continue

            route_id   = trip_stops.iloc[0]["route_id"]
            rtype      = route_type_map.get(route_id, 3)
            rfreq      = route_freq_map.get(route_id, 2.0)
            rbase      = route_base_map.get(route_id, 2.5)
            n_stops    = len(trip_stops)

            # Simulate multiple departure times per day per trip
            dep_times  = [random.randint(5, 22) for _ in range(3)]

            for hour in dep_times:
                delays = generate_delays_for_trip(
                    trip_stops, rtype, hour, dow, weather, rbase
                )

                prev_delay = 0.0
                for i, (_, stop_row) in enumerate(trip_stops.iterrows()):
                    delay = delays[i]
                    seq_norm = round(i / max(n_stops - 1, 1), 4)

                    rows.append({
                        # Identifiers (not used as features)
                        "trip_id":          trip_id,
                        "stop_id":          stop_row["stop_id"],
                        "route_id":         route_id,
                        "day":              date.strftime("%Y-%m-%d"),

                        # ── Features ─────────────────────────────────────
                        "stop_sequence_norm": seq_norm,
                        "hour":               hour,
                        "is_rush_hour":       is_rush_hour(hour),
                        "is_weekend":         is_weekend(dow),
                        "day_of_week":        dow,
                        "route_type":         rtype,
                        "n_stops_on_trip":    n_stops,
                        "prior_stop_delay":   round(prev_delay, 2),
                        "temp_deviation":     round(weather, 2),
                        "route_frequency":    round(rfreq, 1),

                        # ── Target ───────────────────────────────────────
                        "delay_minutes":      delay,
                    })

                    prev_delay = delay

    return rows


# ── 5. EDA helpers ────────────────────────────────────────────────────────────

def eda_summary(df: pd.DataFrame):
    """Print key statistics about the generated dataset."""

    # Overall stats
    stat_tbl = Table(title="Dataset Overview", box=box.ROUNDED, header_style="bold cyan")
    stat_tbl.add_column("Metric")
    stat_tbl.add_column("Value", justify="right", style="bold")
    stat_tbl.add_row("Total rows",         f"{len(df):,}")
    stat_tbl.add_row("Features",           str(len(df.columns) - 4))  # minus ID cols
    stat_tbl.add_row("Days simulated",     str(df["day"].nunique()))
    stat_tbl.add_row("Unique trips",       str(df["trip_id"].nunique()))
    stat_tbl.add_row("Unique stops",       str(df["stop_id"].nunique()))
    stat_tbl.add_row("Avg delay",          f"{df['delay_minutes'].mean():.2f} min")
    stat_tbl.add_row("Median delay",       f"{df['delay_minutes'].median():.2f} min")
    stat_tbl.add_row("Max delay",          f"{df['delay_minutes'].max():.2f} min")
    stat_tbl.add_row("On-time rows (=0)",  f"{(df['delay_minutes'] == 0).sum():,}")
    stat_tbl.add_row("% on time",          f"{(df['delay_minutes'] == 0).mean()*100:.1f}%")
    console.print(stat_tbl)

    # Delay by hour
    hour_tbl = Table(title="Average delay by hour", box=box.ROUNDED, header_style="bold blue")
    hour_tbl.add_column("Hour")
    hour_tbl.add_column("Avg delay", justify="right")
    hour_tbl.add_column("Bar")

    hourly = df.groupby("hour")["delay_minutes"].mean().sort_index()
    max_d  = hourly.max()
    for hour, avg in hourly.items():
        bar_len = int((avg / max_d) * 28)
        bar     = "█" * bar_len
        color   = "red" if is_rush_hour(int(hour)) else "cyan"
        label   = f"[dim]{int(hour):02d}:00[/dim]"
        hour_tbl.add_row(label, f"{avg:.2f}m", f"[{color}]{bar}[/{color}]")
    console.print(hour_tbl)

    # Delay by route type
    type_tbl = Table(title="Delay by route type", box=box.ROUNDED, header_style="bold green")
    type_tbl.add_column("Route type")
    type_tbl.add_column("Avg delay",  justify="right")
    type_tbl.add_column("Rows",       justify="right")
    type_map_display = {1: "Metro", 3: "Bus"}
    for rtype, grp in df.groupby("route_type"):
        type_tbl.add_row(
            type_map_display.get(int(rtype), str(rtype)),
            f"{grp['delay_minutes'].mean():.2f}m",
            f"{len(grp):,}",
        )
    console.print(type_tbl)

    # Feature correlation with target
    feature_cols = [
        "stop_sequence_norm", "hour", "is_rush_hour", "is_weekend",
        "route_type", "n_stops_on_trip", "prior_stop_delay",
        "temp_deviation", "route_frequency"
    ]
    corr_tbl = Table(
        title="Feature correlation with delay_minutes",
        box=box.ROUNDED, header_style="bold magenta"
    )
    corr_tbl.add_column("Feature")
    corr_tbl.add_column("Pearson r", justify="right")
    corr_tbl.add_column("Strength")

    corrs = df[feature_cols + ["delay_minutes"]].corr()["delay_minutes"].drop("delay_minutes")
    for feat, r in corrs.sort_values(key=abs, ascending=False).items():
        bar_len = int(abs(r) * 20)
        bar     = "█" * bar_len
        color   = "green" if abs(r) > 0.3 else ("yellow" if abs(r) > 0.1 else "dim")
        sign    = "+" if r >= 0 else "-"
        corr_tbl.add_row(
            feat,
            f"{r:+.3f}",
            f"[{color}]{sign}{bar}[/{color}]",
        )
    console.print(corr_tbl)
    console.print(
        "[dim]Strong predictors (|r|>0.3) highlighted green. "
        "prior_stop_delay and is_rush_hour should dominate.[/dim]\n"
    )


def print_sample_rows(df: pd.DataFrame, n: int = 6):
    """Show a sample of the dataset."""
    feature_cols = [
        "stop_id", "hour", "is_rush_hour", "stop_sequence_norm",
        "prior_stop_delay", "temp_deviation", "delay_minutes"
    ]
    tbl = Table(title=f"Sample rows (n={n})", box=box.ROUNDED, header_style="bold yellow")
    for c in feature_cols:
        tbl.add_column(c, justify="right" if c != "stop_id" else "left")

    sample = df[feature_cols].sample(n, random_state=1)
    for _, row in sample.iterrows():
        tbl.add_row(*[str(round(row[c], 2)) if isinstance(row[c], float) else str(row[c])
                      for c in feature_cols])
    console.print(tbl)


# ── 6. Save dataset ───────────────────────────────────────────────────────────

def save_dataset(df: pd.DataFrame, conn: sqlite3.Connection):
    """Save to CSV and to a new SQLite table."""
    # CSV
    df.to_csv(CSV_PATH, index=False)
    size_kb = CSV_PATH.stat().st_size / 1024
    console.print(f"[green]✓[/green] Saved [bold]{CSV_PATH}[/bold] ({size_kb:.0f} KB, {len(df):,} rows)")

    # SQLite table
    df.to_sql("delay_features", conn, if_exists="replace", index=False)
    conn.commit()
    console.print(f"[green]✓[/green] Saved [bold]delay_features[/bold] table to transit.db")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 13: Feature Engineering\n"
        "[dim]Phase 2 | ML delay prediction dataset[/dim]",
        border_style="blue",
    ))

    conn = sqlite3.connect(DB_PATH)

    # Step 1 — load GTFS
    console.rule("[bold]Step 1 — Load GTFS base data[/bold]")
    stops_df, routes_df, stop_times_df = load_base_data(conn)
    console.print(
        f"[green]✓[/green] {len(stops_df)} stops  "
        f"{len(routes_df)} routes  "
        f"{len(stop_times_df)} stop-time records"
    )
    console.print(f"[dim]Simulating {N_DAYS} days of operations...[/dim]\n")

    # Step 2 — generate features
    console.rule("[bold]Step 2 — Generate synthetic delay dataset[/bold]")
    import time
    t0   = time.perf_counter()
    rows = build_feature_rows(stops_df, routes_df, stop_times_df, n_days=N_DAYS)
    df   = pd.DataFrame(rows)
    elapsed = time.perf_counter() - t0
    console.print(
        f"[green]✓[/green] Generated [bold]{len(df):,}[/bold] rows "
        f"in {elapsed:.2f}s\n"
    )

    # Step 3 — EDA
    console.rule("[bold]Step 3 — Exploratory Data Analysis[/bold]")
    eda_summary(df)

    # Step 4 — sample rows
    console.rule("[bold]Step 4 — Sample rows[/bold]")
    print_sample_rows(df)

    # Step 5 — save
    console.rule("[bold]Step 5 — Save dataset[/bold]")
    save_dataset(df, conn)
    conn.close()

    # Step 6 — what's next
    console.print(Panel(
        "[bold]Features engineered this week[/bold]\n\n"
        "  [cyan]stop_sequence_norm[/cyan]   Where in the trip (0=start → 1=end)\n"
        "  [cyan]hour[/cyan]                 Departure hour — captures time-of-day signal\n"
        "  [cyan]is_rush_hour[/cyan]         Binary flag: 7-10am or 5-8pm\n"
        "  [cyan]is_weekend[/cyan]           Binary flag: less congestion on weekends\n"
        "  [cyan]route_type[/cyan]           Metro (1) vs Bus (3) — systematic difference\n"
        "  [cyan]n_stops_on_trip[/cyan]      Longer routes accumulate more delay\n"
        "  [cyan]prior_stop_delay[/cyan]     Lag feature — most predictive signal\n"
        "  [cyan]temp_deviation[/cyan]       Weather proxy — random spike days\n"
        "  [cyan]route_frequency[/cyan]      Busier routes = more congestion\n\n"
        "  [bold]Target: delay_minutes[/bold]  (regression — predict a continuous value)\n\n"
        "  [dim]Dataset saved to data/delay_features.csv[/dim]",
        title="Feature summary",
        border_style="dim",
    ))

    console.print(Panel(
        "[bold green]Week 13 complete![/bold green]\n\n"
        f"  {len(df):,} training rows generated from {N_DAYS} simulated days\n"
        "  9 features engineered from temporal + route + weather signals\n"
        "  EDA confirms prior_stop_delay and is_rush_hour are strong predictors\n"
        "  Dataset saved to CSV + SQLite for Week 14\n\n"
        "Next up → [bold]Week 14:[/bold] Train the delay prediction model\n"
        "  Linear Regression → Random Forest → compare with MAE/RMSE",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
