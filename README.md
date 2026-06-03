# Transit Optimizer 🚇

Welcome to the **Transit Optimizer**! This smart-city project is designed to load, analyze, query, and optimize transit networks. 

---

## 📅 Phase 1: Week 1 — GTFS Data Explorer

Week 1 focus is on loading standard General Transit Feed Specification (GTFS) files into memory using `pandas` and displaying a high-level summary of the network using the `rich` library.

### 📁 Project Structure

```
Transit system/
├── data/
│   └── gtfs/             # General Transit Feed Specification sources
│       ├── routes.txt    # Transit routes (Purple Metro, Green Metro, etc.)
│       ├── stops.txt     # Latitudes, longitudes, and names of transit stops
│       ├── stop_times.txt# Trip sequence arrival and departure events
│       └── trips.txt     # List of trips linked to routes
├── scripts/
│   └── week1_explore.py  # Python script to load and visualize GTFS network
├── tests/                # Automated unit and integration tests
├── logs/                 # Operational log records
├── requirements.txt      # Python dependencies (pandas, rich)
├── README.md             # Project documentation (this file)
└── .gitignore            # Git exclusions
```

---

## 🚀 Quick Start

### 1. Pre-requisites
Ensure you have Python 3.8+ installed on your machine.

### 2. Set Up Virtual Environment (Optional but Recommended)
```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
```

### 3. Install Dependencies
Install pandas and rich using pip:
```bash
pip install -r requirements.txt
```

### 4. Run the Explorer
Execute the Python exploration script to view the transit statistics and network insights:
```bash
python scripts/week1_explore.py
```

---

## 📊 Network Insights Generated

The Week 1 explore script computes and presents the following:
* **Network Summary**: Counts of total stops, routes, trips, and stop events.
* **Stop Samples**: Details of locations and coordinate pairs.
* **Routes Listing**: Details and transportation modes (Metro, Bus, etc.).
* **Route Drill-down**: Complete sequence of stops, arrival, and departure times for a sample route.
* **Fun Facts**: Most visited stops, average stops per trip, and the busiest route.

---

## 🔮 Next Steps
* **Week 2**: Load GTFS datasets into SQLite databases and construct expressive SQL queries to explore the network.
* **Week 3**: Formulate transit network topology as a Directed Graph (DiGraph) for routing engines.
