# Display Board — Upgrade 2

Two ways to deploy a live bus stop display board powered by your API.

## Option A — Web board (easiest)

Open `board.html` in any browser:

```
board.html?stop=S001&api=https://your-railway-url.railway.app
```

Works on:
- Any browser on a Raspberry Pi
- Android TV (open in Chrome)
- Fire Stick (Silk Browser)
- Smart TV with built-in browser
- Chromium in kiosk mode

### Kiosk mode on Raspberry Pi:
```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  "file:///home/pi/board.html?stop=S001&api=https://your-api.railway.app"
```

## Option B — Terminal board (Python)

```bash
pip install rich aiohttp
python display_board/board_client.py --stop S001 --api http://localhost:8000
```

## API Endpoints used

| Endpoint | What it does |
|---|---|
| `GET /board/{stop_id}` | Next 4-6 arrivals with predicted ETA |
| `GET /live-delays/{stop_id}` | Raw live delay in minutes |
| `WS /ws/board/{stop_id}` | Push update when delay changes |

## URL parameters (board.html)

| Param | Default | Description |
|---|---|---|
| `stop` | `S001` | Stop ID (from GET /stops) |
| `api` | `http://localhost:8000` | Your Railway API URL |
| `refresh` | `30` | Poll interval in seconds |
