"""Immutable-outcome daily performance and risk history for A9 and legacy brains."""
import json
import math
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


def build_performance_history(scored, predictions=None, limit=180):
    """One record per matured brain/date, plus a separate daily risk time series."""
    records = []
    if scored is not None and not scored.empty:
        frame = scored.copy()
        frame["base_date"] = frame.base_date.astype(str).str[:10]
        frame["agent"] = frame.agent.astype(str)
        for agent, group in frame.groupby("agent", sort=True):
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
                records.append({
                    "date": date, "agent": agent, "family": _family(agent),
                    "prob_up": round(probs[i], 6), "outcome_up": y,
                    "correct": int(correct[i]), "daily_brier": round(briers[i], 6),
                    "daily_log_loss": round(logloss, 6),
                    "regime": str(regimes[i] or "未知"),
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
    return {
        "schema_version": 1,
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
