from .common import result

def analyze(results, regime):
    base=[r for r in results if r.name!="chief_super"]
    if not base:return None
    # Correlated groups are intentionally capped; independent risk brains can veto extreme conviction.
    groups={"market":["technical","quant","market_structure"],"policy":["macro","policy"],"risk":["geopolitical","global","money_sentiment"]}
    gp=[]
    for names in groups.values():
        rs=[r for r in base if r.name in names]
        if rs: gp.append(sum(r.prob_up for r in rs)/len(rs))
    p=sum(gp)/len(gp) if gp else sum(r.prob_up for r in base)/len(base)
    risk=[r for r in base if r.name in ("geopolitical","global")]
    if risk:
        rp=sum(r.prob_up for r in risk)/len(risk)
        if rp<0.40 and p>0.55:p=0.5+0.80*(p-0.5)
        if rp>0.60 and p<0.45:p=0.5+0.80*(p-0.5)
    spread=max(r.prob_up for r in base)-min(r.prob_up for r in base)
    conf=max(0.35,min(0.92,0.62-0.55*spread+0.08*sum(r.confidence for r in base)/len(base)))
    label=regime.get("label","未知")
    return result("chief_super",p,conf,f"9脑协同：状态={label}；分组交叉验证={'; '.join(f'{k}:{sum(r.prob_up for r in base if r.name in v)/max(1,len([r for r in base if r.name in v])):.1%}' for k,v in groups.items())}；分歧={spread:.1%}；最终综合判断",[r.reason for r in base[:6]])
