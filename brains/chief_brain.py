from .common import result
from .learning import learned_weights

def analyze(results, regime):
    base=[r for r in results if r.name!="chief_super"]
    if not base:return None
    groups={"market":["technical","quant","market_structure"],"policy":["macro","policy"],"risk":["geopolitical","global","money_sentiment"]}
    lw=learned_weights([r.name for r in base],regime.get("label","未知")); gp=[]
    for nameset in groups.values():
        rs=[r for r in base if r.name in nameset]
        if rs:
            den=sum(lw.get(r.name,1.0) for r in rs)
            gp.append(sum(r.prob_up*lw.get(r.name,1.0) for r in rs)/den)
    den=sum(lw.get(r.name,1.0) for r in base)
    p=sum(gp)/len(gp) if gp else sum(r.prob_up*lw.get(r.name,1.0) for r in base)/den
    risk=[r for r in base if r.name in ("geopolitical","global")]
    if risk:
        denr=sum(lw.get(r.name,1.0) for r in risk); rp=sum(r.prob_up*lw.get(r.name,1.0) for r in risk)/denr
        if rp<0.40 and p>0.55:p=0.5+0.80*(p-0.5)
        if rp>0.60 and p<0.45:p=0.5+0.80*(p-0.5)
    spread=max(r.prob_up for r in base)-min(r.prob_up for r in base)
    avg=sum(r.confidence for r in base)/len(base)
    conf=max(0.35,min(0.92,0.62-0.55*spread+0.08*avg))
    learned="；".join(f"{r.name}权重={lw.get(r.name,1.0):.2f}" for r in base)
    return result("chief_super",p,conf,f"9脑闭环：状态={regime.get('label','未知')}；历史学习={learned}；分歧={spread:.1%}；最终综合判断",[r.reason for r in base[:6]],metadata={"learned_weights":lw})
