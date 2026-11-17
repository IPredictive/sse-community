"""Heuristic event memory for regime-aware prediction learning.

Event labels are evidence tags, not claims of proven causation. A minimum sample
threshold and a small adjustment cap keep sparse histories from dominating.
"""
import json
from pathlib import Path

import pandas as pd
from db import load_daily, load_scored

PATH = Path(__file__).parent.parent / "data" / "event_memory.json"
MIN_EVENT_SAMPLES = 6
MAX_EVENT_ADJUSTMENT = 0.05

KEYWORDS = {
    "policy_macro": ("降准", "降息", "财政", "货币政策", "央行", "国务院", "刺激", "政策"),
    "geopolitical": ("战争", "冲突", "制裁", "地缘", "军事", "关税", "封锁"),
    "rmb_fx": ("人民币", "美元", "汇率", "中间价", "外汇"),
    "overseas": ("美股", "标普", "纳斯达克", "恒生", "海外市场", "全球市场"),
    "liquidity": ("流动性", "资金面", "融资", "降杠杆", "北向资金", "成交额", "放量"),
    "sentiment_flow": ("情绪", "恐慌", "贪婪", "主力资金", "资金流", "市场情绪"),
}

def _text_event(text):
    s = str(text or "")
    for label, words in KEYWORDS.items():
        if any(w in s for w in words):
            return label
    return None

def _daily_features():
    df = load_daily()
    if df is None or df.empty:
        return {}
    df = df.sort_values("date").copy()
    close = pd.to_numeric(df["close"], errors="coerce")
    prev = close.shift(1)
    ret = close / prev - 1
    day_range = (pd.to_numeric(df["high"], errors="coerce") - pd.to_numeric(df["low"], errors="coerce")) / prev
    volume = pd.to_numeric(df["volume"], errors="coerce")
    vol_base = volume.shift(1).rolling(20, min_periods=5).median()
    vol_ratio = volume / vol_base.replace(0, float("nan"))
    out = {}
    for i, row in df.iterrows():
        idx = df.index.get_loc(i)
        r = ret.loc[i]
        rg = day_range.loc[i]
        vr = vol_ratio.loc[i]
        hist = ret.iloc[max(0, idx-5):idx]
        trend = float(hist.mean()) if len(hist.dropna()) else 0.0
        out[str(row["date"])[:10]] = {
            "return": float(r) if pd.notna(r) else 0.0,
            "range": float(rg) if pd.notna(rg) else 0.0,
            "volume_ratio": float(vr) if pd.notna(vr) else 1.0,
            "prior_5d_return": trend,
        }
    return out

def _market_event(feature, reason=""):
    f = feature or {}
    move = abs(float(f.get("return", 0.0)))
    intraday = abs(float(f.get("range", 0.0)))
    volume = float(f.get("volume_ratio", 1.0))
    text_label = _text_event(reason)
    if move >= 0.018 or intraday >= 0.028:
        return "volatility_shock"
    if volume >= 1.55 and move >= 0.008:
        return "liquidity"
    if text_label:
        return text_label
    prior = float(f.get("prior_5d_return", 0.0))
    today = float(f.get("return", 0.0))
    if abs(today) >= 0.004 and prior * today > 0:
        return "trend_continuation"
    return "normal_noise"

def current_event(df, context=None):
    context = context or {}
    titles = context.get("news_titles", []) + context.get("macro_titles", [])
    text = " ".join(str(x) for x in titles)
    macro = _text_event(text)
    overseas = context.get("overseas", {}) or {}
    overseas_shock = any(abs(float(v)) >= 0.012 for v in overseas.values() if isinstance(v, (int, float)))
    if macro:
        return macro
    if overseas_shock:
        return "overseas"
    if df is not None and len(df) >= 2:
        a, b = float(df.close.iloc[-2]), float(df.close.iloc[-1])
        if a:
            move = b / a - 1
            if abs(move) >= 0.018:
                return "volatility_shock"
            if abs(move) >= 0.004:
                return "trend_continuation"
    return "normal_noise"

def build_event_memory():
    scored = load_scored()
    if scored is None or scored.empty:
        return {"sample_count": 0, "events": {}, "by_brain": {}}
    features = _daily_features()
    scored = scored.copy()
    if "reason" not in scored.columns:
        scored["reason"] = ""
    scored["event"] = scored.apply(
        lambda r: _market_event(features.get(str(r.base_date)[:10]), r.get("reason", "")),
        axis=1,
    )
    events = {}
    by_brain = {}
    for event, group in scored.groupby("event"):
        events[str(event)] = {"samples": int(len(group)), "accuracy": round(float(group.correct.mean()), 4),
                              "avg_brier": round(float(group.brier.mean()), 4)}
    for brain, group in scored.groupby(scored.agent.astype(str)):
        by_brain[brain] = {}
        for event, rows in group.groupby("event"):
            by_brain[brain][str(event)] = {
                "samples": int(len(rows)),
                "accuracy": round(float(rows.correct.mean()), 4),
                "avg_brier": round(float(rows.brier.mean()), 4),
                "false_bull": int(((rows.prob_up > 0.5) & (rows.went_up == 0)).sum()),
                "false_bear": int(((rows.prob_up <= 0.5) & (rows.went_up == 1)).sum()),
            }
    return {"sample_count": int(len(scored)), "events": events, "by_brain": by_brain}

def event_weight_adjustments(names, event_label):
    try:
        memory = build_event_memory()
    except Exception as exc:
        print(f"[event-memory] unavailable: {exc}")
        return {name: 1.0 for name in names}
    out = {}
    for name in names:
        stats = (memory.get("by_brain", {}).get("A9_" + name, {}) or memory.get("by_brain", {}).get(name, {})).get(str(event_label), {})
        n = int(stats.get("samples", 0))
        if n < MIN_EVENT_SAMPLES:
            out[name] = 1.0
            continue
        # Brier 0.25 is the neutral reference; shrink toward 1 and cap at +/-5%.
        raw = (0.25 - float(stats.get("avg_brier", 0.25))) * 0.20
        shrink = n / (n + 12.0)
        delta = max(-MAX_EVENT_ADJUSTMENT, min(MAX_EVENT_ADJUSTMENT, raw * shrink))
        out[name] = round(1.0 + delta, 4)
    return out

def persist_event_memory():
    report = build_event_memory()
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
