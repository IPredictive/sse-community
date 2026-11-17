from .common import result, clamp
from .learning import learned_weights

def analyze(results, regime):
    base = [r for r in results if r.name != "chief_super"]
    if not base:
        return None
    groups = {
        "market": ["technical", "quant", "market_structure"],
        "policy": ["macro", "policy"],
        "risk": ["geopolitical", "global", "money_sentiment"],
    }
    event_label = regime.get("_event_label", "normal_noise")
    as_of_date = regime.get("_as_of_date")
    learned_weights_map = learned_weights(
        [r.name for r in base], regime.get("label", "未知"), event_label, as_of_date=as_of_date
    )
    routing = regime.get("_routing", {}) or {}
    route_multipliers = routing.get("multipliers", {}) or {}
    lw = {r.name: clamp(learned_weights_map.get(r.name, 1.0) * route_multipliers.get(r.name, 1.0), .65, 1.45)
          for r in base}

    gp = []
    for nameset in groups.values():
        rs = [r for r in base if r.name in nameset]
        if rs:
            den = sum(lw.get(r.name, 1.0) for r in rs)
            gp.append(sum(r.prob_up * lw.get(r.name, 1.0) for r in rs) / den)
    den = sum(lw.get(r.name, 1.0) for r in base)
    p = sum(gp) / len(gp) if gp else sum(r.prob_up * lw.get(r.name, 1.0) for r in base) / den

    risk = [r for r in base if r.name in ("geopolitical", "global")]
    if risk:
        denr = sum(lw.get(r.name, 1.0) for r in risk)
        rp = sum(r.prob_up * lw.get(r.name, 1.0) for r in risk) / denr
        if rp < .40 and p > .55:
            p = .5 + .80 * (p - .5)
        if rp > .60 and p < .45:
            p = .5 + .80 * (p - .5)

    spread = max(r.prob_up for r in base) - min(r.prob_up for r in base)
    avg = sum(r.confidence for r in base) / len(base)
    risk_review = spread >= .35
    conf = max(.35, min(.92, .62 - .55 * spread + .08 * avg))
    if risk_review:
        conf = max(.30, conf - .08)
    scenario = regime.get("_context_scenario", {}) or {}
    penalty = float(scenario.get("scenario_penalty", 0.0) or 0.0)
    if penalty and p > .50:
        p = clamp(p - penalty, .05, .95)
        conf = max(.30, conf - .60 * penalty)

    learned = "；".join(f"{r.name}权重={lw.get(r.name, 1.0):.2f}" for r in base)
    stress = f"；压力测试下调={penalty:.1%}" if penalty else "；压力测试未触发下调"
    dominant = "、".join(routing.get("dominant_brains", [])) or "均衡"
    route_reason = f"；动态路由主导={dominant}"
    review_reason = "；高分歧触发风险复核" if risk_review else "；分歧处于常规范围"
    return result(
        "chief_super", p, conf,
        f"9脑闭环：状态={regime.get('label','未知')}；事件={event_label}；历史学习+动态路由={learned}；"
        f"分歧={spread:.1%}{review_reason}{stress}{route_reason}；最终综合判断",
        [r.reason for r in base[:6]],
        metadata={
            "learned_weights": learned_weights_map, "effective_weights": lw, "routing": routing,
            "event_label": event_label, "scenario_penalty": penalty, "scenario": scenario,
            "disagreement_spread": spread, "risk_review_required": risk_review,
            "as_of_date": str(as_of_date)[:10] if as_of_date is not None else None,
        },
    )
