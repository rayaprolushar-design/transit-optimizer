"""
scripts/week_u7.py — Upgrade 7 Demo
Run: python -m scripts.week_u7
"""
import sys, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich         import box

console = Console()

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Upgrade 7\n"
        "[dim]Redis · PostgreSQL · Metrics · Locust[/dim]",
        border_style="blue",
    ))

    # Step 1: Redis cache
    console.rule("[bold]Step 1 — Redis Cache[/bold]")
    from infra.cache import route_cache
    console.print(f"  Backend: [bold]{'Redis' if route_cache.is_redis else 'In-memory (Redis not running)'}[/bold]")

    for i in range(60):
        route_cache.set(f"route:S00{i%5}:S01{i%4}", {"found": True, "minutes": 20+i%10})
    for i in range(100):
        route_cache.get(f"route:S00{i%5}:S01{i%4}")

    s = route_cache.stats()
    tbl = Table(title="Cache stats", box=box.ROUNDED, header_style="bold cyan")
    tbl.add_column("Metric"); tbl.add_column("Value", justify="right", style="bold")
    for k,v in s.items(): tbl.add_row(k, str(v))
    console.print(tbl)

    # Step 2: Database
    console.rule("[bold]Step 2 — Database[/bold]")
    from infra.database import db
    console.print(f"  Backend: [bold]{db.backend}[/bold]")
    for _ in range(5):
        db.log_algorithm_run("astar", f"S00{random.randint(1,5)}",
                             f"S01{random.randint(0,7)}", True,
                             round(random.uniform(10,40),1),
                             random.randint(3,12),
                             round(random.uniform(0.01,0.5),3))
    console.print("  [green]✓[/green] Logged 5 algorithm runs")

    # Step 3: Metrics
    console.rule("[bold]Step 3 — Metrics Collector[/bold]")
    from infra.metrics import metrics
    endpoints = [("/route","GET",200),("/predict-delay","POST",200),
                 ("/board/S001","GET",200),("/stats","GET",200)]
    for _ in range(200):
        p,m,st = random.choice(endpoints)
        metrics.record(p, m, st, max(0.5, random.gauss(15,8)))

    sm = metrics.summary()
    lat = sm["latency_ms"]
    tbl2 = Table(title="Live metrics", box=box.ROUNDED, header_style="bold magenta")
    tbl2.add_column("Metric"); tbl2.add_column("Value", justify="right", style="bold")
    tbl2.add_row("Throughput",   f"{sm['throughput_rps']} req/s")
    tbl2.add_row("Error rate",   f"{sm['error_rate_pct']}%")
    tbl2.add_row("p50",          f"{lat['p50']}ms")
    tbl2.add_row("p95",          f"{lat['p95']}ms")
    tbl2.add_row("p99",          f"{lat['p99']}ms")
    console.print(tbl2)

    # Step 4: Locust instructions
    console.rule("[bold]Step 4 — Load Test Commands[/bold]")
    console.print(Panel(
        "# Terminal 1 — 4 FastAPI workers\n"
        "uvicorn api.server:app --workers 4 --port 8000\n\n"
        "# Terminal 2 — 100 concurrent users, 60 seconds\n"
        "locust -f locustfile.py --headless \\\n"
        "  --users 100 --spawn-rate 10 \\\n"
        "  --run-time 60s --host http://localhost:8000\n\n"
        "# Or open the web UI at localhost:8089:\n"
        "locust -f locustfile.py --host http://localhost:8000\n\n"
        "Target: [green]> 500 req/s · p99 < 100ms · error < 0.1%[/green]",
        border_style="dim", title="Commands",
    ))

    console.print(Panel(
        "[bold green]Upgrade 7 complete![/bold green]\n\n"
        "  Redis cache      → TTL-based, auto-fallback to memory\n"
        "  PostgreSQL       → connection pool size=10, full-text search\n"
        "  Metrics          → p50/p95/p99 latency, throughput, errors\n"
        "  Locust           → ready to run 100-500 concurrent users\n\n"
        "  After running Locust, update your email:\n"
        "  '[X] req/s throughput · p99 = [Y]ms · error rate < 0.1%'",
        border_style="green",
    ))

if __name__ == "__main__":
    main()
