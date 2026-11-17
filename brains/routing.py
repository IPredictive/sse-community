"""Conservative, explainable A9 specialist routing.

Routing multipliers are bounded and deterministic. They only redistribute the
existing learned specialist weights; they do not create new signals or change
the overall specialist group budget.
"""
from pathlib import Path
import json

from .common import clamp

BRAIN_GROUPS = {
    "technical": "trend",
    "quant": "trend",
    "market_structure": "structure",
    "macro": "policy",
    "policy": "policy",
    "geopolitical": "risk",
    "global": "global",
    "money_sentiment": "flow",
}

def route_brains(regime=None, event_label="normal_noise", scenario=None):
    regime = regime or {}
    scenario = scenario or {}
    label = str(regime.get("label", "未知"))
    vol = regime.get("volatility20")
    trend = regime.get("trend20")
    multipliers = {name: 1.0 for name in BRAIN_GROUPS}
    reasons = []

    def apply(group, factor):
        for name, brain_group in BRAIN_GROUPS.items():
            if brain_group == group:
                multipliers[name] *= factor

    if label == "上行趋势":
        apply("trend", 1.12)
        apply("structure", 1.06)
        apply("risk", 0.94)
        reasons.append("上行趋势：提高趋势/结构脑权重")
    elif label == "下行趋势":
        apply("risk", 1.12)
        apply("global", 1.08)
        apply("trend", 0.94)
        reasons.append("下行趋势：提高风险脑权重")
    elif label == "高波动风险":
        apply("risk", 1.18)
        apply("global", 1.12)
        apply("trend", 0.88)
        apply("flow", 1.06)
        reasons.append("高波动：风险与全球脑优先")
    else:
        apply("structure", 1.08)
        apply("flow", 1.05)
        reasons.append("震荡/未知状态：提高结构与资金情绪脑权重")

    event_routes = {
        "policy_macro": ("policy", 1.12),
        "geopolitical": ("risk", 1.14),
        "rmb_fx": ("global", 1.10),
        "overseas": ("global", 1.10),
        "liquidity": ("flow", 1.12),
        "sentiment_flow": ("flow", 1.10),
        "volatility_shock": ("risk", 1.12),
        "trend_continuation": ("trend", 1.08),
    }
    if event_label in event_routes:
        group, factor = event_routes[event_label]
        apply(group, factor)
        reasons.append(f"事件路由：{event_label} → {group}")

    downside = float(scenario.get("downside_stress_avg", 0.5) or 0.5)
    penalty = float(scenario.get("scenario_penalty", 0.0) or 0.0)
    if downside >= 0.62 or penalty >= 0.04:
        apply("risk", 1.06)
        apply("global", 1.04)
        reasons.append("压力测试偏高：加强风险/全球脑")
    # Hard bounds prevent a routing rule from dominating learned evidence.
    multipliers = {k: round(clamp(v, 0.82, 1.22), 4) for k, v in multipliers.items()}
    ranked = sorted(multipliers.items(), key=lambda item: item[1], reverse=True)
    return {
        "regime": label,
        "event_label": event_label,
        "multipliers": multipliers,
        "dominant_brains": [name for name, _ in ranked[:3]],
        "reasons": reasons,
        "bounds": [0.82, 1.22],
        "downside_stress_avg": downside,
        "scenario_penalty": penalty,
    }

def persist_routing(route, base_date=None):
    path = Path(__file__).parent.parent / "data" / "routing_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(route or {})
    payload["base_date"] = str(base_date) if base_date is not None else None
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
