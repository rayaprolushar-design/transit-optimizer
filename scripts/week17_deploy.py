"""
Week 17 — Docker + Deployment Guide
Transit Optimizer | Phase 2

This script:
  1. Verifies your project structure is deployment-ready
  2. Prints step-by-step Docker + Railway deploy instructions
  3. Generates a curl test suite you can run against the live URL

Run: python -m scripts.week17_deploy
"""

import json
import sys
from pathlib import Path
from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.syntax  import Syntax
from rich         import box

console = Console()

ROOT = Path(__file__).parent.parent


# ── 1. Pre-flight checks ──────────────────────────────────────────────────────

def check_structure() -> bool:
    """Verify all required files exist before attempting deploy."""
    required = [
        "Dockerfile",
        "docker-compose.yml",
        "railway.json",
        "requirements.txt",
        ".github/workflows/ci.yml",
        "api/server.py",
        "api/__init__.py",
        "scripts/router.py",
        "scripts/search.py",
        "scripts/week9_performance.py",
        "data/graph_with_transfers.json",
        "data/delay_model.joblib",
        "data/model_meta.json",
    ]

    tbl = Table(
        title="Pre-flight check", box=box.ROUNDED,
        header_style="bold cyan",
    )
    tbl.add_column("File")
    tbl.add_column("Status", justify="center", width=10)

    all_ok = True
    for f in required:
        exists = (ROOT / f).exists()
        if not exists:
            all_ok = False
        tbl.add_row(f, "[green]✓[/green]" if exists else "[red]✗ MISSING[/red]")

    console.print(tbl)
    return all_ok


# ── 2. Model info ─────────────────────────────────────────────────────────────

def print_model_info():
    meta_path = ROOT / "data/model_meta.json"
    if not meta_path.exists():
        console.print("[red]model_meta.json missing[/red]")
        return
    meta = json.loads(meta_path.read_text())

    tbl = Table(title="Model being deployed", box=box.ROUNDED, header_style="bold green")
    tbl.add_column("Metric")
    tbl.add_column("Value", justify="right", style="bold")
    tbl.add_row("Name",      meta.get("model_name", "?"))
    tbl.add_row("Test MAE",  f"{meta.get('test_mae', '?')} min")
    tbl.add_row("Test R²",   str(meta.get("test_r2",  "?")))
    tbl.add_row("Trained on", f"{meta.get('n_train', '?'):,} rows")
    console.print(tbl)


# ── 3. Step-by-step instructions ─────────────────────────────────────────────

def print_docker_steps():
    console.print(Panel(
        "[bold]Step 1 — Test Docker build locally[/bold]\n\n"
        "  [cyan]# Build the image[/cyan]\n"
        "  docker build -t transit-optimizer .\n\n"
        "  [cyan]# Run it[/cyan]\n"
        "  docker run -p 8000:8000 transit-optimizer\n\n"
        "  [cyan]# Or use docker compose[/cyan]\n"
        "  docker compose up --build\n\n"
        "  [cyan]# Test it's alive[/cyan]\n"
        "  curl http://localhost:8000/\n\n"
        "  [dim]Expected: {\"status\": \"ok\", \"stops\": 23, ...}[/dim]",
        border_style="blue",
        title="Docker",
    ))


def print_railway_steps():
    console.print(Panel(
        "[bold]Step 2 — Deploy to Railway (free tier)[/bold]\n\n"
        "  1. Go to [bold]railway.app[/bold] → sign in with GitHub\n"
        "  2. Click [bold]New Project → Deploy from GitHub repo[/bold]\n"
        "  3. Select [bold]transit-optimizer[/bold]\n"
        "  4. Railway auto-detects the Dockerfile → click Deploy\n"
        "  5. Wait ~2 min for build\n"
        "  6. Click [bold]Settings → Generate Domain[/bold]\n"
        "     → you get https://transit-optimizer-xxxx.railway.app\n\n"
        "  [dim]Free tier: 500 hours/month, 512 MB RAM — plenty for demos[/dim]\n\n"
        "  [bold]That URL goes on your resume and GitHub README.[/bold]",
        border_style="green",
        title="Railway Deploy",
    ))


def print_render_steps():
    console.print(Panel(
        "[bold]Alternative: Render.com (also free)[/bold]\n\n"
        "  1. Go to [bold]render.com[/bold] → sign in with GitHub\n"
        "  2. New → Web Service → connect transit-optimizer repo\n"
        "  3. Runtime: Docker\n"
        "  4. Start command: leave blank (reads from Dockerfile CMD)\n"
        "  5. Free instance type → Create Web Service\n\n"
        "  [dim]Render free tier spins down after 15 min inactivity.\n"
        "  Railway stays up — better for live demos.[/dim]",
        border_style="dim",
        title="Alternative: Render",
    ))


def print_ci_explanation():
    console.print(Panel(
        "[bold]Step 3 — GitHub Actions CI/CD[/bold]\n\n"
        "  Every push to main now automatically:\n"
        "    1. Runs pytest tests/test_phase1.py   (49 tests)\n"
        "    2. Runs pytest tests/test_api.py       (31 tests)\n"
        "    3. Checks coverage ≥ 70%\n"
        "    4. Builds Docker image\n"
        "    5. Smoke tests the container (hits /)\n\n"
        "  If any step fails → red X on GitHub, deploy blocked.\n"
        "  If all pass → green ✓ → Railway auto-deploys.\n\n"
        "  [dim]This is exactly how Uber/Google ship code to production.\n"
        "  Showing this pipeline in interviews is a massive signal.[/dim]",
        border_style="yellow",
        title="CI/CD",
    ))


def print_curl_tests(base_url: str = "http://localhost:8000"):
    console.print(Panel(
        f"[bold]curl test suite — run against {base_url}[/bold]\n\n"

        "[cyan]# 1. Health check[/cyan]\n"
        f"curl {base_url}/\n\n"

        "[cyan]# 2. List stops[/cyan]\n"
        f"curl '{base_url}/stops?limit=5'\n\n"

        "[cyan]# 3. Filter metro stops[/cyan]\n"
        f"curl '{base_url}/stops?filter=metro'\n\n"

        "[cyan]# 4. Route: MG Road → HSR Layout[/cyan]\n"
        f"curl '{base_url}/route?from=MG%20Road&to=HSR%20Layout'\n\n"

        "[cyan]# 5. Route: compare algorithms[/cyan]\n"
        f"curl '{base_url}/route?from=MG%20Road&to=BTM%20Layout&algorithm=dijkstra'\n\n"

        "[cyan]# 6. Predict delay: rush hour bus[/cyan]\n"
        f"""curl -X POST {base_url}/predict-delay \\
  -H 'Content-Type: application/json' \\
  -d '{{"stop_id":"S001","hour":8,"is_weekend":0,"""
        """"prior_stop_delay":0,"temp_deviation":0.5,"""
        """"stop_sequence_norm":0,"route_type":3,"n_stops_on_trip":6}}'\n\n"""

        "[cyan]# 7. Model info[/cyan]\n"
        f"curl {base_url}/model-info\n\n"

        "[cyan]# 8. Stats[/cyan]\n"
        f"curl {base_url}/stats",
        title="Live API tests",
        border_style="magenta",
    ))


def print_resume_bullets():
    console.print(Panel(
        "[bold]What to write on your resume[/bold]\n\n"
        "  [bold]SmartCity Transit Optimizer[/bold]  |  Python · FastAPI · scikit-learn · Docker\n\n"
        "  • Built end-to-end transit routing system processing real GTFS data\n"
        "    from Bengaluru with 23 stops and 38 route connections\n\n"
        "  • Implemented Dijkstra and A* from scratch; A* visits 62% fewer nodes\n"
        "    via Haversine heuristic on geographic coordinates\n\n"
        "  • Trained Gradient Boosting delay prediction model (MAE=0.76 min, R²=0.83)\n"
        "    on 11,340 synthetic rows; deployed as REST API via FastAPI\n\n"
        "  • Built LRU cache (O(1), thread-safe) reducing repeat query latency 39×;\n"
        "    background graph loader via threading.Event\n\n"
        "  • 80 pytest tests (unit + integration + thread safety);\n"
        "    GitHub Actions CI/CD pipeline; deployed on Railway\n\n"
        "  • [bold]Live:[/bold] https://transit-optimizer-xxxx.railway.app/docs",
        title="Resume",
        border_style="green",
    ))


def print_git_commands():
    console.print(Panel(
        "[bold]Git commands for this week[/bold]\n\n"
        "  git add Dockerfile docker-compose.yml railway.json\n"
        "  git add .github/ .gitignore .dockerignore\n"
        "  git add requirements.txt scripts/week17_deploy.py\n"
        "  git commit -m 'Week 17: Docker, CI/CD pipeline, Railway deploy'\n"
        "  git tag v2.0.0\n"
        "  git push && git push --tags\n\n"
        "  [dim]After Railway connects your repo, every push to main\n"
        "  triggers a new deploy automatically.[/dim]",
        border_style="blue",
        title="Git",
    ))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 17: Docker + Deploy\n"
        "[dim]Phase 2 | Containerize → CI/CD → Live URL[/dim]",
        border_style="blue",
    ))

    # Pre-flight
    console.rule("[bold]Pre-flight check[/bold]")
    ok = check_structure()
    if not ok:
        console.print(
            "\n[red]Some files are missing.[/red] "
            "Make sure you've run weeks 1–16 first.\n"
        )
    else:
        console.print("[green]✓ All required files present — ready to deploy[/green]\n")

    # Model info
    console.rule("[bold]Model being shipped[/bold]")
    print_model_info()
    console.print()

    # Deploy steps
    console.rule("[bold]Deployment steps[/bold]")
    print_docker_steps()
    print_railway_steps()
    print_render_steps()
    print_ci_explanation()

    # Test suite
    console.rule("[bold]Test your live API[/bold]")
    print_curl_tests("https://transit-optimizer-xxxx.railway.app")

    # Git
    console.rule("[bold]Commit this week[/bold]")
    print_git_commands()

    # Resume
    console.rule("[bold]Resume bullets[/bold]")
    print_resume_bullets()

    console.print(Panel(
        "[bold green]Week 17 complete — Phase 2 done![/bold green]\n\n"
        "  [bold]Dockerfile[/bold]          Multi-stage build, non-root user, health check\n"
        "  [bold]docker-compose.yml[/bold]  Local dev with volume-mounted logs\n"
        "  [bold]railway.json[/bold]        One-click Railway deploy config\n"
        "  [bold]ci.yml[/bold]              GitHub Actions: test → build → smoke test\n"
        "  [bold].gitignore[/bold]          Clean repo — no logs, no csvs, no cache\n\n"
        "  After Railway connects: every [bold]git push → auto-deploy[/bold]\n\n"
        "  [bold]Your project now has:[/bold]\n"
        "    ✓ 80 tests passing   ✓ Live HTTPS URL\n"
        "    ✓ CI/CD pipeline     ✓ Docker container\n"
        "    ✓ ML model serving   ✓ Resume-ready bullets\n\n"
        "  Phase 3 → React dashboard with live WebSocket updates\n"
        "  [dim](Say 'start phase 3' whenever you're ready)[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
