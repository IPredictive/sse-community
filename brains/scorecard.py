"""Outcome-based A9 brain scorecard and disagreement risk audit.

Only forecasts with a known next-session close are scored. A9 specialist
streams are reported independently from legacy specialists and the A9 chief.
"""
import json
import math
from pathlib import Path

import pandas as pd
from db import load_scored
from .walkforward import evaluate_walk_forward

PATH = Path(__file__).parent.parent / "data" / "brain_scorecard.json"
MIN_RANK_SAMPLES = 5
MIN_REGIME_SAMPLES = 8
EXCLUDED = {"CHIEF_ANALYST_CALIBRATED", "A9_SUPER_CHIEF", "chief_super"}
A9_SPECIALISTS = (
    "technical", "quant", "market_structure", "macro",
    "policy", "geopolitical", "global", "money_sentiment",
)


def _ece(group, bins=10):
    if group is None or group.empty:
        return None
    total = len(group)
    value = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        part = group[(group.prob_up >= lo) & (
            (group.prob_up < hi) if i < bins - 1 else (group.prob_up <= hi)
        )]
        if not part.empty:
            value += len(part) / total * abs(float(part.prob_up.mean()) - float(part.went_up.mean()))
    return value


def _metrics(group):
    g = group.copy()
    g["prob_up"] = pd.to_numeric(g.prob_up, errors="coerce").clip(0.0, 1.0)
    g["went_up"] = pd.to_numeric(g.went_up, errors="coerce")
    g = g.dropna(subset=["prob_up", "went_up"]).sort_values("base_date")
    if g.empty:
        return None
    p = g.prob_up.astype(float).tolist()
    y = g.went_up.astype(int).tolist()
    eps = 1e-9
    brier = sum((a-b)**2 for a,b in zip(p,y)) / len(y)
    logloss = -sum(b*math.log(max(eps,min(1-eps,a))) +
                   (1-b)*math.log(max(eps,min(1-eps,1-a))) for a,b in zip(p,y)) / len(y)
    majority = int(sum(y) >= len(y)/2)
    recent = g.tail(20)
    return {
        "samples": len(g),
        "accuracy": round(float(g.correct.mean()), 4),
        "brier": round(brier, 6),
        "log_loss": round(logloss, 6),
        "ece": round(_ece(g), 6),
        "recent20_accuracy": round(float(recent.correct.mean()), 4),
        "recent20_brier": round(float(recent.brier.mean()), 6),
        "up_rate": round(float(sum(y)/len(y)), 4),
        "majority_baseline_accuracy": round(sum(1 for v in y if v == majority)/len(y), 4),
        "last_scored_date": str(g.base_date.iloc[-1])[:10],
        "rank_eligible": len(g) >= MIN_RANK_SAMPLES,
    }


def _a9_scorecards(frame):
    """Return independent A9 specialist metrics with explicit evidence gates."""
    a9 = frame[frame.agent.astype(str).str.startswith("A9_")].copy()
    a9 = a9[a9.agent.astype(str) != "A9_SUPER_CHIEF"]
    out = {}
    for name in A9_SPECIALISTS:
        rows = a9[a9.agent.astype(str) == "A9_" + name].copy()
        global_metrics = _metrics(rows) if not rows.empty else None
        regimes = {}
        if not rows.empty and "regime" in rows.columns:
            for regime, group in rows.groupby("regime"):
                metrics = _metrics(group)
                if metrics:
                    metrics["evidence_status"] = (
                        "eligible" if metrics["samples"] >= MIN_REGIME_SAMPLES
                        else "insufficient_evidence"
                    )
                    regimes[str(regime)] = metrics
        samples = int(len(rows))
        out[name] = {
            "samples": samples,
            "evidence_status": "eligible" if samples >= MIN_RANK_SAMPLES else "collecting",
            "global": global_metrics,
            "regimes": regimes,
            "minimum_global_samples": MIN_RANK_SAMPLES,
            "minimum_regime_samples": MIN_REGIME_SAMPLES,
            "last_scored_date": str(rows.base_date.max())[:10] if samples else None,
        }
    return out


def _risk_review_history(frame, limit=30):
    """Historical settled-date disagreement audit; never mixes unsettled outcomes."""
    rows = []
    specialists = frame[~frame.agent.astype(str).isin(EXCLUDED | {"CHIEF_ANALYST"})].copy()
    for date, day in specialists.groupby("base_date", sort=True):
        a9 = day[day.agent.astype(str).str.startswith("A9_") &
                 (day.agent.astype(str) != "A9_SUPER_CHIEF")]
        if not a9.empty:
            day = a9
        else:
            day = day[~day.agent.astype(str).str.startswith("A9_")]
        p = pd.to_numeric(day.prob_up, errors="coerce").dropna()
        if len(p) < 2:
            continue
        spread = float(p.max() - p.min())
        directions = (p > .5).astype(int)
        majority = int(directions.mean() >= .5)
        dissent = int((directions != majority).sum())
        rows.append({
            "base_date": str(date)[:10],
            "source": "A9_specialists" if not a9.empty else "traditional_specialists",
            "brain_count": int(len(p)),
            "probability_spread": round(spread, 4),
            "disagreement_count": dissent,
            "triggered": spread >= .35,
            "threshold": .35,
            "status": "high_disagreement_review" if spread >= .35 else "normal",
        })
    return rows[-limit:]


def build_scorecard(scored=None):
    if scored is None:
        scored = load_scored()
    if scored is None or scored.empty:
        return {
            "method": "matured_next_session_outcomes", "sample_count": 0,
            "brains": {}, "a9_specialists": _a9_scorecards(pd.DataFrame(
                columns=["agent", "base_date", "prob_up", "went_up", "correct", "brier", "regime"]
            )), "ranking": [], "disagreements": [], "risk_review": None,
        }
    frame = scored.copy()
    frame["base_date"] = frame.base_date.astype(str).str[:10]
    frame["agent"] = frame.agent.astype(str)
    brains = {}
    for name, group in frame.groupby("agent"):
        if name in EXCLUDED:
            continue
        metrics = _metrics(group)
        if metrics:
            brains[name] = metrics
    regime_breakdown = {}
    if "regime" in frame.columns:
        for (brain, regime), group in frame[~frame.agent.isin(EXCLUDED)].groupby(["agent", "regime"]):
            metrics = _metrics(group)
            if metrics:
                metrics["evidence_status"] = (
                    "eligible" if metrics["samples"] >= MIN_REGIME_SAMPLES
                    else "insufficient_evidence"
                )
                regime_breakdown.setdefault(str(brain), {})[str(regime)] = metrics
    ranking = sorted(
        [{"brain": name, **metrics} for name, metrics in brains.items() if metrics["rank_eligible"]],
        key=lambda x: (x["brier"], -x["accuracy"], -x["samples"])
    )

    usable = frame[~frame.agent.isin(EXCLUDED)].copy()
    wide = usable.pivot_table(index="base_date", columns="agent", values="prob_up", aggfunc="last")
    outcome = usable.groupby("base_date").went_up.first()
    names = sorted(wide.columns.tolist())
    disagreements = []
    for i, left in enumerate(names):
        for right in names[i+1:]:
            pair = pd.concat([wide[left], wide[right], outcome], axis=1).dropna()
            pair = pair[(pair[left] - 0.5) * (pair[right] - 0.5) < 0]
            if pair.empty:
                continue
            left_correct = ((pair[left] > 0.5).astype(int) == pair.went_up.astype(int))
            right_correct = ((pair[right] > 0.5).astype(int) == pair.went_up.astype(int))
            disagreements.append({
                "brain_a": left, "brain_b": right, "samples": len(pair),
                "a_correct_rate": round(float(left_correct.mean()), 4),
                "b_correct_rate": round(float(right_correct.mean()), 4),
                "a_only_correct": int((left_correct & ~right_correct).sum()),
                "b_only_correct": int((right_correct & ~left_correct).sum()),
                "both_wrong": int((~left_correct & ~right_correct).sum()),
            })
    disagreements.sort(key=lambda x: (-x["samples"], x["brain_a"], x["brain_b"]))
    risk_history = _risk_review_history(frame)
    return {
        "method": "matured_next_session_outcomes",
        "sample_count": int(len(frame)),
        "scored_dates": int(frame.base_date.nunique()),
        "min_rank_samples": MIN_RANK_SAMPLES,
        "min_regime_samples": MIN_REGIME_SAMPLES,
        "brains": brains,
        "a9_specialists": _a9_scorecards(frame),
        "regime_breakdown": regime_breakdown,
        "ranking": ranking,
        "walk_forward": evaluate_walk_forward(frame),
        "disagreements": disagreements[:60],
        "risk_review": risk_history[-1] if risk_history else None,
        "risk_review_history": risk_history,
        "notes": [
            "只统计下一交易日收盘结果已知的预测。",
            "A9 八个专业脑独立计分，不与传统智能体或 A9 SUPER CHIEF 混算。",
            "全局排名至少需要5个已结算样本；分市场状态至少需要8个样本。",
            "高分歧复核阈值为专业脑上涨概率最大差值达到35个百分点。",
            "市场状态评分只使用预测当时记录的状态标签；缺少状态标签的旧记录不参与分状态评分。",
            "历史相关性和回测表现不保证未来收益。",
        ],
    }


def persist_scorecard():
    report = build_scorecard()
    PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    PATH.write_text(payload, encoding="utf-8")
    public_path = PATH.parent.parent / "site" / "brain-scorecard.json"
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(payload, encoding="utf-8")
    return report
