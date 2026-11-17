from db import load_scored
MIN_SAMPLES=8
MAX_HISTORY=80

def _skill(rows):
    if rows is None or len(rows)<MIN_SAMPLES:return 0.0
    rows=rows.tail(MAX_HISTORY).copy(); n=len(rows)
    weights=[0.97**i for i in range(n-1,-1,-1)]; z=sum(weights) or 1.0
    acc=sum(float(c)*w for c,w in zip(rows.correct.astype(float),weights))/z
    brier=sum(float(c)*w for c,w in zip(rows.brier.astype(float),weights))/z
    acc=((acc*n)+0.5*8)/(n+8); brier=((brier*n)+0.25*8)/(n+8)
    return max(-1.0,min(1.0,0.60*(acc-0.5)*2+0.40*(1-brier/0.25)))

def learned_weights(names, regime_label):
    out={name:1.0 for name in names}
    try: scored=load_scored()
    except Exception as exc: print(f"[learning] unavailable: {exc}"); return out
    if scored is None or scored.empty:return out
    for name in names:
        rows=scored[scored.agent.astype(str)==name]; global_skill=_skill(rows); regime_skill=global_skill
        if "regime" in rows.columns:
            rr=rows[rows.regime.astype(str)==str(regime_label)]
            if len(rr)>=MIN_SAMPLES: regime_skill=_skill(rr)
        skill=0.65*global_skill+0.35*regime_skill
        out[name]=max(0.65,min(1.35,1.0+0.35*skill))
    return out

def learning_report(regime_label="未知"):
    try:
        scored=load_scored()
        if scored is None or scored.empty:return {"sample_count":0,"brains":{}}
        names=sorted(scored.agent.astype(str).unique()); weights=learned_weights(names,regime_label)
        return {"sample_count":int(len(scored)),"brains":{n:{"weight":round(weights[n],3)} for n in names}}
    except Exception:return {"sample_count":0,"brains":{}}
