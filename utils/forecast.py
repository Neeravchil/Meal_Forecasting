"""
Pure-Python GBT scorer — reads Spark MLlib GBTRegressionModel Parquet files.
No Java / PySpark runtime required.

Key insight: tree 0 is the initial-prediction tree and carries weight 1.0;
all subsequent trees carry the stepSize weight (0.1).
Weights are read from treesMetadata/part-*.parquet.
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ── Model accuracy constants (from test set in notebook) ────────────────────
LUNCH_RMSE     = 0.0292   # 2.92 pp
BREAKFAST_RMSE = 0.0299   # 2.99 pp

# ── Feature columns — must match VectorAssembler order used during training ─
BASE_FEATURES = [
    "MONTH", "YEAR", "ENROLLMENT",
    "absence_rate", "absence_rate_lag_1", "absence_rate_roll3",
    "weighted_absence_rate", "pct_full_absence", "pct_half_absence",
    "pct_excused", "pct_mental_health_day",
    "pct_female", "pct_male",
    "pct_free_reduced_lunch", "pct_direct_cert", "pct_reduced_lunch",
]
LUNCH_SPECIFIC = [
    "lunch_lag_1", "lunch_roll3", "lunch_mom_pct",
    "lunch_part_lag_1", "lunch_part_roll3",
]
BREAKFAST_SPECIFIC = [
    "breakfast_lag_1", "breakfast_roll3",
]

FEATURES_LUNCH     = BASE_FEATURES + LUNCH_SPECIFIC        # 21 features, indices 0-20
FEATURES_BREAKFAST = BASE_FEATURES + BREAKFAST_SPECIFIC    # 18 features, indices 0-17


# ── Tree I/O ─────────────────────────────────────────────────────────────────
def _read_trees_and_weights(model_dir: str) -> tuple[dict, dict]:
    """Load all 100 trees and their per-tree weights from a Spark GBT model dir."""
    data_files = sorted(Path(model_dir).glob("data/part-*.parquet"))
    if not data_files:
        raise FileNotFoundError(f"No Parquet data files found in {model_dir}/data/")

    node_df = pd.concat([pd.read_parquet(f) for f in data_files], ignore_index=True)

    trees: dict[int, dict[int, dict]] = {}
    for _, row in node_df.iterrows():
        tid = int(row["treeID"])
        nd  = dict(row["nodeData"])
        if tid not in trees:
            trees[tid] = {}
        trees[tid][int(nd["id"])] = nd

    wfiles = sorted(Path(model_dir).glob("treesMetadata/part-*.parquet"))
    wmeta  = pd.concat([pd.read_parquet(f) for f in wfiles], ignore_index=True)
    weights: dict[int, float] = {int(r["treeID"]): float(r["weights"])
                                  for _, r in wmeta.iterrows()}
    return trees, weights


@st.cache_resource(show_spinner="Loading GBT models…")
def load_gbt_models() -> tuple[dict, dict, dict, dict]:
    """Load lunch and breakfast GBT models once per server start.

    Returns (lunch_trees, lunch_weights, breakfast_trees, breakfast_weights).
    """
    lt, lw = _read_trees_and_weights("gbt_lunch_participation")
    bt, bw = _read_trees_and_weights("gbt_breakfast_participation")
    return lt, lw, bt, bw


# ── Tree traversal ────────────────────────────────────────────────────────────
def _traverse(nodes: dict[int, dict], fvec: np.ndarray) -> float:
    node = nodes[0]
    while True:
        lc = int(node["leftChild"])
        if lc == -1:
            return float(node["prediction"])
        sp   = node["split"]
        fi   = int(sp["featureIndex"])
        cats = sp["leftCategoriesOrThreshold"]
        th   = float(cats[0]) if hasattr(cats, "__len__") and len(cats) > 0 else 0.0
        node = nodes[lc] if fvec[fi] <= th else nodes[int(node["rightChild"])]


def score_gbt(trees: dict, weights: dict, fvec: np.ndarray) -> float:
    """Σ  tree_i(x) × weight_i   for all trees."""
    return sum(_traverse(trees[t], fvec) * weights[t] for t in trees)


# ── Feature engineering helpers ───────────────────────────────────────────────
def _roll3_mean(lst: list) -> float:
    vals = [v for v in lst[-3:] if v is not None and pd.notna(v)]
    return float(np.mean(vals)) if vals else 0.0


def _safe(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return default if np.isnan(v) else v
    except (TypeError, ValueError):
        return default


def _build_forecast_row(school_data: pd.DataFrame, month: int, year: int,
                        hist: dict) -> dict:
    """Construct the 21-feature dict for one forecast month.

    `hist` is a rolling buffer maintained by `gbt_forecast`:
        hist["lunch_part"]    — LUNCH_PARTICIPATION values (proportions)
        hist["lunch_avg"]     — LUNCH_AVERAGE_PER_DAY values
        hist["breakfast_avg"] — BREAKFAST_AVERAGE_PER_DAY values
        hist["absence"]       — absence_rate values
    """
    latest = school_data.iloc[-1]

    def s(col, default=0.0):
        return _safe(latest.get(col, default), default)

    la_lag1  = _safe(hist["lunch_avg"][-1])     if hist["lunch_avg"]      else s("LUNCH_AVERAGE_PER_DAY")
    lp_lag1  = _safe(hist["lunch_part"][-1])    if hist["lunch_part"]     else s("LUNCH_PARTICIPATION")
    ba_lag1  = _safe(hist["breakfast_avg"][-1]) if hist["breakfast_avg"]  else s("BREAKFAST_AVERAGE_PER_DAY")
    abs_lag1 = _safe(hist["absence"][-1])       if hist["absence"]        else s("absence_rate")

    # Month-over-month change in LUNCH_AVERAGE_PER_DAY (fraction, not %)
    if len(hist["lunch_avg"]) >= 2 and hist["lunch_avg"][-2] and hist["lunch_avg"][-2] != 0:
        mom_pct = (_safe(hist["lunch_avg"][-1]) - _safe(hist["lunch_avg"][-2])) / _safe(hist["lunch_avg"][-2])
    else:
        mom_pct = 0.0

    # For forecast months, carry absence_rate forward from the most recent known value
    abs_curr = abs_lag1

    return {
        "MONTH":                  float(month),
        "YEAR":                   float(year),
        "ENROLLMENT":             s("ENROLLMENT"),
        "absence_rate":           abs_curr,
        "absence_rate_lag_1":     abs_lag1,
        "absence_rate_roll3":     _roll3_mean(hist["absence"]),
        "weighted_absence_rate":  s("weighted_absence_rate", abs_curr),
        "pct_full_absence":       s("pct_full_absence"),
        "pct_half_absence":       s("pct_half_absence"),
        "pct_excused":            s("pct_excused"),
        "pct_mental_health_day":  s("pct_mental_health_day"),
        "pct_female":             s("pct_female", 0.5),
        "pct_male":               s("pct_male", 0.5),
        "pct_free_reduced_lunch": s("pct_free_reduced_lunch"),
        "pct_direct_cert":        s("pct_direct_cert"),
        "pct_reduced_lunch":      s("pct_reduced_lunch"),
        # Lunch-specific
        "lunch_lag_1":            la_lag1,
        "lunch_roll3":            _roll3_mean(hist["lunch_avg"]),
        "lunch_mom_pct":          float(mom_pct),
        "lunch_part_lag_1":       lp_lag1,
        "lunch_part_roll3":       _roll3_mean(hist["lunch_part"]),
        # Breakfast-specific
        "breakfast_lag_1":        ba_lag1,
        "breakfast_roll3":        _roll3_mean(hist["breakfast_avg"]),
    }


# ── Aggregate forecast (district, network, or any school subset) ──────────────
@st.cache_data(ttl=3600, show_spinner=False)
def aggregate_gbt_forecast(df) -> tuple[list[float], list[float]]:
    """3-month GBT forecast for any group of schools.

    Averages all records to one row per month, then runs gbt_forecast on that
    aggregated series.  Works for district-wide, a single network, or any
    filtered subset.  Returns (lunch_preds, breakfast_preds) in proportion units (0–1).
    """
    _numeric = [c for c in [
        "ENROLLMENT", "LUNCH_PARTICIPATION", "BREAKFAST_PARTICIPATION",
        "LUNCH_AVERAGE_PER_DAY", "BREAKFAST_AVERAGE_PER_DAY",
        "absence_rate", "weighted_absence_rate",
        "pct_full_absence", "pct_half_absence",
        "pct_excused", "pct_mental_health_day",
        "pct_female", "pct_male",
        "pct_free_reduced_lunch", "pct_direct_cert", "pct_reduced_lunch",
    ] if c in df.columns]

    agg: dict = {c: "mean" for c in _numeric}
    agg["MONTH"] = "first"
    agg["YEAR"]  = "first"

    aggregated = (
        df.groupby("MONTH_START")
        .agg(agg)
        .reset_index()
        .sort_values("MONTH_START")
        .reset_index(drop=True)
    )
    aggregated["SCHOOL_NAME"] = "_aggregate_"

    return gbt_forecast(aggregated, n_ahead=3)


# ── Main forecast entry point ─────────────────────────────────────────────────
def gbt_forecast(
    school_data: pd.DataFrame,
    n_ahead: int = 3,
    part_shift_pp: float = 0.0,
    absence_shift_pp: float = 0.0,
) -> tuple[list[float], list[float]]:
    """Iteratively forecast `n_ahead` months using the real GBT models.

    Returns (lunch_preds, breakfast_preds) in **proportion units** (0–1).

    What-if shifts (pp) adjust the first forecast month's lag-1 inputs so the
    model re-scores with the user's hypothetical scenario.
    """
    lt, lw, bt, bw = load_gbt_models()

    sd = school_data.sort_values("MONTH_START").reset_index(drop=True)

    enrollment = _safe(sd.iloc[-1]["ENROLLMENT"])

    hist: dict[str, list] = {
        "lunch_part":    sd["LUNCH_PARTICIPATION"].tolist(),
        "lunch_avg":     sd["LUNCH_AVERAGE_PER_DAY"].tolist(),
        "breakfast_avg": sd["BREAKFAST_AVERAGE_PER_DAY"].tolist(),
        "absence":       sd["absence_rate"].tolist(),
    }

    # Convert pp shifts → proportion
    part_shift   = part_shift_pp   / 100.0
    absence_shift = absence_shift_pp / 100.0

    forecast_schedule = [(4, 2026), (5, 2026), (6, 2026)]
    lunch_preds:     list[float] = []
    breakfast_preds: list[float] = []

    for i, (month, year) in enumerate(forecast_schedule[:n_ahead]):
        row = _build_forecast_row(sd, month, year, hist)

        # Apply what-if adjustments to the first forecast month only
        if i == 0 and (part_shift_pp != 0.0 or absence_shift_pp != 0.0):
            row["lunch_part_lag_1"]   = max(0.0, row["lunch_part_lag_1"]   + part_shift)
            row["absence_rate"]       = max(0.0, row["absence_rate"]       + absence_shift)
            row["absence_rate_lag_1"] = max(0.0, row["absence_rate_lag_1"] + absence_shift)

        fvec_l = np.array([_safe(row[f]) for f in FEATURES_LUNCH],     dtype=np.float64)
        fvec_b = np.array([_safe(row[f]) for f in FEATURES_BREAKFAST],  dtype=np.float64)

        lp = float(np.clip(score_gbt(lt, lw, fvec_l), 0.0, 1.5))
        bp = float(np.clip(score_gbt(bt, bw, fvec_b), 0.0, 1.5))

        lunch_preds.append(lp)
        breakfast_preds.append(bp)

        # Update rolling history so the next month can use these as lag/roll inputs
        hist["lunch_part"].append(lp)
        hist["lunch_avg"].append(lp * enrollment)
        hist["breakfast_avg"].append(bp * enrollment)
        hist["absence"].append(row["absence_rate"])

    return lunch_preds, breakfast_preds
