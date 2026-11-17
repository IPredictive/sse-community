from .common import result, clamp
from .learning import learned_weights

def analyze(results, regime):
    base=[r for r in results if r.name!="chief_super"]
    if not base:
        return None
    groups={"market":["technical","quant","market_structure"],"policy":["macro","policy"],"risk":["geopolitical","global","money_sentiment"]}
    event_label=regime.get("_event_label","normal_noise")
    learned_weights_map=learned_weights([r.name for r in base],regime.get("label","未知"),event_label)
    routing=regime.get("_routing",{}) or {}
    route_multipliers=routing.get("multipliers",{}) or {}
    # Learning remains the evidence base; routing is a bounded regime multiplier.
    lw={r.name: clamp(learned_weights_map.get(r.name,1.0)*route_multipliers.get(r.name,1.0),0.65,1.45) for r in base}
    gp=[]
    for nameset in groups.values():
        rs=[r for r in base if r.name in nameset]
        if rs:
            den=sum(lw.get(r.name,1.0) for r in rs)
            gp.append(sum(r.prob_up*lw.get(r.name,1.0) for r in rs)/den)
    den=sum(lw.get(r.name,1.0) for r in base)
    p=sum(gp)/len(gp) if gp else sum(r.prob_up*lw.get(r.name,1.0) for r in base)/den
    risk=[r for r in base if r.name in ("geopolitical","global")]
    if risk:
        denr=sum(lw.get(r.name,1.0) for r in risk)
        rp=sum(r.prob_up*lw.get(r.name,1.0) for r in risk)/denr
        if rp<0.40 and p>0.55:
            p=0.5+0.80*(p-0.5)
        if rp>0.60 and p<0.45:
            p=0.5+0.80*(p-0.5)
    spread=max(r.prob_up for r in base)-min(r.prob_up for r in base)
    avg=sum(r.confidence for r in base)/len(base)
    conf=max(0.35,min(0.92,0.62-0.55*spread+0.08*avg))
    scenario=regime.get("_context_scenario",{}) or {}
    penalty=float(scenario.get("scenario_penalty",0.0) or 0.0)
    if penalty and p>0.50:
        p=clamp(p-penalty,0.05,0.95)
        conf=max(0.30,conf-0.60*penalty)
    learned="；".join(f"{r.name}权重={lw.get(r.name,1.0):.2f}" for r in base)
    stress=f"；压力测试下调={penalty:.1%}" if penalty else "；压力测试未触发下调"
    dominant="、".join(routing.get("dominant_brains",[])) or "均衡"
    route_reason=f"；动态路由主导={dominant}"
    return result("chief_super",p,conf,
                  f"9脑闭环：状态={regime.get('label','未知')}；事件={event_label}；历史学习+动态路由={learned}；分歧={spread:.1%}{stress}{route_reason}；最终综合判断",
                  [r.reason for r in base[:6]],
                  metadata={"learned_weights":learned_weights_map,"effective_weights":lw,"routing":routing,"event_label":event_label,"scenario_penalty":penalty,"scenario":scenario})
