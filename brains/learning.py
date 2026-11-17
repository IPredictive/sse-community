from db import load_scored
from .postmortem import build_postmortem
from .event_memory import event_weight_adjustments, build_event_memory
from .similarity_memory import similarity_weight_adjustments, build_similarity_memory

MIN_SAMPLES = 8
MAX_HISTORY = 80
MIN_REGIME_SAMPLES = 8


def _skill(rows):
    if rows is None or len(rows) < MIN_SAMPLES:
        return 0.0
    rows = rows.tail(MAX_HISTORY).copy()
    n = len(rows)
    weights = [0.97 ** i for i in range(n - 1, -1, -1)]
    z = sum(weights) or 1.0
    acc = sum(float(c) * w for c, w in zip(rows.correct.astype(float), weights)) / z
    brier = sum(float(c) * w for c, w in zip(rows.brier.astype(float), weights)) / z
    acc = ((acc * n) + .5 * 8) / (n + 8)
    brier = ((brier * n) + .25 * 8) / (n + 8)
    return max(-1, min(1, .60 * (acc - .5) * 2 + .40 * (1 - brier / .25)))


def learned_weights(names, regime_label, event_label="normal_noise", as_of_date=None):
    """Use only matured forecasts strictly earlier than the forecast being built."""
    out = {name: 1.0 for name in names}
    try:
        scored = load_scored()
    except Exception as exc:
        print(f"[learning] unavailable: {exc}")
        return out
    if scored is None or scored.empty:
        return out

    scored = scored.copy()
    all_latest_scored_date = max(scored.base_date.astype(str).str[:10])
    scored["base_date"] = scored.base_date.astype(str).str[:10]
    if as_of_date is not None:
        cutoff = str(as_of_date)[:10]
        scored = scored[scored.base_date < cutoff]
    if scored.empty:
        return out

    historical_replay = as_of_date is not None and str(as_of_date)[:10] < all_latest_scored_date
    # During historical replay, disable state builders that currently summarize
    # the full database; this prevents future postmortems/event/case memories
    # from contaminating a past forecast. Live forecasts can use matured memory.
    post = {} if historical_replay else build_postmortem().get("agents", {})
    event_adjust = ({name: 1.0 for name in names} if historical_replay
                    else event_weight_adjustments(names, event_label))
    similarity_adjust = ({name: 1.0 for name in names} if historical_replay
                         else similarity_weight_adjustments(names))
    for name in names:
        # A9 specialist outcomes are evaluated independently. If the A9 stream
        # has not matured enough observations, fall back conservatively to the
        # corresponding traditional specialist history.
        own = scored[scored.agent.astype(str) == "A9_" + name]
        rows = own if len(own) >= MIN_SAMPLES else scored[scored.agent.astype(str) == name]
        global_skill = _skill(rows)
        regime_skill = global_skill
        if "regime" in rows.columns:
            rr = rows[rows.regime.astype(str) == str(regime_label)]
            if len(rr) >= MIN_REGIME_SAMPLES:
                regime_skill = _skill(rr)
        skill = .65 * global_skill + .35 * regime_skill

        penalty = 1.0
        pm = post.get("A9_" + name, post.get(name, {}))
        if int(pm.get("wrong_streak", 0)) >= 3:
            penalty -= .06
        if float(pm.get("overconfidence_error_rate", 0)) >= .35:
            penalty -= .04
        if float(pm.get("severe_error_rate", 0)) >= .45:
            penalty -= .03
        base = max(.65, min(1.35, 1 + .35 * skill)) * max(.85, penalty)
        out[name] = round(base * event_adjust.get(name, 1.0) * similarity_adjust.get(name, 1.0), 4)
    return out


def learning_report(regime_label="未知", event_label="normal_noise", as_of_date=None):
    try:
        scored = load_scored()
        if scored is None or scored.empty:
            return {"sample_count": 0, "brains": {}, "event_label": event_label}
        if as_of_date is not None:
            scored = scored[scored.base_date.astype(str).str[:10] < str(as_of_date)[:10]]
        names = sorted(scored.agent.astype(str).unique())
        weights = learned_weights(names, regime_label, event_label, as_of_date=as_of_date)
        post = build_postmortem().get("agents", {})
        event_memory = build_event_memory()
        similarity = build_similarity_memory()
        return {
            "sample_count": int(len(scored)),
            "as_of_date": str(as_of_date)[:10] if as_of_date is not None else None,
            "event_label": event_label,
            "event_samples": int(event_memory.get("events", {}).get(event_label, {}).get("samples", 0)),
            "similarity_as_of": similarity.get("as_of"),
            "similarity_matched_samples": similarity.get("matched_samples", 0),
            "nearest_cases": similarity.get("nearest_cases", []),
            "brains": {n: {"weight": round(weights.get(n, 1.0), 3), "postmortem": post.get(n, {}),
                           "similar_cases": similarity.get("brains", {}).get(n, {})} for n in names}
        }
    except Exception as exc:
        print(f"[learning-report] failed: {exc}")
        return {"sample_count": 0, "brains": {}, "event_label": event_label}
