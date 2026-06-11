"""
Week 14 — Train the Delay Prediction Model
Transit Optimizer | Phase 2

What this script does:
  1. Loads delay_features.csv (built in Week 13)
  2. Splits data into train / validation / test sets
  3. Trains three models in order of complexity:
       a. Baseline (predict the mean — sanity check)
       b. Linear Regression
       c. Random Forest Regressor
  4. Evaluates each with MAE, RMSE, and R²
  5. Plots feature importances (Random Forest)
  6. Saves the best model + feature list to data/delay_model.joblib

Key ML concepts covered:
  - Train / test split (why we need held-out data)
  - Baseline model (the floor your model must beat)
  - MAE vs RMSE (what each metric penalises)
  - Overfitting vs underfitting
  - Feature importance (which inputs matter most)
  - Model persistence with joblib

Run: python -m scripts.week14_model
"""

import sqlite3
import time
import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model    import LinearRegression, Ridge
from sklearn.ensemble        import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing   import StandardScaler
from sklearn.pipeline        import Pipeline
from sklearn.metrics         import mean_absolute_error, mean_squared_error, r2_score
from sklearn.dummy           import DummyRegressor

from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.columns import Columns
from rich         import box

console   = Console()
CSV_PATH  = Path("data/delay_features.csv")
DB_PATH   = Path("data/transit.db")
MODEL_OUT = Path("data/delay_model.joblib")
META_OUT  = Path("data/model_meta.json")

FEATURE_COLS = [
    "stop_sequence_norm",
    "hour",
    "is_rush_hour",
    "is_weekend",
    "day_of_week",
    "route_type",
    "n_stops_on_trip",
    "prior_stop_delay",
    "temp_deviation",
    "route_frequency",
]
TARGET = "delay_minutes"


# ── 1. Load & split ───────────────────────────────────────────────────────────

def load_and_split(path: Path):
    """
    Load CSV and produce train / val / test splits.

    Split strategy:
      80% train  — model learns from this
      10% val    — tune hyperparameters on this (we don't contaminate test)
      10% test   — final honest evaluation, touched ONCE at the very end

    Why not just train/test?
      If you tune hyperparameters on the test set you're overfitting to it.
      The val set is the "practice exam"; test is the "real exam".
    """
    df = pd.read_csv(path)
    X  = df[FEATURE_COLS].values
    y  = df[TARGET].values

    # First split: 80% train, 20% temp
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    # Second split: 50/50 of temp → val and test (each 10% of total)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42
    )

    console.print(
        f"[green]✓[/green] Split: "
        f"train={len(X_train):,}  val={len(X_val):,}  test={len(X_test):,}"
    )
    return X_train, X_val, X_test, y_train, y_val, y_test, df


# ── 2. Metrics ────────────────────────────────────────────────────────────────

def evaluate(name: str, model, X_tr, y_tr, X_val, y_val) -> dict:
    """Fit on train, score on val. Return metrics dict."""
    t0      = time.perf_counter()
    model.fit(X_tr, y_tr)
    fit_ms  = (time.perf_counter() - t0) * 1000

    y_pred  = model.predict(X_val)

    mae  = mean_absolute_error(y_val, y_pred)
    rmse = mean_squared_error(y_val, y_pred) ** 0.5
    r2   = r2_score(y_val, y_pred)

    return {
        "name":   name,
        "model":  model,
        "mae":    round(mae,  3),
        "rmse":   round(rmse, 3),
        "r2":     round(r2,   3),
        "fit_ms": round(fit_ms, 1),
        "y_pred": y_pred,
    }


# ── 3. Models ─────────────────────────────────────────────────────────────────

def build_models():
    """Return list of (name, sklearn estimator) pairs."""
    return [
        # Always train a dummy baseline first.
        # If your real model doesn't beat this, something is wrong.
        ("Baseline (mean)",
         DummyRegressor(strategy="mean")),

        # Linear Regression — fast, interpretable, assumes linear relationships.
        # Pipeline: StandardScaler normalises features first (important for LR).
        ("Linear Regression",
         Pipeline([
             ("scaler", StandardScaler()),
             ("model",  LinearRegression()),
         ])),

        # Ridge — Linear Regression + L2 regularisation.
        # Penalises large coefficients → less overfitting on correlated features.
        ("Ridge (α=1.0)",
         Pipeline([
             ("scaler", StandardScaler()),
             ("model",  Ridge(alpha=1.0)),
         ])),

        # Random Forest — ensemble of decision trees.
        # Handles non-linear relationships (e.g. rush hour spike).
        # n_estimators=100 trees, max_depth=8 prevents overfitting.
        ("Random Forest",
         RandomForestRegressor(
             n_estimators=100,
             max_depth=8,
             min_samples_leaf=10,
             random_state=42,
             n_jobs=-1,
         )),

        # Gradient Boosting — sequential trees, each correcting prior errors.
        # Often the best for tabular data but slower to train.
        ("Gradient Boosting",
         GradientBoostingRegressor(
             n_estimators=100,
             max_depth=4,
             learning_rate=0.1,
             random_state=42,
         )),
    ]


# ── 4. Cross-validation on the best model ────────────────────────────────────

def cross_validate_best(model, X_train, y_train) -> dict:
    """
    5-fold CV on training data — more reliable than a single val split.
    Each fold: 4/5 used for training, 1/5 for scoring. Repeat 5×, average.
    """
    scores = cross_val_score(
        model, X_train, y_train,
        cv=5, scoring="neg_mean_absolute_error", n_jobs=-1,
    )
    maes = -scores   # sklearn negates scores for maximisation
    return {
        "cv_mae_mean": round(maes.mean(), 3),
        "cv_mae_std":  round(maes.std(),  3),
    }


# ── 5. Feature importances ────────────────────────────────────────────────────

def print_feature_importance(rf_model, feature_cols: list):
    """Print Random Forest feature importances as a bar chart."""
    importances = rf_model.feature_importances_
    pairs = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)

    tbl = Table(
        title="Feature importances (Random Forest)",
        box=box.ROUNDED, header_style="bold cyan",
    )
    tbl.add_column("Feature",    min_width=22)
    tbl.add_column("Importance", justify="right", width=10)
    tbl.add_column("Bar")

    max_imp = pairs[0][1]
    for feat, imp in pairs:
        bar_len = int((imp / max_imp) * 30)
        bar     = "█" * bar_len
        color   = "green" if imp > 0.15 else ("yellow" if imp > 0.05 else "dim")
        tbl.add_row(feat, f"{imp:.4f}", f"[{color}]{bar}[/{color}]")

    console.print(tbl)


# ── 6. Comparison table ───────────────────────────────────────────────────────

def print_comparison(results: list[dict]):
    """Side-by-side model comparison."""
    tbl = Table(
        title="Model comparison (validation set)",
        box=box.ROUNDED, header_style="bold blue",
    )
    tbl.add_column("Model",        min_width=22)
    tbl.add_column("MAE",          justify="right", width=8)
    tbl.add_column("RMSE",         justify="right", width=8)
    tbl.add_column("R²",           justify="right", width=7)
    tbl.add_column("Train time",   justify="right", width=11)
    tbl.add_column("vs baseline",  justify="right", width=12)

    baseline_mae = results[0]["mae"]

    for r in results:
        pct_better = (baseline_mae - r["mae"]) / baseline_mae * 100
        if r["name"] == "Baseline (mean)":
            vs = "[dim]—[/dim]"
        elif pct_better > 0:
            vs = f"[green]+{pct_better:.1f}%[/green]"
        else:
            vs = f"[red]{pct_better:.1f}%[/red]"

        # Highlight best non-baseline model
        best_mae = min(x["mae"] for x in results[1:])
        is_best  = r["name"] != "Baseline (mean)" and r["mae"] == best_mae
        name_str = f"[bold]{r['name']}[/bold]" if is_best else r["name"]

        tbl.add_row(
            name_str,
            f"{r['mae']:.3f}",
            f"{r['rmse']:.3f}",
            f"{r['r2']:.3f}",
            f"{r['fit_ms']:.0f}ms",
            vs,
        )
    console.print(tbl)


# ── 7. Residual analysis ──────────────────────────────────────────────────────

def print_residuals(best: dict, y_val: np.ndarray):
    """Show distribution of prediction errors."""
    residuals = y_val - best["y_pred"]

    bins = [(-99,-5),(-5,-2),(-2,-1),(-1,0),(0,1),(1,2),(2,5),(5,99)]
    labels = ["< -5m", "-5→-2m", "-2→-1m", "-1→0m",
              "0→1m",  "1→2m",  "2→5m",  "> +5m"]

    tbl = Table(
        title=f"Residual distribution — {best['name']}",
        box=box.ROUNDED, header_style="bold magenta",
    )
    tbl.add_column("Error bucket")
    tbl.add_column("Count",   justify="right")
    tbl.add_column("% of val",justify="right")
    tbl.add_column("Bar")

    n = len(residuals)
    for (lo, hi), label in zip(bins, labels):
        count = int(((residuals > lo) & (residuals <= hi)).sum())
        pct   = count / n * 100
        bar   = "█" * int(pct / 2)
        color = "green" if -1 <= (lo+hi)/2 <= 1 else "yellow" if abs((lo+hi)/2) <= 3 else "red"
        tbl.add_row(label, str(count), f"{pct:.1f}%", f"[{color}]{bar}[/{color}]")

    console.print(tbl)
    console.print(
        f"[dim]Mean error: {residuals.mean():.3f}m  "
        f"| Errors within ±2 min: "
        f"{((residuals > -2) & (residuals < 2)).mean()*100:.1f}%[/dim]\n"
    )


# ── 8. Final test-set evaluation ─────────────────────────────────────────────

def final_test_eval(best_model, X_test, y_test) -> dict:
    """
    ONE-TIME evaluation on the held-out test set.
    This is the honest number — the model has never seen this data.
    """
    y_pred = best_model.predict(X_test)
    return {
        "test_mae":  round(mean_absolute_error(y_test, y_pred), 3),
        "test_rmse": round(mean_squared_error(y_test, y_pred) ** 0.5, 3),
        "test_r2":   round(r2_score(y_test, y_pred), 3),
    }


# ── 9. Predict helper (used by FastAPI in Week 16) ────────────────────────────

def predict_delay(model, stop_sequence_norm: float, hour: int,
                  is_rush_hour: int, is_weekend: int, day_of_week: int,
                  route_type: int, n_stops_on_trip: int,
                  prior_stop_delay: float, temp_deviation: float,
                  route_frequency: float) -> float:
    """
    Single-row prediction — the function FastAPI will call.
    Returns predicted delay in minutes (≥ 0).
    """
    X = np.array([[
        stop_sequence_norm, hour, is_rush_hour, is_weekend,
        day_of_week, route_type, n_stops_on_trip, prior_stop_delay,
        temp_deviation, route_frequency,
    ]])
    pred = model.predict(X)[0]
    return round(max(0.0, float(pred)), 2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    console.print(Panel.fit(
        "[bold blue]Transit Optimizer[/bold blue] — Week 14: Model Training\n"
        "[dim]Phase 2 | Delay prediction — Linear Regression → Random Forest[/dim]",
        border_style="blue",
    ))

    # Step 1 — load data
    console.rule("[bold]Step 1 — Load & split data[/bold]")
    X_train, X_val, X_test, y_train, y_val, y_test, df = load_and_split(CSV_PATH)
    console.print(f"  Features: {FEATURE_COLS}")
    console.print(f"  Target range: {y_train.min():.1f} – {y_train.max():.1f} min\n")

    # Step 2 — train all models
    console.rule("[bold]Step 2 — Train models[/bold]")
    models  = build_models()
    results = []

    for name, model in models:
        r = evaluate(name, model, X_train, y_train, X_val, y_val)
        console.print(
            f"  [green]✓[/green] {name:28s} "
            f"MAE={r['mae']:.3f}  RMSE={r['rmse']:.3f}  "
            f"R²={r['r2']:.3f}  [{r['fit_ms']:.0f}ms]"
        )
        results.append(r)

    # Step 3 — comparison table
    console.rule("[bold]Step 3 — Model comparison[/bold]")
    print_comparison(results)

    # Step 4 — pick best (lowest MAE, exclude baseline)
    best = min(results[1:], key=lambda x: x["mae"])
    console.print(
        f"\n[bold green]Best model:[/bold green] {best['name']}  "
        f"MAE={best['mae']}  RMSE={best['rmse']}  R²={best['r2']}\n"
    )

    # Step 5 — feature importance (Random Forest only)
    rf_result = next((r for r in results if "Random Forest" in r["name"]), None)
    if rf_result:
        console.rule("[bold]Step 4 — Feature importances[/bold]")
        # Get the raw RF from pipeline or directly
        rf_est = rf_result["model"]
        if hasattr(rf_est, "named_steps"):
            rf_est = rf_est.named_steps.get("model", rf_est)
        if hasattr(rf_est, "feature_importances_"):
            print_feature_importance(rf_est, FEATURE_COLS)

    # Step 6 — cross-validation on best model
    console.rule("[bold]Step 5 — Cross-validation (5-fold)[/bold]")
    cv = cross_validate_best(best["model"], X_train, y_train)
    console.print(
        f"  5-fold CV MAE: [bold]{cv['cv_mae_mean']}[/bold] ± {cv['cv_mae_std']} min\n"
        f"  [dim](Lower ± = more stable model across different data slices)[/dim]\n"
    )

    # Step 7 — residual analysis
    console.rule("[bold]Step 6 — Residual analysis[/bold]")
    print_residuals(best, y_val)

    # Step 8 — final test set evaluation (ONE TIME)
    console.rule("[bold]Step 7 — Final test-set evaluation[/bold]")
    test_metrics = final_test_eval(best["model"], X_test, y_test)
    console.print(Panel(
        f"  Test MAE:  [bold]{test_metrics['test_mae']}[/bold] min\n"
        f"  Test RMSE: [bold]{test_metrics['test_rmse']}[/bold] min\n"
        f"  Test R²:   [bold]{test_metrics['test_r2']}[/bold]\n\n"
        f"  [dim]Val MAE was {best['mae']} — test MAE is "
        f"{'similar ✓' if abs(test_metrics['test_mae'] - best['mae']) < 0.1 else 'higher (slight overfit)'}[/dim]",
        title="Honest final score (test set — seen for the first time)",
        border_style="green",
    ))

    # Step 9 — sample predictions
    console.rule("[bold]Step 8 — Sample predictions[/bold]")
    samples = [
        ("MG Road, rush hour, bus, mid-route",   0.5, 8,  1, 0, 0, 3, 6, 2.5, 0.3, 2.0),
        ("MG Road, off-peak, bus, first stop",   0.0, 14, 0, 0, 1, 3, 6, 0.0, 0.2, 2.0),
        ("Metro, rush hour, start of trip",      0.0, 8,  1, 0, 0, 1, 3, 0.0, 0.1, 3.0),
        ("Bus, bad weather, end of route",       1.0, 18, 1, 0, 2, 3, 6, 5.0, 3.5, 2.0),
        ("Weekend, off-peak, mid-route",         0.5, 13, 0, 1, 6, 3, 6, 1.2, 0.4, 2.0),
    ]
    pred_tbl = Table(
        title="Model predictions on hand-crafted scenarios",
        box=box.ROUNDED, header_style="bold yellow",
    )
    pred_tbl.add_column("Scenario",        min_width=36)
    pred_tbl.add_column("Predicted delay", justify="right")

    for label, *feats in samples:
        pred = predict_delay(best["model"], *feats)
        color = "red" if pred > 4 else ("yellow" if pred > 2 else "green")
        pred_tbl.add_row(label, f"[{color}]{pred} min[/{color}]")
    console.print(pred_tbl)

    # Step 10 — save model
    console.rule("[bold]Step 9 — Save model[/bold]")
    joblib.dump(best["model"], MODEL_OUT)
    size_kb = MODEL_OUT.stat().st_size / 1024
    console.print(
        f"[green]✓[/green] Model saved → [bold]{MODEL_OUT}[/bold] ({size_kb:.0f} KB)"
    )

    # Save metadata (used by FastAPI in Week 16)
    meta = {
        "model_name":    best["name"],
        "feature_cols":  FEATURE_COLS,
        "val_mae":       best["mae"],
        "val_rmse":      best["rmse"],
        "val_r2":        best["r2"],
        "test_mae":      test_metrics["test_mae"],
        "test_rmse":     test_metrics["test_rmse"],
        "test_r2":       test_metrics["test_r2"],
        "cv_mae_mean":   cv["cv_mae_mean"],
        "cv_mae_std":    cv["cv_mae_std"],
        "n_train":       len(X_train),
        "n_features":    len(FEATURE_COLS),
    }
    META_OUT.write_text(json.dumps(meta, indent=2))
    console.print(
        f"[green]✓[/green] Metadata saved → [bold]{META_OUT}[/bold]"
    )

    # Concept summary
    console.print(Panel(
        "[bold]MAE vs RMSE — what each metric penalises[/bold]\n\n"
        "  MAE (Mean Absolute Error) = average |predicted - actual|\n"
        "  → Treats all errors equally. Good for 'how wrong am I on average?'\n\n"
        "  RMSE (Root Mean Square Error) = √(average of squared errors)\n"
        "  → Penalises large errors heavily. A 10-min miss counts 100× more\n"
        "    than a 1-min miss. Use when big errors are especially bad.\n\n"
        "  R² = 1 - (variance unexplained / total variance)\n"
        "  → 1.0 = perfect, 0.0 = as good as predicting the mean.\n"
        "  → Negative = worse than predicting the mean.\n\n"
        "  [dim]For transit: MAE ≤ 1.5 min is production-grade.[/dim]",
        title="ML theory",
        border_style="dim",
    ))

    console.print(Panel(
        "[bold green]Week 14 complete![/bold green]\n\n"
        f"  Best model: [bold]{best['name']}[/bold]\n"
        f"  Val MAE:    {best['mae']} min  (predicts delay within ~{best['mae']} min on average)\n"
        f"  Test MAE:   {test_metrics['test_mae']} min  (honest held-out score)\n"
        f"  Test R²:    {test_metrics['test_r2']}  (explains {test_metrics['test_r2']*100:.0f}% of delay variance)\n\n"
        "  Model saved → [bold]data/delay_model.joblib[/bold]\n"
        "  Metadata  → [bold]data/model_meta.json[/bold]\n\n"
        "Next up → [bold]Week 15:[/bold] Hyperparameter tuning + model hardening\n"
        "Then     → [bold]Week 16:[/bold] FastAPI server — POST /predict-delay",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
