"""Immutable-outcome daily performance and risk history for A9 and legacy brains."""
import json
import math
import random
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "brain_performance_history.json"
SITE_PATH = Path(__file__).parent.parent / "site" / "brain-performance-history.json"
A9_KEYS = {"A9_" + key for key in (
    "technical", "quant", "market_structure", "macro", "policy",
    "geopolitical", "global", "money_sentiment"
)}
TRADITIONAL_KEYS = {
    "technical", "flow", "macro", "sentiment", "overseas", "CHIEF_ANALYST"
}


def _family(agent):
    if agent in A9_KEYS:
        return "A9"
    if agent == "A9_SUPER_CHIEF":
        return "A9_SUPER_CHIEF"
    return "traditional" if agent in TRADITIONAL_KEYS else "other"


def _log_loss(probability, outcome):
    p = max(1e-9, min(1 - 1e-9, float(probability)))
    y = int(outcome)
    return -(y * math.log(p) + (1-y) * math.log(1-p))


def _block_bootstrap_ci(values, block_size=5, iterations=1000):
    """Deterministic moving-block bootstrap CI for paired daily Brier deltas."""
    n = len(values)
    if n < 60:
        return None
    rng = random.Random(20261117)
    blocks = [values[i:i + block_size] for i in range(max(1, n - block_size + 1))]
    estimates = []
    for _ in range(iterations):
        sample = []
        while len(sample) < n:
            sample.extend(rng.choice(blocks))
        sample = sample[:n]
        estimates.append(sum(sample) / n)
    estimates.sort()
    return [round(estimates[int(.025 * (iterations - 1))], 6),
            round(estimates[int(.975 * (iterations - 1))], 6)]


def build_performance_history(scored, predictions=None, limit=180):
    """One record per matured brain/date, plus a separate daily risk time series."""
    records = []
    if scored is not None and not scored.empty:
        frame = scored.copy()
        frame["base_date"] = frame.base_date.astype(str).str[:10]
        frame["agent"] = frame.agent.astype(str)
        for agent, group in frame.groupby("agent", sort=True):
            if agent in {"CHIEF_ANALYST_CALIBRATED", "chief_super"}:
                continue
            group = group.sort_values("base_date").drop_duplicates("base_date", keep="last")
            correct = group.correct.astype(float).tolist()
            briers = group.brier.astype(float).tolist()
            probs = group.prob_up.astype(float).tolist()
            outcomes = group.went_up.astype(int).tolist()
            dates = group.base_date.astype(str).tolist()
            regimes = group.regime.tolist() if "regime" in group.columns else ["未知"] * len(group)
            for i, date in enumerate(dates):
                start10, start20 = max(0, i - 9), max(0, i - 19)
                p = max(1e-9, min(1 - 1e-9, probs[i]))
                y = outcomes[i]
                logloss = -(y * math.log(p) + (1-y) * math.log(1-p))
                regime_value = regimes[i]
                regime_label = (
                    str(regime_value) if regime_value is not None
                    and str(regime_value).strip().lower() not in {"", "nan", "none"}
                    else "未知"
                )
                records.append({
                    "date": date, "agent": agent, "family": _family(agent),
                    "prob_up": round(probs[i], 6), "outcome_up": y,
                    "correct": int(correct[i]), "daily_brier": round(briers[i], 6),
                    "daily_log_loss": round(logloss, 6),
                    "regime": regime_label,
                    "rolling10_accuracy": round(sum(correct[start10:i+1]) / len(correct[start10:i+1]), 4),
                    "rolling10_brier": round(sum(briers[start10:i+1]) / len(briers[start10:i+1]), 6),
                    "rolling20_accuracy": round(sum(correct[start20:i+1]) / len(correct[start20:i+1]), 4),
                    "rolling20_brier": round(sum(briers[start20:i+1]) / len(briers[start20:i+1]), 6),
                    "cumulative_accuracy": round(sum(correct[:i+1]) / (i+1), 4),
                    "cumulative_brier": round(sum(briers[:i+1]) / (i+1), 6),
                    "samples": i + 1,
                })
    records.sort(key=lambda r: (r["date"], r["family"], r["agent"]))
    risks = []
    if predictions is not None and not predictions.empty:
        frame = predictions.copy()
        frame["base_date"] = frame.base_date.astype(str).str[:10]
        frame["agent"] = frame.agent.astype(str)
        for date, day in frame.groupby("base_date", sort=True):
            a9 = day[day.agent.isin(A9_KEYS)]
            traditional = day[day.agent.isin(TRADITIONAL_KEYS - {"CHIEF_ANALYST"})]
            selected = a9 if len(a9) >= 2 else traditional
            if len(selected) < 2:
                continue
            values = [max(0.0, min(1.0, float(v))) for v in selected.prob_up.tolist()]
            spread = max(values) - min(values)
            bullish = sum(v > .5 for v in values)
            bearish = len(values) - bullish
            risks.append({
                "date": str(date)[:10],
                "family": "A9" if len(a9) >= 2 else "traditional",
                "brain_count": len(values),
                "probability_spread": round(spread, 6),
                "direction_disagreement": min(bullish, bearish),
                "triggered": spread >= .35,
                "threshold": .35,
            })
    paired_daily = []
    if scored is not None and not scored.empty:
        pair_frame = scored.copy()
        pair_frame["base_date"] = pair_frame.base_date.astype(str).str[:10]
        a9_chief = pair_frame[pair_frame.agent.astype(str) == "A9_SUPER_CHIEF"]
        legacy_chief = pair_frame[pair_frame.agent.astype(str) == "CHIEF_ANALYST"]
        paired = a9_chief.merge(
            legacy_chief, on="base_date", suffixes=("_a9", "_traditional")
        ).sort_values("base_date")
        for _, row in paired.iterrows():
            paired_daily.append({
                "date": row.base_date,
                "regime": str(row.get("regime_a9") or row.get("regime_traditional") or "未知"),
                "a9_correct": int(row.correct_a9),
                "traditional_correct": int(row.correct_traditional),
                "a9_brier": round(float(row.brier_a9), 6),
                "traditional_brier": round(float(row.brier_traditional), 6),
                "a9_log_loss": round(_log_loss(row.prob_up_a9, row.went_up_a9), 6),
                "traditional_log_loss": round(_log_loss(row.prob_up_traditional, row.went_up_traditional), 6),
            })
    paired_n = len(paired_daily)
    def paired_metrics(key):
        if not paired_daily:
            return None
        return {
            "samples": paired_n,
            "accuracy": round(sum(x[key + "_correct"] for x in paired_daily) / paired_n, 4),
            "brier": round(sum(x[key + "_brier"] for x in paired_daily) / paired_n, 6),
            "log_loss": round(sum(x[key + "_log_loss"] for x in paired_daily) / paired_n, 6),
        }
    regime_pairs = {}
    for regime in sorted({x["regime"] for x in paired_daily}):
        subset = [x for x in paired_daily if x["regime"] == regime]
        regime_pairs[regime] = {
            "samples": len(subset),
            "a9_brier": round(sum(x["a9_brier"] for x in subset) / len(subset), 6),
            "traditional_brier": round(sum(x["traditional_brier"] for x in subset) / len(subset), 6),
            "evidence_status": "eligible" if len(subset) >= 10 else "insufficient_evidence",
        }
    brier_deltas = [x["a9_brier"] - x["traditional_brier"] for x in paired_daily]
    brier_ci = _block_bootstrap_ci(brier_deltas)
    if paired_n < 30:
        comparison_status = "collecting"
    elif paired_n < 60:
        comparison_status = "provisional_comparison"
    elif brier_ci[1] < 0:
        comparison_status = "evidence_favors_a9"
    elif brier_ci[0] > 0:
        comparison_status = "evidence_favors_traditional"
    else:
        comparison_status = "no_clear_brier_advantage"
    comparison = {
        "method": "same_date_A9_SUPER_CHIEF_vs_CHIEF_ANALYST",
        "paired_dates": paired_n,
        "minimum_paired_dates": 60,
        "descriptive_threshold": 30,
        "status": comparison_status,
        "paired_brier_delta_ci95_block5": brier_ci,
        "a9": paired_metrics("a9"),
        "traditional": paired_metrics("traditional"),
        "brier_delta_a9_minus_traditional": (
            round(paired_metrics("a9")["brier"] - paired_metrics("traditional")["brier"], 6)
            if paired_n else None
        ),
        "regimes": regime_pairs,
        "paired_daily": paired_daily[-180:],
        "note": "30个配对日期仅开放描述性观察；至少60个同日期成熟配对样本后，才使用5日移动区块Bootstrap 95%区间评估Brier差异。区间跨0则不判胜负；市场状态至少10个配对样本才展示分层指标。",
    }
    return {
        "schema_version": 1,
        "paired_comparison": comparison,
        "method": "matured_next_session_outcomes_only",
        "record_count": len(records),
        "risk_days": len(risks),
        "records": records[-limit * 20:],
        "risk_history": risks[-limit:],
        "notes": [
            "准确率、Brier 与 LogLoss 只在下一交易日收盘已知后生成。",
            "rolling10/20 按每个脑自身的已结算预测序列计算，不填补缺失日期。",
            "市场状态采用预测时保存的标签；未知状态单独保留。",
            "A9 与传统 AI 分开记录；风险序列优先采用同日 A9 专业脑，否则采用传统专业脑。",
        ],
    }


def persist_performance_history(scored, predictions=None):
    report = build_performance_history(scored, predictions)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(payload, encoding="utf-8")
    SITE_PATH.write_text(payload, encoding="utf-8")
    return report
