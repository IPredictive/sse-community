from agents.base import Prediction
from agents.quant import clamp, confidence_from_score, direction_text
from db import load_scored

# Preserve the established priors; history may refine them only after enough settled forecasts.
BASE_WEIGHTS = {
    "technical": 1.00,
    "flow": 1.00,
    "macro": 1.10,
    "sentiment": 0.95,
    "overseas": 0.90,
}
MIN_ADAPTIVE_SAMPLES = 12
MAX_HISTORY = 60


def evidence_quality(pred, name, context=None):
    conf = clamp(getattr(pred, "confidence", 0.5), 0.5, 0.92)
    quality = 0.45 + 0.75 * (conf - 0.5) / 0.42
    ctx = context or {}
    if name == "sentiment":
        n = len(ctx.get("news_items", []) or [])
        quality *= 0.65 if n < 2 else (0.82 if n < 4 else (0.92 if n < 8 else 1.0))
    elif name == "macro":
        n = len(ctx.get("macro_items", []) or [])
        quality *= 0.65 if n < 2 else (0.82 if n < 4 else (0.92 if n < 8 else 1.0))
    elif name == "overseas":
        n = len(ctx.get("overseas", {}) or {})
        quality *= 0.70 if n < 2 else (0.86 if n < 3 else 1.0)
    return clamp(quality, 0.25, 1.0)


def stabilize_extreme(probability, quality):
    """Shrink extreme probabilities when evidence is thin; never invent stronger conviction."""
    p = clamp(probability, 0.08, 0.92)
    q = clamp(quality, 0.25, 1.0)
    if abs(p - 0.5) <= 0.30:
        return p
    damp = 0.40 + 0.60 * q
    return 0.5 + (p - 0.5) * damp


def _historical_skill(rows):
    """Recency-weighted skill with a neutral prior to reduce overfitting."""
    if rows is None or rows.empty:
        return None
    rows = rows.tail(MAX_HISTORY).copy()
    if len(rows) < MIN_ADAPTIVE_SAMPLES:
        return None

    # Newer settled predictions count more, but no single result can dominate.
    import numpy as np
    n = len(rows)
    recency = np.power(0.97, np.arange(n - 1, -1, -1, dtype=float))
    recency = recency / recency.sum()
    accuracy = clamp(float((rows["correct"].astype(float).to_numpy() * recency).sum()), 0.0, 1.0)
    brier_values = rows["brier"].astype(float).to_numpy()
    brier = clamp(float((brier_values * recency).sum()), 0.0, 1.0)

    # Shrink noisy metrics toward chance-level accuracy and the 0.25 Brier baseline.
    prior_n = 8.0
    effective_n = float(n)
    accuracy = (accuracy * effective_n + 0.5 * prior_n) / (effective_n + prior_n)
    brier = (brier * effective_n + 0.25 * prior_n) / (effective_n + prior_n)
    brier_skill = clamp(1.0 - brier / 0.25, -1.0, 1.0)
    return 0.55 * (accuracy - 0.5) * 2.0 + 0.45 * brier_skill


def adaptive_weights(preds):
    weights = {name: BASE_WEIGHTS.get(name, 1.0) for name in preds}
    try:
        scored = load_scored()
        if scored is None or scored.empty:
            return weights
        for name in preds:
            rows = scored[scored.agent.astype(str) == name]
            skill = _historical_skill(rows)
            if skill is None:
                # Fewer than 12 settled outcomes: preserve the prior exactly.
                continue
            # Skill around zero means approximately chance-level performance.
            # Bound the adjustment to prevent noisy history from silencing an agent.
            multiplier = 1.0 + 0.40 * clamp(skill, -0.75, 0.75)
            weights[name] *= clamp(multiplier, 0.70, 1.30)
    except Exception as exc:
        print(f"[ensemble] adaptive weighting skipped; using prior weights: {exc}")
    return weights


def combine(preds, context=None):
    if not preds:
        return None

    weights = adaptive_weights(preds)
    quality = {name: evidence_quality(pred, name, context) for name, pred in preds.items()}
    adjusted = {
        name: stabilize_extreme(pred.prob_up, quality[name])
        for name, pred in preds.items()
    }
    for name in weights:
        weights[name] *= 0.70 + 0.50 * quality[name]

    total = sum(weights.values())
    if total <= 0:
        return None
    base_prob = sum(adjusted[name] * weights[name] for name in preds) / total
    base_conf = sum(
        clamp(preds[name].confidence, 0.35, 0.95) * weights[name]
        for name in preds
    ) / total

    probs = [clamp(pred.prob_up, 0.0, 1.0) for pred in preds.values()]
    spread = max(probs) - min(probs)
    mean_abs_deviation = sum(abs(p - base_prob) for p in adjusted.values()) / len(adjusted)
    agreement = clamp(1.0 - spread / 0.55, 0.0, 1.0)

    # Independent evidence clusters prevent several correlated signals from dominating.
    clusters = {
        "核心市场": [name for name in ("technical", "flow") if name in preds],
        "政策情绪": [name for name in ("macro", "sentiment") if name in preds],
        "海外环境": [name for name in ("overseas",) if name in preds],
    }
    cluster_probs = {}
    for cluster, names in clusters.items():
        if not names:
            continue
        cluster_weight = sum(weights[name] for name in names)
        if cluster_weight:
            cluster_probs[cluster] = sum(
                adjusted[name] * weights[name] for name in names
            ) / cluster_weight

    cluster_votes = [prob >= 0.5 for prob in cluster_probs.values()]
    bullish = sum(cluster_votes)
    bearish = len(cluster_votes) - bullish
    if len(cluster_votes) >= 2 and (bullish == len(cluster_votes) or bearish == len(cluster_votes)):
        consensus_prob = sum(cluster_probs.values()) / len(cluster_probs)
        base_prob = 0.78 * base_prob + 0.22 * consensus_prob
        base_conf = min(0.95, base_conf + 0.025)
        cross_label = "独立分组方向一致"
    elif len(cluster_votes) >= 2 and bullish and bearish:
        base_prob = 0.5 + 0.82 * (base_prob - 0.5)
        base_conf = max(0.35, base_conf - 0.07)
        cross_label = "独立分组存在分歧"
    else:
        base_conf = max(0.35, base_conf - 0.02)
        cross_label = "独立分组样本不足"

    # Confidence is reduced when analysts disagree, even if the average is directional.
    disagreement_penalty = clamp(mean_abs_deviation * 0.45 + max(0.0, spread - 0.25) * 0.12, 0.0, 0.18)
    confidence = clamp(base_conf * (0.88 + 0.12 * agreement) - disagreement_penalty, 0.35, 0.92)

    cluster_text = "；".join(f"{name}:{prob:.1%}" for name, prob in cluster_probs.items())
    details = "；".join(
        f"{name}:{adjusted[name]:.1%}(证据{quality[name]:.0%}，权重{weights[name]:.2f})"
        for name in preds
    )
    regime = (context or {}).get("market_regime") or {}
    regime_label = str(regime.get("label") or "未识别")
    regime_detail = str(regime.get("detail") or "")
    reason = (
        f"市场状态={regime_label}（{regime_detail}）；"
        f"协同分析：{details}；分析师分歧区间={spread:.1%}；"
        f"{cross_label}；分组交叉验证={cluster_text or '暂无'}；"
        f"综合判断{direction_text(base_prob)}"
    )
    return Prediction(clamp(base_prob, 0.08, 0.92), reason, confidence)
