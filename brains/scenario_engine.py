from .common import clamp, pct, news_score

SCENARIOS = (
    ("base", "基准", 0.00),
    ("bull", "上行扩张", 0.06),
    ("bear", "下行压力", -0.06),
    ("shock", "综合冲击", -0.12),
    ("liquidity", "流动性冲击", -0.10),
    ("geopolitical", "地缘风险", -0.09),
    ("policy_stimulus", "政策刺激", 0.08),
    ("rmb_shock", "人民币冲击", -0.07),
    ("overseas_selloff", "海外急跌", -0.10),
)

def _features(df, context):
    close=df["close"]
    t20=pct(close,20) or 0.0
    t60=pct(close,60) or 0.0
    ret=close.pct_change().dropna()
    vol=float(ret.tail(20).std()) if len(ret)>=20 else 0.0
    overseas=context.get("overseas",{}) or {}
    sp=float(overseas.get("标普500",0.0) or 0.0)
    nas=float(overseas.get("纳斯达克",0.0) or 0.0)
    hsi=float(overseas.get("恒生指数",0.0) or 0.0)
    rmb=float(overseas.get("美元人民币",0.0) or 0.0)
    news=news_score(context.get("news_items",[]),
                    ["利好","提振","上涨","增持","降准","降息","刺激","支持","回购"],
                    ["利空","下跌","减持","风险","冲击","加息","紧缩","制裁"])
    macro=news_score(context.get("macro_items",[]),
                     ["降准","降息","宽松","刺激","财政","支持","稳增长","扩内需"],
                     ["紧缩","加息","收紧","风险","下行","衰退"])
    return dict(t20=t20,t60=t60,vol=vol,sp=sp,nas=nas,hsi=hsi,rmb=rmb,news=news,macro=macro)

def run(df, context, specialist_results):
    f=_features(df,context)
    base=sum(r.prob_up*r.confidence for r in specialist_results)/max(0.25,sum(r.confidence for r in specialist_results))
    regime=(context.get("market_regime",{}) or {}).get("label","未知")
    regime_risk={"高波动风险":0.10,"下行趋势":0.06,"上行趋势":-0.02}.get(regime,0.0)
    sensitivity={
        "base":0.0,
        "bull":0.06 + 0.20*max(f["t20"],0)+0.12*max(f["macro"],0),
        "bear":-0.06 + 0.20*min(f["t20"],0)-0.10*max(f["news"],0),
        "shock":-0.12-0.20*f["vol"]+0.03*min(f["t20"],0),
        "liquidity":-0.10-0.08*max(f["rmb"],0)-0.06*max(f["vol"]-0.02,0),
        "geopolitical":-0.09-0.05*max(-f["news"],0),
        "policy_stimulus":0.08+0.05*max(f["macro"],0),
        "rmb_shock":-0.07-0.18*max(f["rmb"],0),
        "overseas_selloff":-0.10-0.10*max(-f["sp"],0)-0.06*max(-f["nas"],0)-0.04*max(-f["hsi"],0),
    }
    scenarios=[]
    for key,label,seed in SCENARIOS:
        adj=sensitivity.get(key,seed)
        p=clamp(base+adj,0.08,0.92)
        if key=="shock": p=clamp(p-regime_risk,0.05,0.92)
        c=clamp(0.45+0.35*min(1.0,abs(adj)/0.10)+0.15*(1-f["vol"]/0.05),0.30,0.85)
        scenarios.append({"name":key,"label":label,"prob_up":round(p,4),"confidence":round(c,4),"delta":round(p-base,4)})
    downside=[s for s in scenarios if s["name"] in ("bear","shock","liquidity","geopolitical","rmb_shock","overseas_selloff")]
    downside_avg=sum(s["prob_up"] for s in downside)/len(downside)
    penalty=max(0.0,min(0.18,(0.50-downside_avg)*0.55))
    if base>0.60 and downside_avg<0.40: penalty=0.0
    adjusted=clamp(base-penalty if base>0.5 else base+penalty,0.05,0.95)
    return {
        "base_prob_up":round(base,4),
        "stress_adjusted_prob_up":round(adjusted,4),
        "scenario_penalty":round(penalty,4),
        "downside_stress_avg":round(downside_avg,4),
        "regime":regime,
        "features":{k:round(v,6) for k,v in f.items()},
        "scenarios":scenarios,
        "risk_flags":[
            "下行压力情景一致偏弱" if downside_avg<0.40 else None,
            "高波动放大尾部风险" if f["vol"]>=0.025 else None,
            "海外同步走弱" if f["sp"]<0 and f["nas"]<0 and f["hsi"]<0 else None,
        ],
    }
