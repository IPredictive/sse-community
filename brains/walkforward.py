"""Strict chronological out-of-sample evaluation of adaptive brain weighting."""
import pandas as pd

MIN_TRAIN = 8
WINDOW = 80


def _skill(rows):
    if len(rows) < MIN_TRAIN:
        return 0.0
    rows = rows.tail(WINDOW)
    n = len(rows)
    decay = [0.97 ** i for i in range(n - 1, -1, -1)]
    total = sum(decay) or 1.0
    accuracy = sum(float(v) * w for v, w in zip(rows.correct.astype(float), decay)) / total
    brier = sum(float(v) * w for v, w in zip(rows.brier.astype(float), decay)) / total
    accuracy = (accuracy * n + .5 * 8) / (n + 8)
    brier = (brier * n + .25 * 8) / (n + 8)
    return max(-1.0, min(1.0, .60 * (accuracy - .5) * 2 + .40 * (1 - brier / .25)))


def evaluate_walk_forward(scored):
    """Compare equal weights with learned weights, using strictly prior outcomes."""
    empty = {
        "method": "strict_chronological_walk_forward",
        "evaluation_dates": 0,
        "training_minimum": MIN_TRAIN,
        "equal_weight_brier": None,
        "adaptive_weight_brier": None,
        "equal_weight_accuracy": None,
        "adaptive_weight_accuracy": None,
        "improvement_brier": None,
        "note": "样本不足，暂不评价动态权重。",
    }
    if scored is None or scored.empty:
        return empty
    frame = scored.copy()
    frame["base_date"] = frame.base_date.astype(str).str[:10]
    frame["agent"] = frame.agent.astype(str)
    frame["brain"] = frame.agent.str.replace(r"^A9_", "", regex=True)
    excluded = {"CHIEF_ANALYST", "CHIEF_ANALYST_CALIBRATED", "A9_SUPER_CHIEF", "chief_super"}
    frame = frame[~frame.brain.isin(excluded)].copy()
    if frame.empty:
        return empty

    results = []
    for date, current in frame.groupby("base_date", sort=True):
        history = frame[frame.base_date < date]
        if history.empty:
            continue
        # Prefer A9 specialist forecasts on a date; use legacy specialist rows
        # only when an A9 row for that specialist is not available.
        current = current.copy()
        current["_is_a9"] = current.agent.str.startswith("A9_")
        current = current.sort_values("_is_a9", ascending=False).drop_duplicates("brain")
        if current.empty:
            continue
        weights = []
        for _, row in current.iterrows():
            prior = history[history.brain == row.brain].tail(WINDOW)
            global_skill = _skill(prior)
            regime_skill = global_skill
            if "regime" in prior.columns and pd.notna(row.get("regime")):
                same = prior[prior.regime.astype(str) == str(row.regime)]
                if len(same) >= MIN_TRAIN:
                    regime_skill = _skill(same)
            skill = .65 * global_skill + .35 * regime_skill
            weights.append(max(.65, min(1.35, 1 + .35 * skill)))
        probs = pd.to_numeric(current.prob_up, errors="coerce")
        valid = probs.notna()
        if not valid.any():
            continue
        current = current.loc[valid].copy()
        probs = probs.loc[valid].astype(float)
        weights = [w for w, ok in zip(weights, valid.tolist()) if ok]
        actuals = pd.to_numeric(current.went_up, errors="coerce")
        if actuals.isna().any() or actuals.nunique() != 1:
            continue
        actual = int(actuals.iloc[0])
        equal_p = float(probs.mean())
        adaptive_p = float(sum(p * w for p, w in zip(probs.tolist(), weights)) / sum(weights))
        results.append({
            "date": date, "actual": actual,
            "equal_p": equal_p, "adaptive_p": adaptive_p,
            "equal_correct": int((equal_p > .5) == bool(actual)),
            "adaptive_correct": int((adaptive_p > .5) == bool(actual)),
        })

    if len(results) < 3:
        return dict(empty, evaluation_dates=len(results),
                    note="样本外日期少于3个，暂不判断动态权重是否优于等权。")
    out = pd.DataFrame(results)
    equal_brier = float(((out.equal_p - out.actual) ** 2).mean())
    adaptive_brier = float(((out.adaptive_p - out.actual) ** 2).mean())
    equal_acc = float(out.equal_correct.mean())
    adaptive_acc = float(out.adaptive_correct.mean())
    return {
        "method": "strict_chronological_walk_forward",
        "evaluation_dates": int(len(out)),
        "first_evaluation_date": str(out.date.iloc[0]),
        "last_evaluation_date": str(out.date.iloc[-1]),
        "training_minimum": MIN_TRAIN,
        "rolling_window": WINDOW,
        "equal_weight_brier": round(equal_brier, 6),
        "adaptive_weight_brier": round(adaptive_brier, 6),
        "equal_weight_accuracy": round(equal_acc, 4),
        "adaptive_weight_accuracy": round(adaptive_acc, 4),
        "improvement_brier": round(equal_brier - adaptive_brier, 6),
        "note": "仅按日期顺序训练和评估；动态权重是否有效以样本外 Brier 为主，样本量不足时不作结论。",
    }
