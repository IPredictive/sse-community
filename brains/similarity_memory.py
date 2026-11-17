"""Nearest-neighbour market memory using only matured historical predictions.

Similarity is a decision-support signal, not a causal claim. Historical rows
must have a known next-session outcome before they can influence current weights.
"""
import json
import math
from pathlib import Path

import pandas as pd
from db import load_daily, load_scored

PATH = Path(__file__).parent.parent / "data" / "similarity_memory.json"
FEATURE_SCALES = {
    "ret_1d": 0.012,
    "ret_5d": 0.030,
    "ret_20d": 0.060,
    "vol_20d": 0.015,
    "range_1d": 0.025,
    "volume_ratio": 0.75,
}
MIN_NEIGHBORS = 8
MAX_NEIGHBORS = 30
MIN_SIMILARITY = 0.42
MAX_ADJUSTMENT = 0.03

def _feature_frame():
    df = load_daily()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.sort_values("date").copy().reset_index(drop=True)
    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    ret = close.pct_change()
    baseline = volume.shift(1).rolling(20, min_periods=5).median()
    frame = pd.DataFrame({
        "base_date": df["date"].astype(str).str[:10],
        "ret_1d": ret,
        "ret_5d": close.pct_change(5),
        "ret_20d": close.pct_change(20),
        "vol_20d": ret.rolling(20, min_periods=10).std(),
        "range_1d": (high - low) / close.shift(1),
        "volume_ratio": volume / baseline.replace(0, float("nan")),
    })
    frame = frame.replace([float("inf"), -float("inf")], float("nan"))
    frame["volume_ratio"] = frame["volume_ratio"].fillna(1.0)
    return frame

def _similarity(a, b):
    total = 0.0
    count = 0
    for key, scale in FEATURE_SCALES.items():
        av, bv = a.get(key), b.get(key)
        if pd.isna(av) or pd.isna(bv):
            continue
        delta = (float(av) - float(bv)) / scale
        total += min(delta * delta, 25.0)
        count += 1
    if count < 4:
        return 0.0
    distance = math.sqrt(total / count)
    return math.exp(-0.5 * distance)

def _matched_rows():
    scored = load_scored()
    features = _feature_frame()
    if scored is None or scored.empty or features.empty:
        return pd.DataFrame(), None
    scored = scored.copy()
    scored["base_date"] = scored["base_date"].astype(str).str[:10]
    merged = scored.merge(features, on="base_date", how="inner")
    current = features.iloc[-1].to_dict()
    # Only matured rows from earlier sessions are eligible; today's forecast is excluded.
    merged = merged[merged["base_date"] < str(current["base_date"])]
    return merged, current

def build_similarity_memory():
    rows, current = _matched_rows()
    if current is None or rows.empty:
        return {"as_of": None if current is None else current.get("base_date"),
                "matched_samples": 0, "brains": {}, "nearest_cases": []}
    rows = rows.copy()
    rows["similarity"] = rows.apply(lambda r: _similarity(current, r), axis=1)
    rows = rows[rows["similarity"] >= MIN_SIMILARITY]
    eligible = rows.copy()
    nearest = []
    for _, r in eligible.sort_values("similarity", ascending=False).head(5).iterrows():
        nearest.append({
            "date": str(r["base_date"]),
            "similarity": round(float(r["similarity"]), 4),
            "agent": str(r["agent"]),
            "prob_up": round(float(r["prob_up"]), 4),
            "actual_up": int(r["went_up"]),
            "correct": int(r["correct"]),
        })
    brains = {}
    for name, group in eligible.groupby(eligible["agent"].astype(str)):
        group = group.sort_values("similarity", ascending=False).head(MAX_NEIGHBORS)
        weights = group["similarity"].astype(float)
        denom = float(weights.sum()) or 1.0
        brains[name] = {
            "neighbors": int(len(group)),
            "weighted_accuracy": round(float((group["correct"] * weights).sum() / denom), 4),
            "weighted_brier": round(float((group["brier"] * weights).sum() / denom), 4),
            "avg_similarity": round(float(weights.mean()), 4),
        }
    return {
        "as_of": str(current.get("base_date")),
        "matched_samples": int(len(eligible)),
        "brains": brains,
        "nearest_cases": nearest,
    }

def similarity_weight_adjustments(names):
    try:
        report = build_similarity_memory()
    except Exception as exc:
        print(f"[similarity-memory] unavailable: {exc}")
        return {name: 1.0 for name in names}
    out = {}
    for name in names:
        stats = report.get("brains", {}).get("A9_" + name, {}) or report.get("brains", {}).get(name, {})
        n = int(stats.get("neighbors", 0))
        if n < MIN_NEIGHBORS:
            out[name] = 1.0
            continue
        quality = float(stats.get("weighted_brier", 0.25))
        similarity = float(stats.get("avg_similarity", 0.0))
        shrink = (n / (n + 16.0)) * max(0.0, min(1.0, similarity))
        delta = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, (0.25 - quality) * 0.12 * shrink))
        out[name] = round(1.0 + delta, 4)
    return out

def persist_similarity_memory():
    report = build_similarity_memory()
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
