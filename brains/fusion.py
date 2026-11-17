from agents.base import Prediction

def fuse(classic, a9, context=None):
    if not classic and not a9: return None
    if not classic: return Prediction(a9.prob_up,a9.reason,a9.confidence)
    if not a9: return Prediction(classic.prob_up,classic.reason,classic.confidence)
    p1,p2=float(classic.prob_up),float(a9.prob_up)
    gap=abs(p1-p2)
    # A9 has wider evidence coverage; classic ensemble retains veto weight for continuity.
    w9=0.55 if gap<0.15 else 0.48
    p=w9*p2+(1-w9)*p1
    # When the two independent systems disagree, move toward neutral rather than hide disagreement.
    if gap>0.25: p=0.5+0.78*(p-0.5)
    conf=min(0.92,(1-w9)*classic.confidence+w9*a9.confidence-0.18*min(gap,0.35))
    regime=(context or {}).get("market_regime",{}).get("label","未知")
    reason=(f"闭环融合：传统5智能体={p1:.1%}；A9九脑={p2:.1%}；两套系统分歧={gap:.1%}；"
            f"市场状态={regime}；采用独立双引擎交叉验证后的{p:.1%}判断")
    return Prediction(max(.08,min(.92,p)),reason,max(.35,min(.92,conf)))
