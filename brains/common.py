import math
import numpy as np

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))

def sigmoid(x):
    try: return 1.0/(1.0+math.exp(-float(x)))
    except OverflowError: return 0.0 if x < 0 else 1.0

def pct(series, n):
    if series is None or len(series) <= n: return None
    a=float(series.iloc[-1]); b=float(series.iloc[-1-n])
    return a/b-1 if b else None

def norm(x, scale):
    return math.tanh(float(x)/float(scale)) if scale else 0.0

def news_score(items, positive, negative):
    score=0.0; weight=0.0
    for item in items or []:
        t=str(item.get("title", item) if isinstance(item,dict) else item)
        w=float(item.get("freshness_weight",1.0)) if isinstance(item,dict) else 1.0
        p=sum(1 for k in positive if k in t); n=sum(1 for k in negative if k in t)
        score += w*(p-n); weight += w
    return score/max(weight,1.0)

def result(name, p, c, reason, evidence=None, metadata=None):
    from .types import BrainResult
    return BrainResult(name,clamp(p,0.05,0.95),clamp(c,0.25,0.95),reason,evidence or [],metadata=metadata or {})
