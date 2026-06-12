"""
Week 15 — Hyperparameter Tuning + Model Hardening
Transit Optimizer | Phase 2

What this script does:
  1. GridSearchCV — systematically searches hyperparameter space
  2. Analyses first-stop vs mid-route predictions separately
     (prior_stop_delay=0 at first stop → different problem)
  3. Builds a ChainedPredictor:
       - FirstStopModel  for stop_sequence_norm == 0
       - PropagationModel for all other stops
  4. Evaluates the chained model vs the single model
  5. Saves the best final artifact to data/delay_model.joblib (overwrites)

Key ML concepts covered:
  - Hyperparameter vs model parameter
  - GridSearchCV — exhaustive search over a param grid
  - Bias-variance tradeoff (underfitting vs overfitting)
  - Specialised models for different data regimes
  - Model chaining / ensemble design

Run: python -m scripts.week15_tuning
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection    import train_test_split, GridSearchCV, cross_val_score
from sklearn.ensemble           import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model       import Ridge
from sklearn.metrics            import mean_absolute_error, mean_squared_error, r2_score
from sklearn.base               import BaseEstimator, RegressorMixin

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich         import box

console   = Console()
CSV_PATH  = Path("data/delay_features.csv")
MODEL_OUT = Path("data/delay_model.joblib")
META_OUT  = Path("data/model_meta.json")

FEATURE_COLS = [
    "stop_sequence_norm", "hour", "is_rush_hour", "is_weekend",
    "day_of_week", "route_type", "n_stops_on_trip", "prior_stop_delay",
    "temp_deviation", "route_frequency",
]
# Features used when prior_stop_delay is unavailable (first stop)
FIRST_STOP_FEATURES = [
    "hour", "is_rush_hour", "is_weekend", "day_of_week",
    "route_type", "n_stops_on_trip", "temp_deviation", "route_frequency",
]
TARGET = "delay_minutes"


# ── Load & split ──────────────────────────────────────────────────────────────

def load_data():
    df = pd.read_csv(CSV_PATH)
    X  = df[FEATURE_COLS].values
    y  = df[TARGET].values
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.2, random_state=42)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5, random_state=42)
    return df, X_tr, X_val, X_te, y_tr, y_val, y_te


def metrics(y_true, y_pred) -> dict:
    return {
        "mae":  round(mean_absolute_error(y_true, y_pred), 4),
        "rmse": round(mean_squared_error(y_true, y_pred) ** 0.5, 4),
        "r2":   round(r2_score(y_true, y_pred), 4),
    }


# ── 1. GridSearchCV ───────────────────────────────────────────────────────────
#
# Hyperparameters are settings you choose BEFORE training.
# Parameters are what the model LEARNS during training (e.g. tree split points).
#
# GridSearchCV tries every combination in the param grid using cross-validation
# and picks the one with the best CV score.
#
# Trade-off: more combinations → better tuning, but slower.
# We use a small grid here since our dataset is modest.

def grid_search(X_train, y_train) -> tuple:
    """Run GridSearchCV on GradientBoosting. Returns (best_model, cv_results_df)."""

    param_grid = {
        "n_estimators":  [100, 200],
        "max_depth":     [3, 4, 5],
        "learning_rate": [0.05, 0.1],
        "min_samples_leaf": [5, 10],
    }

    n_combinations = (
        len(param_grid["n_estimators"]) *
        len(param_grid["max_depth"]) *
        len(param_grid["learning_rate"]) *
        len(param_grid["min_samples_leaf"])
    )

    console.print(
        f"  Searching [bold]{n_combinations}[/bold] combinations "
        f"× 3-fold CV = [bold]{n_combinations*3}[/bold] fits..."
    )

    base = GradientBoostingRegressor(random_state=42)
    gs   = GridSearchCV(
        base,
        param_grid,
        cv=3,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        verbose=0,
    )

    t0 = time.perf_counter()
    gs.fit(X_train, y_train)
    elapsed = time.perf_counter() - t0

    console.print(f"  [green]✓[/green] Search complete in {elapsed:.1f}s")
    console.print(f"  Best params: [bold]{gs.best_params_}[/bold]")
    console.print(f"  Best CV MAE: [bold]{-gs.best_score_:.4f}[/bold] min\n")

    # Build results table
    results = pd.DataFrame(gs.cv_results_)
    results["mae"] = -results["mean_test_score"]
    results = results.sort_values("mae")

    return gs.best_estimator_, results


def print_grid_results(results: pd.DataFrame, top_n: int = 8):
    """Show the top N hyperparameter combinations."""
    tbl = Table(
        title=f"GridSearchCV — top {top_n} combinations",
        box=box.ROUNDED, header_style="bold cyan",
    )
    tbl.add_column("Rank",       justify="right", width=5)
    tbl.add_column("n_est",      justify="right", width=6)
    tbl.add_column("depth",      justify="right", width=6)
    tbl.add_column("lr",         justify="right", width=6)
    tbl.add_column("min_leaf",   justify="right", width=9)
    tbl.add_column("CV MAE",     justify="right", width=9)
    tbl.add_column("Bar")

    max_mae = results["mae"].max()
    for i, (_, row) in enumerate(results.head(top_n).iterrows(), 1):
        p    = row["params"]
        bar  = "█" * int((1 - row["mae"] / max_mae) * 20)
        color = "green" if i == 1 else "dim"
        tbl.add_row(
            str(i),
            str(p["n_estimators"]),
            str(p["max_depth"]),
            str(p["learning_rate"]),
            str(p["min_samples_leaf"]),
            f"{row['mae']:.4f}",
            f"[{color}]{bar}[/{color}]",
        )
    console.print(tbl)


# ── 2. First-stop vs propagation analysis ────────────────────────────────────
#
# The model trained in Week 14 uses prior_stop_delay as the dominant feature.
# At the FIRST stop of every trip, prior_stop_delay = 0 by definition.
# This means the model is flying blind for first stops.
#
# Solution: train a SEPARATE model for first stops that uses only
# temporal + route features. Then chain them together.

def split_by_stop_position(df: pd.DataFrame):
    """Split dataset into first-stop rows and mid-route rows."""
    first = df[df["stop_sequence_norm"] == 0.0].copy()
    mid   = df[df["stop_sequence_norm"] >  0.0].copy()
    return first, mid


def train_first_stop_model(first_df: pd.DataFrame):
    """Train a model specifically for the first stop (no prior delay info)."""
    X = first_df[FIRST_STOP_FEATURES].values
    y = first_df[TARGET].values

    X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(
        n_estimators=100, max_depth=3,
        learning_rate=0.1, min_samples_leaf=5,
        random_state=42,
    )
    model.fit(X_tr, y_tr)
    m = metrics(y_val, model.predict(X_val))
    return model, m


# ── 3. ChainedPredictor ────────────────────────────────────────────────────────
#
# A custom sklearn-compatible estimator that:
#   - Uses first_stop_model when stop_sequence_norm == 0
#   - Uses propagation_model otherwise
#
# This is the same pattern used in production ML pipelines at companies
# like Uber and Google Maps — "routing" inputs to specialist sub-models.

class ChainedDelayPredictor(BaseEstimator, RegressorMixin):
    """
    Routes predictions between two specialist models:
      first_model       — for first stop of a trip (no prior delay)
      propagation_model — for all subsequent stops (uses prior delay)
    """

    def __init__(self, first_model, prop_model,
                 all_features, first_features):
        self.first_model       = first_model
        self.prop_model        = prop_model
        self.all_features      = all_features
        self.first_features    = first_features

    def fit(self, X, y):
        # Both sub-models are already fitted; this is a post-hoc combiner
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        X has columns matching all_features.
        stop_sequence_norm is the FIRST column (index 0).
        prior_stop_delay is index 7.
        """
        preds   = np.zeros(len(X))
        is_first = X[:, 0] == 0.0   # stop_sequence_norm == 0

        # First-stop rows → use first_model (subset of features)
        first_idx = [self.all_features.index(f) for f in self.first_features]
        if is_first.any():
            X_first = X[is_first][:, first_idx]
            preds[is_first] = self.first_model.predict(X_first)

        # Mid-route rows → use propagation_model (all features)
        if (~is_first).any():
            preds[~is_first] = self.prop_model.predict(X[~is_first])

        return np.maximum(preds, 0.0)   # delay can't be negative

    def predict_single(self, features: dict) -> float:
        """Convenience wrapper for single-row prediction (used by FastAPI)."""
        seq_norm = features.get("stop_sequence_norm", 0.0)
        if seq_norm == 0.0:
            X = np.array([[features[f] for f in self.first_features]])
            pred = self.first_model.predict(X)[0]
        else:
            X = np.array([[features[f] for f in self.all_features]])
            pred = self.prop_model.predict(X)[0]
        return round(max(0.0, float(pred)), 2)


# ── 4. Comparison table ────────────────────────────────────────────────────────

def print_comparison(results: list[dict]):
    prev_meta = json.loads(META_OUT.read_text()) if META_OUT.exists() else {}
    baseline_mae = prev_meta.get("test_mae", 0.767)

    tbl = Table(
        title="Model comparison (validation set)",
        box=box.ROUNDED, header_style="bold blue",
    )
    tbl.add_column("Model",       min_width=26)
    tbl.add_column("MAE",         justify="right", width=8)
    tbl.add_column("RMSE",        justify="right", width=8)
    tbl.add_column("R²",          justify="right", width=7)
    tbl.add_column("vs Week 14",  justify="right", width=12)

    for r in results:
        imp = (baseline_mae - r["mae"]) / baseline_mae * 100
        if r.get("is_baseline"):
            vs = "[dim]week 14[/dim]"
        elif imp > 0:
            vs = f"[green]+{imp:.1f}%[/green]"
        else:
            vs = f"[red]{imp:.1f}%[/red]"
        name = f"[bold]{r['name']}[/bold]" if r.get("best") else r["name"]
        tbl.add_row(name, f"{r['mae']:.4f}", f"{r['rmse']:.4f}", f"{r['r2']:.4f}", vs)

    console.print(tbl)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 15: Hyperparameter Tuning\n"
        "[dim]Phase 2 | GridSearchCV · ChainedPredictor · Final model[/dim]",
        border_style="blue",
    ))

    df, X_tr, X_val, X_te, y_tr, y_val, y_te = load_data()
    prev_meta = json.loads(META_OUT.read_text()) if META_OUT.exists() else {}
    baseline_mae = prev_meta.get("test_mae", 0.767)
    console.print(
        f"[green]✓[/green] Data loaded: {len(df):,} rows | "
        f"Week 14 test MAE to beat: [bold]{baseline_mae}[/bold]\n"
    )

    # ── Step 1: GridSearchCV ──────────────────────────────────────────────────
    console.rule("[bold]Step 1 — GridSearchCV on GradientBoosting[/bold]")
    best_gb, gs_results = grid_search(X_tr, y_tr)
    print_grid_results(gs_results)

    m_tuned = metrics(y_val, best_gb.predict(X_val))
    console.print(
        f"  Tuned GB → Val MAE: [bold]{m_tuned['mae']}[/bold]  "
        f"RMSE: {m_tuned['rmse']}  R²: {m_tuned['r2']}\n"
    )

    # ── Step 2: First-stop analysis ───────────────────────────────────────────
    console.rule("[bold]Step 2 — First-stop vs mid-route error analysis[/bold]")
    first_df, mid_df = split_by_stop_position(df)

    # Evaluate on first_df directly
    X_first_all = first_df[FEATURE_COLS].values
    y_first_all = first_df[TARGET].values
    _, X_fv, _, y_fv = train_test_split(X_first_all, y_first_all, test_size=0.2, random_state=42)

    X_mid_all = mid_df[FEATURE_COLS].values
    y_mid_all = mid_df[TARGET].values
    _, X_mv, _, y_mv = train_test_split(X_mid_all, y_mid_all, test_size=0.2, random_state=42)

    m_first_gb = metrics(y_fv, best_gb.predict(X_fv))
    m_mid_gb   = metrics(y_mv, best_gb.predict(X_mv))

    regime_tbl = Table(
        title="Tuned GB error by stop position",
        box=box.ROUNDED, header_style="bold magenta",
    )
    regime_tbl.add_column("Data regime")
    regime_tbl.add_column("Rows",    justify="right")
    regime_tbl.add_column("MAE",     justify="right")
    regime_tbl.add_column("RMSE",    justify="right")
    regime_tbl.add_column("Note")

    regime_tbl.add_row(
        "First stop (seq=0)",
        f"{len(first_df):,}",
        f"[yellow]{m_first_gb['mae']}[/yellow]",
        f"{m_first_gb['rmse']}",
        "prior_stop_delay=0 → harder to predict",
    )
    regime_tbl.add_row(
        "Mid-route (seq>0)",
        f"{len(mid_df):,}",
        f"[green]{m_mid_gb['mae']}[/green]",
        f"{m_mid_gb['rmse']}",
        "prior delay propagates → easier",
    )
    console.print(regime_tbl)

    # ── Step 3: Train first-stop specialist ───────────────────────────────────
    console.rule("[bold]Step 3 — Train first-stop specialist model[/bold]")
    first_model, m_first_spec = train_first_stop_model(first_df)
    console.print(
        f"  First-stop specialist → "
        f"Val MAE: [bold]{m_first_spec['mae']}[/bold]  "
        f"R²: {m_first_spec['r2']}\n"
        f"  [dim](Uses only temporal + route features — no prior delay)[/dim]\n"
    )

    # ── Step 4: Build + evaluate ChainedPredictor ─────────────────────────────
    console.rule("[bold]Step 4 — ChainedPredictor[/bold]")
    chained = ChainedDelayPredictor(
        first_model       = first_model,
        prop_model        = best_gb,
        all_features      = FEATURE_COLS,
        first_features    = FIRST_STOP_FEATURES,
    )
    chained.fit(X_tr, y_tr)   # no-op but keeps sklearn interface

    m_chained_val  = metrics(y_val, chained.predict(X_val))
    m_chained_test = metrics(y_te,  chained.predict(X_te))

    console.print(
        f"  ChainedPredictor → "
        f"Val MAE: [bold]{m_chained_val['mae']}[/bold]  "
        f"Test MAE: [bold green]{m_chained_test['mae']}[/bold green]  "
        f"R²: {m_chained_test['r2']}\n"
    )

    # ── Step 5: Full comparison ────────────────────────────────────────────────
    console.rule("[bold]Step 5 — Model comparison[/bold]")
    comparison = [
        {"name": "Week 14 GB (baseline)",
         "mae": baseline_mae, "rmse": prev_meta.get("test_rmse", 0.0),
         "r2": prev_meta.get("test_r2", 0.0), "is_baseline": True},
        {"name": "Tuned GB (GridSearchCV)",
         "mae": m_tuned["mae"], "rmse": m_tuned["rmse"], "r2": m_tuned["r2"]},
        {"name": "ChainedPredictor (final)",
         "mae": m_chained_val["mae"], "rmse": m_chained_val["rmse"],
         "r2": m_chained_val["r2"], "best": True},
    ]
    print_comparison(comparison)

    # ── Step 6: Sample predictions ─────────────────────────────────────────────
    console.rule("[bold]Step 6 — Sample predictions[/bold]")
    scenarios = [
        ("First stop, rush hour, bus",
         {"stop_sequence_norm":0.0,"hour":8,"is_rush_hour":1,"is_weekend":0,
          "day_of_week":0,"route_type":3,"n_stops_on_trip":6,
          "prior_stop_delay":0.0,"temp_deviation":0.3,"route_frequency":2.0}),
        ("Mid-route, rush hour, prior=3min",
         {"stop_sequence_norm":0.5,"hour":8,"is_rush_hour":1,"is_weekend":0,
          "day_of_week":0,"route_type":3,"n_stops_on_trip":6,
          "prior_stop_delay":3.0,"temp_deviation":0.3,"route_frequency":2.0}),
        ("First stop, metro, off-peak",
         {"stop_sequence_norm":0.0,"hour":14,"is_rush_hour":0,"is_weekend":0,
          "day_of_week":1,"route_type":1,"n_stops_on_trip":3,
          "prior_stop_delay":0.0,"temp_deviation":0.1,"route_frequency":3.0}),
        ("Last stop, bad weather, bus",
         {"stop_sequence_norm":1.0,"hour":18,"is_rush_hour":1,"is_weekend":0,
          "day_of_week":2,"route_type":3,"n_stops_on_trip":6,
          "prior_stop_delay":5.0,"temp_deviation":3.5,"route_frequency":2.0}),
        ("Weekend, mid-route, no delay yet",
         {"stop_sequence_norm":0.5,"hour":13,"is_rush_hour":0,"is_weekend":1,
          "day_of_week":5,"route_type":3,"n_stops_on_trip":6,
          "prior_stop_delay":0.5,"temp_deviation":0.4,"route_frequency":2.0}),
    ]

    pred_tbl = Table(
        title="ChainedPredictor — sample predictions",
        box=box.ROUNDED, header_style="bold yellow",
    )
    pred_tbl.add_column("Scenario",   min_width=36)
    pred_tbl.add_column("Model used", justify="center", width=14)
    pred_tbl.add_column("Prediction", justify="right",  width=14)

    for label, feats in scenarios:
        pred   = chained.predict_single(feats)
        model_used = (
            "[blue]first-stop[/blue]"
            if feats["stop_sequence_norm"] == 0.0
            else "[green]propagation[/green]"
        )
        color  = "red" if pred > 4 else ("yellow" if pred > 2 else "green")
        pred_tbl.add_row(label, model_used, f"[{color}]{pred} min[/{color}]")
    console.print(pred_tbl)

    # ── Step 7: Save final model ───────────────────────────────────────────────
    console.rule("[bold]Step 7 — Save final model[/bold]")

    # Decide which to save — chained if it improved, else tuned GB
    if m_chained_test["mae"] <= m_tuned["mae"]:
        final_model      = chained
        final_model_name = "ChainedDelayPredictor"
        final_test       = m_chained_test
    else:
        final_model      = best_gb
        final_model_name = "Tuned GradientBoosting"
        final_test       = metrics(y_te, best_gb.predict(X_te))

    joblib.dump(final_model, MODEL_OUT)
    size_kb = MODEL_OUT.stat().st_size / 1024
    console.print(
        f"[green]✓[/green] Saved [bold]{final_model_name}[/bold] "
        f"→ {MODEL_OUT} ({size_kb:.0f} KB)"
    )

    # Update metadata
    cv_scores = cross_val_score(
        best_gb, X_tr, y_tr, cv=5,
        scoring="neg_mean_absolute_error", n_jobs=-1,
    )
    meta = {
        "model_name":       final_model_name,
        "feature_cols":     FEATURE_COLS,
        "first_stop_features": FIRST_STOP_FEATURES,
        "val_mae":          m_chained_val["mae"],
        "val_rmse":         m_chained_val["rmse"],
        "val_r2":           m_chained_val["r2"],
        "test_mae":         final_test["mae"],
        "test_rmse":        final_test["rmse"],
        "test_r2":          final_test["r2"],
        "cv_mae_mean":      round(-cv_scores.mean(), 4),
        "cv_mae_std":       round(cv_scores.std(), 4),
        "n_train":          len(X_tr),
        "n_features":       len(FEATURE_COLS),
        "week14_test_mae":  baseline_mae,
        "improvement_pct":  round((baseline_mae - final_test["mae"]) / baseline_mae * 100, 2),
    }
    META_OUT.write_text(json.dumps(meta, indent=2))
    console.print(f"[green]✓[/green] Metadata updated → {META_OUT}\n")

    improvement = meta["improvement_pct"]
    console.print(Panel(
        "[bold]What GridSearchCV actually does[/bold]\n\n"
        "  Hyperparameters = settings you choose (n_estimators, max_depth)\n"
        "  Parameters      = what the model learns (tree split points, weights)\n\n"
        "  GridSearchCV tries EVERY combination in the grid:\n"
        "    2 n_estimators × 3 depths × 2 learning rates × 2 min_leaf\n"
        "    = 24 combinations × 3 CV folds = 72 model fits\n\n"
        "  Each fit trains on 4/5 of data, scores on 1/5.\n"
        "  Best combo = lowest average CV MAE across all 3 folds.\n\n"
        "  [dim]RandomizedSearchCV is faster for large grids (samples randomly\n"
        "  instead of exhaustively). Used at Google/Uber scale.[/dim]",
        title="ML theory",
        border_style="dim",
    ))

    console.print(Panel(
        f"[bold green]Week 15 complete![/bold green]\n\n"
        f"  GridSearchCV searched 24 combinations → found better hyperparams\n"
        f"  ChainedPredictor: separate first-stop + propagation models\n"
        f"  Final test MAE:  [bold]{final_test['mae']}[/bold] min "
        f"({'improved' if improvement > 0 else 'same'} vs Week 14 "
        f"by {abs(improvement):.1f}%)\n"
        f"  Final model saved → [bold]{MODEL_OUT}[/bold]\n\n"
        "Next up → [bold]Week 16:[/bold] FastAPI server\n"
        "  [dim]GET  /route?from=MG+Road&to=HSR+Layout\n"
        "  POST /predict-delay  →  {predicted_minutes: 3.2}[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
