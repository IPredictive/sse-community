import math
import numpy as np
import pandas as pd

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))

def sigmoid(x):
    x = max(-8.0, min(8.0, float(x)))
    return 1.0 / (1.0 + math.exp(-x))

def rsi(series, n=14):
    d = series.diff()
    gain = d.clip(lower=0).rolling(n).mean()
    loss = (-d.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return float(out.iloc[-1]) if np.isfinite(out.iloc[-1]) else 50.0

def atr(df, n=14):
    c = df.close.astype(float)
    h = df.high.astype(float)
    l = df.low.astype(float)
    prev = c.shift(1)
    tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    v = tr.rolling(n).mean().iloc[-1]
    return float(v) if np.isfinite(v) else float((h-l).tail(n).mean())

def confidence_from_score(score, evidence=1.0):
    return clamp(0.50 + min(0.42, abs(score) * 0.18) * clamp(evidence, 0.5, 1.2), 0.50, 0.92)

def direction_text(p):
    p=float(p)
    if p>=0.70:return "强烈偏多"
    if p>=0.60:return "偏多"
    if p>=0.53:return "中性偏多"
    if p>0.47:return "中性"
    if p>0.40:return "中性偏空"
    if p>0.30:return "偏空"
    return "强烈偏空"

POSITIVE = {"上涨":1.0,"上升":0.8,"增长":0.7,"提振":0.9,"支持":0.8,"促进":0.7,"改善":0.6,"回购":0.9,"增持":0.9,"降息":1.0,"降准":1.0,"宽松":0.9,"利好":1.0,"突破":0.8,"反弹":0.5,"企稳":0.7,"活跃":0.5,"扩张":0.5,"加码":0.6,"放宽":0.7,"稳增长":0.9,"优化":0.5,"鼓励":0.6,"提速":0.5,"复苏":0.7,"流入":0.7}
NEGATIVE = {"下跌":-1.0,"下降":-0.8,"回落":-0.7,"亏损":-0.9,"风险":-0.7,"承压":-0.8,"减持":-0.9,"处罚":-0.8,"监管":-0.35,"收紧":-0.8,"加息":-1.0,"通胀":-0.4,"流出":-0.7,"疲弱":-0.7,"低迷":-0.8,"违约":-1.0,"暴跌":-1.3,"失速":-0.8,"恶化":-0.9,"压力":-0.5,"风险提示":-0.8}

def title_sentiment(items):
    scores, weights = [], []
    for raw in items or []:
        if isinstance(raw, dict):
            title = str(raw.get("title", ""))
            weight = float(raw.get("freshness_weight", 1.0) or 1.0)
        else:
            title, weight = str(raw), 1.0
        if not title:
            continue
        score = sum(v for word, v in POSITIVE.items() if word in title)
        score += sum(v for word, v in NEGATIVE.items() if word in title)
        if "大涨" in title: score += 0.8
        if "大跌" in title: score -= 0.8
        if "同比" in title and ("增长" in title or "提升" in title): score += 0.25
        scores.append(score)
        weights.append(max(0.08, min(1.0, weight)))
    if not scores:
        return 0.0, 0.0, 0
    total = float(np.tanh(np.average(scores, weights=weights) / 2.2))
    dispersion = float(np.std(scores))
    evidence = min(1.0, 0.55 + sum(weights) / 24)
    if dispersion > 1.4: evidence *= 0.85
    return total, evidence, len(scores)
