"""
scripts/display_board.py — Upgrade 2: Bus Stop Display Board Simulator
Simulates a Raspberry Pi-powered LED/LCD display board at a bus stop.
Polls GET /live-delays/{stop_id} and displays eta info in terminal.

Run: python3 -m scripts.display_board --stop S003
"""

import sys
import argparse
import asyncio
import aiohttp
import time
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

console = Console()
API_URL = "http://localhost:8000/live-delays"

async def fetch_delay(session, stop_id: str) -> dict:
    url = f"{API_URL}/{stop_id}"
    try:
        async with session.get(url, timeout=4) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 404:
                return {"error": f"Stop {stop_id} not found"}
            else:
                return {"error": f"API error: status {resp.status}"}
    except Exception as e:
        return {"error": f"Failed to connect to API: {str(e)}"}

def make_display(stop_id: str, data: dict, status: str) -> Panel:
    # Retro LCD/LED Theme: Green on Black
    time_str = datetime.now().strftime("%H:%M:%S")
    
    if "error" in data:
        lcd_text = Text()
        lcd_text.append(f"╔════════════════════════════════════════════╗\n", style="bold red")
        lcd_text.append(f"║             SYSTEM ERROR                   ║\n", style="bold red")
        lcd_text.append(f"║  {data['error'][:38].center(42)}║\n", style="yellow")
        lcd_text.append(f"║  RECONNECTING...                           ║\n", style="dim yellow")
        lcd_text.append(f"╚════════════════════════════════════════════╝\n", style="bold red")
        return Panel(lcd_text, title=f"[red]LCD Board: {stop_id} (OFFLINE)[/red]", border_style="red", expand=False)

    stop_name = data.get("stop_name", stop_id)
    live_delay = data.get("live_delay_min")
    trend_delay = data.get("trend_delay_min")
    has_live = data.get("has_live_data", False)
    
    lcd_text = Text()
    lcd_text.append(f" {stop_name.upper()} STATION ".center(44, "░") + "\n\n", style="bold green")
    
    if has_live and live_delay is not None:
        delay_val = float(live_delay)
        if delay_val > 0:
            status_text = f"LATE (+{delay_val:.1f} Min)"
            status_style = "bold red"
        elif delay_val < 0:
            status_text = f"EARLY ({delay_val:.1f} Min)"
            status_style = "bold cyan"
        else:
            status_text = "ON TIME"
            status_style = "bold green"
            
        lcd_text.append("  NEXT BUS:  ", style="bold white")
        lcd_text.append(f"{status_text.ljust(25)}", style=status_style)
        lcd_text.append(" [LIVE] \n", style="blink bold red" if status == "connected" else "dim red")
        
        trend_val = float(trend_delay) if trend_delay is not None else delay_val
        trend_dir = "↑ worsening" if trend_val > delay_val else "↓ improving" if trend_val < delay_val else "→ stable"
        lcd_text.append("  TREND:     ", style="bold white")
        lcd_text.append(f"Average {trend_val:+.1f}m ({trend_dir})\n", style="yellow")
    else:
        lcd_text.append("  NEXT BUS:  ", style="bold white")
        lcd_text.append("NO LIVE DATA AVAILABLE     ", style="dim yellow")
        lcd_text.append(" [SIM] \n", style="bold blue")
        lcd_text.append("  SCHEDULED  Check timetable for ETA          \n", style="dim white")
        
    lcd_text.append("\n" + f" {time_str} ".center(44, "═"), style="bold green")
    
    return Panel(
        lcd_text, 
        title=f"[green]LCD Board: {stop_id}[/green]", 
        border_style="green", 
        expand=False,
        subtitle="[dim]Powered by Raspberry Pi & Transit API[/dim]"
    )

async def main():
    parser = argparse.ArgumentParser(description="Simulate bus stop display board")
    parser.add_argument("--stop", default="S003", help="Stop ID to poll")
    parser.add_argument("--interval", type=int, default=3, help="Polling interval in seconds")
    args = parser.parse_args()
    
    console.print(f"[bold yellow]Starting Display Board Simulator for Stop: {args.stop}...[/bold yellow]")
    
    async with aiohttp.ClientSession() as session:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                try:
                    data = await fetch_delay(session, args.stop)
                    board = make_display(args.stop, data, "connected")
                except Exception as e:
                    board = make_display(args.stop, {"error": f"Connection lost: {str(e)}"}, "disconnected")
                
                live.update(board)
                await asyncio.sleep(args.interval)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Display Board Simulator stopped.[/yellow]")
