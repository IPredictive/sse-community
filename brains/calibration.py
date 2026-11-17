"""Conservative probability calibration and leakage-free walk-forward evaluation.

Only matured forecasts from dates strictly before the target forecast date may
train a calibration mapping. Raw probabilities remain immutable and auditable.
"""
import json
import math
from pathlib import Path

import pandas as pd
from db import load_scored

PATH = Path(__file__).parent.parent / "data" / "calibration_state.json"
MIN_TRAIN = 30
MIN_BIN = 5
SHRINKAGE = 25.0
MAX_DELTA = 0.06
EPS = 1e-6


def _clip(p):
    return max(0.08, min(0.92, float(p)))


def _adjust(prob, history):
    """Return a gently shrunk bin correction; history must be strictly earlier."""
    p = _clip(prob)
    if history is None or len(history) < MIN_TRAIN:
        return p, {"active": False, "samples": 0 if history is None else int(len(history)),
                   "method": "insufficient_history", "delta": 0.0}
    h = history.copy()
    h["prob_up"] = pd.to_numeric(h["prob_up"], errors="coerce")
    h["went_up"] = pd.to_numeric(h["went_up"], errors="coerce")
    h = h.dropna(subset=["prob_up", "went_up"])
    if len(h) < MIN_TRAIN:
        return p, {"active": False, "samples": int(len(h)),
                   "method": "insufficient_valid_history", "delta": 0.0}
    idx = min(9, max(0, int(p * 10)))
    lo, hi = idx / 10.0, (idx + 1) / 10.0
    local = h[(h.prob_up >= lo) & (h.prob_up < hi if idx < 9 else h.prob_up <= hi)]
    if len(local) >= MIN_BIN:
        mean_pred = float(local.prob_up.mean())
        observed = float(local.went_up.mean())
        n = len(local)
        method = "shrunk_probability_bin"
    else:
        mean_pred = float(h.prob_up.mean())
        observed = float(h.went_up.mean())
        n = len(h)
        method = "shrunk_global_bias"
    raw_delta = observed - mean_pred
    shrink = n / (n + SHRINKAGE)
    delta = max(-MAX_DELTA, min(MAX_DELTA, raw_delta * shrink))
    calibrated = _clip(p + delta)
    return calibrated, {
        "active": True, "samples": int(len(h)), "bin_samples": int(len(local)),
        "method": method, "delta": round(calibrated - p, 6),
        "bin_observed_rate": round(observed, 4),
        "bin_mean_probability": round(mean_pred, 4),
    }


def calibrate_probability(prob, as_of_date, agent="CHIEF_ANALYST"):
    try:
        scored = load_scored()
    except Exception as exc:
        return _clip(prob), {"active": False, "samples": 0, "method": "data_unavailable",
                             "error": str(exc), "delta": 0.0}
    if scored is None or scored.empty:
        return _clip(prob), {"active": False, "samples": 0,
                             "method": "no_history", "delta": 0.0}
    rows = scored[scored.agent.astype(str) == str(agent)].copy()
    rows["base_date"] = rows.base_date.astype(str).str[:10]
    # Critical leakage guard: the target date and every later date are excluded.
    rows = rows[rows.base_date < str(as_of_date)[:10]].sort_values("base_date").tail(160)
    return _adjust(prob, rows)


def _log_loss(probabilities, outcomes):
    total = 0.0
    for p, y in zip(probabilities, outcomes):
        p = max(EPS, min(1.0 - EPS, float(p)))
        total -= float(y) * math.log(p) + (1.0 - float(y)) * math.log(1.0 - p)
    return total / len(outcomes) if outcomes else None


def _ece(probabilities, outcomes, bins=10):
    if not outcomes:
        return None
    total = len(outcomes)
    error = 0.0
    for i in range(bins):
        group = [(p, y) for p, y in zip(probabilities, outcomes)
                 if i / bins <= p < (i + 1) / bins or (i == bins - 1 and p == 1.0)]
        if group:
            avg_p = sum(p for p, _ in group) / len(group)
            avg_y = sum(y for _, y in group) / len(group)
            error += len(group) / total * abs(avg_p - avg_y)
    return error


def walk_forward_backtest(scored=None):
    """For each forecast date, fit only on earlier matured dates."""
    if scored is None:
        scored = load_scored()
    if scored is None or scored.empty:
        return {"method": "strict_walk_forward", "brains": {}}
    frame = scored.copy()
    frame["base_date"] = frame.base_date.astype(str).str[:10]
    reports = {}
    for agent, group in frame.groupby(frame.agent.astype(str)):
        group = group.sort_values("base_date").reset_index(drop=True)
        raw, calibrated, outcomes = [], [], []
        for _, row in group.iterrows():
            prior = group[group.base_date < str(row.base_date)].tail(160)
            if len(prior) < MIN_TRAIN:
                continue
            p_cal, _ = _adjust(float(row.prob_up), prior)
            raw.append(_clip(row.prob_up))
            calibrated.append(p_cal)
            outcomes.append(int(row.went_up))
        if not outcomes:
            reports[agent] = {"backtested_samples": 0, "status": "样本不足"}
            continue
        raw_brier = sum((p-y)**2 for p, y in zip(raw, outcomes)) / len(outcomes)
        cal_brier = sum((p-y)**2 for p, y in zip(calibrated, outcomes)) / len(outcomes)
        reports[agent] = {
            "backtested_samples": len(outcomes),
            "raw_brier": round(raw_brier, 6),
            "calibrated_brier": round(cal_brier, 6),
            "raw_log_loss": round(_log_loss(raw, outcomes), 6),
            "calibrated_log_loss": round(_log_loss(calibrated, outcomes), 6),
            "raw_ece": round(_ece(raw, outcomes), 6),
            "calibrated_ece": round(_ece(calibrated, outcomes), 6),
            "brier_improvement": round(raw_brier - cal_brier, 6),
            "status": "已完成滚动回测",
        }
    return {"method": "strict_walk_forward", "min_training_samples": MIN_TRAIN,
            "brains": reports}


def persist_calibration(as_of_date=None):
    try:
        scored = load_scored()
        if as_of_date is None and scored is not None and not scored.empty:
            as_of_date = str(scored.base_date.max())[:10]
        report = walk_forward_backtest(scored)
        report["as_of"] = str(as_of_date)[:10] if as_of_date else None
        report["training_rule"] = "仅使用目标预测日期之前、且下一交易日结果已知的历史样本"
        PATH.parent.mkdir(exist_ok=True)
        PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    except Exception as exc:
        report = {"as_of": str(as_of_date)[:10] if as_of_date else None,
                  "method": "strict_walk_forward", "brains": {}, "error": str(exc)}
        PATH.parent.mkdir(exist_ok=True)
        PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
