"""
display_board/board_client.py
Raspberry Pi / terminal display board client.

What this does:
  - Polls GET /board/{stop_id} every 30 seconds
  - Displays a live arrival board in the terminal (or on a connected screen)
  - Reconnects automatically if the API is unreachable
  - Optionally connects to WS /ws/board/{stop_id} for instant updates

Hardware:
  - Raspberry Pi 4B (any model works) + HDMI display
  - Or: any Android TV / Fire Stick running Termux
  - Or: just a browser tab pointing at the web board (see board.html)

Run:
  # Install deps
  pip install rich aiohttp websockets

  # Run for MG Road stop
  python display_board/board_client.py --stop S001

  # Custom API URL (after Railway deploy)
  python display_board/board_client.py \
      --stop S001 \
      --api https://transit-optimizer-xxxx.railway.app
"""

import asyncio
import argparse
import aiohttp
import json
import sys
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.layout  import Layout
from rich.live    import Live
from rich.text    import Text
from rich         import box

console = Console()

DEFAULT_API = "http://localhost:8000"
POLL_SEC    = 30   # how often to refresh (seconds)


# ── Fetch board data ──────────────────────────────────────────────────────────

async def fetch_board(session: aiohttp.ClientSession,
                      api: str, stop_id: str, n: int = 6) -> dict | None:
    """GET /board/{stop_id} and return parsed JSON."""
    try:
        url = f"{api}/board/{stop_id}?n={n}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return await r.json()
            console.print(f"[red]API error {r.status}[/red]")
            return None
    except aiohttp.ClientConnectorError:
        console.print(f"[red]Cannot reach API at {api}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return None


# ── Render the board ──────────────────────────────────────────────────────────

def render_board(data: dict, last_updated: str) -> Panel:
    """Build a rich Panel that looks like a real display board."""
    stop_name = data.get("stop_name", "Unknown Stop")
    arrivals  = data.get("arrivals", [])
    live_del  = data.get("live_delay", 0)
    has_gps   = data.get("has_gps", False)

    # ── Header ────────────────────────────────────────────────────────────────
    gps_indicator = (
        "[green]● LIVE[/green]" if has_gps else "[yellow]◌ SIMULATED[/yellow]"
    )

    # ── Arrivals table ────────────────────────────────────────────────────────
    tbl = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 2),
        expand=True,
    )
    tbl.add_column("ROUTE", width=8,  style="bold yellow")
    tbl.add_column("DESTINATION",     min_width=18)
    tbl.add_column("SCHED",   width=7,  justify="right", style="dim")
    tbl.add_column("ETA",     width=7,  justify="right")
    tbl.add_column("STATUS",  width=14, justify="center")
    tbl.add_column("CONF",    width=8,  justify="center")

    if not arrivals:
        tbl.add_row("—", "[dim]No upcoming arrivals[/dim]", "—", "—", "—", "—")
    else:
        for arr in arrivals:
            delay = arr.get("delay_minutes", 0)
            status = arr.get("status", "On time")

            # Colour-code by delay severity
            if delay > 3:
                eta_color  = "red"
                status_str = f"[red]{status}[/red]"
            elif delay > 1:
                eta_color  = "yellow"
                status_str = f"[yellow]{status}[/yellow]"
            else:
                eta_color  = "green"
                status_str = f"[green]{status}[/green]"

            conf = arr.get("confidence", "medium")
            conf_str = {"high": "[green]●[/green]", "medium": "[yellow]◐[/yellow]", "low": "[red]○[/red]"}.get(conf, "")

            tbl.add_row(
                arr.get("route", "?"),
                arr.get("destination", "?"),
                arr.get("scheduled_time", "--:--"),
                f"[{eta_color}]{arr.get('predicted_time','--:--')}[/{eta_color}]",
                status_str,
                conf_str,
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = (
        f"[dim]Updated: {last_updated}   "
        f"GPS delay: [bold]{live_del:+.1f}m[/bold]   "
        f"{gps_indicator}[/dim]"
    )

    content = Text()
    content.append(f"  {footer}\n\n")

    return Panel(
        tbl,
        title=f"[bold white]  🚌  {stop_name.upper()}  [/bold white]",
        subtitle=footer,
        border_style="blue",
        padding=(1, 2),
    )


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run(api: str, stop_id: str, n: int):
    """Poll the board endpoint and refresh the display every POLL_SEC seconds."""
    console.clear()
    console.print(Panel.fit(
        f"[bold blue]Transit Display Board[/bold blue]\n"
        f"Stop: [bold]{stop_id}[/bold]  ·  API: {api}\n"
        f"Refreshing every {POLL_SEC}s",
        border_style="dim",
    ))

    async with aiohttp.ClientSession() as session:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                data = await fetch_board(session, api, stop_id, n)

                if data:
                    now       = datetime.now().strftime("%H:%M:%S")
                    panel     = render_board(data, now)
                    live.update(panel)
                else:
                    live.update(Panel(
                        "[red]Cannot reach API — retrying...[/red]",
                        title="[bold red]Connection Error[/bold red]",
                        border_style="red",
                    ))

                await asyncio.sleep(POLL_SEC)


def main():
    parser = argparse.ArgumentParser(description="Transit display board client")
    parser.add_argument("--stop", default="S001", help="Stop ID to display (e.g. S001)")
    parser.add_argument("--api",  default=DEFAULT_API, help="API base URL")
    parser.add_argument("--n",    default=6, type=int,  help="Number of arrivals to show")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.api, args.stop, args.n))
    except KeyboardInterrupt:
        console.print("\n[dim]Board stopped.[/dim]")


if __name__ == "__main__":
    main()
