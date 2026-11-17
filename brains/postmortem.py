import json
from pathlib import Path
from db import load_scored
PATH=Path(__file__).parent.parent/"data"/"postmortem_state.json"
def build_postmortem():
    df=load_scored()
    if df is None or df.empty:return {"sample_count":0,"agents":{}}
    out={}
    for name,g in df.groupby(df.agent.astype(str)):
        g=g.sort_values("base_date").tail(20).copy(); wrong=(g.correct.astype(int)==0)
        overconf=((g.prob_up-0.5).abs()>0.18)&wrong; severe=(g.brier>=0.25); streak=0
        for v in reversed(g.correct.astype(int).tolist()):
            if int(v)==0: streak+=1
            else: break
        if float(wrong.mean())>=.60: attribution="方向判断错误偏多"
        elif float(overconf.mean())>=.35: attribution="过度自信偏多"
        elif float(severe.mean())>=.45: attribution="概率校准偏差"
        else: attribution="正常波动"
        out[name]={"samples":int(len(g)),"accuracy":round(float(g.correct.mean()),4),"avg_brier":round(float(g.brier.mean()),4),"wrong_rate":round(float(wrong.mean()),4),"overconfidence_error_rate":round(float(overconf.mean()),4),"severe_error_rate":round(float(severe.mean()),4),"wrong_streak":streak,"attribution":attribution}
    return {"sample_count":int(len(df)),"agents":out}
def persist_postmortem():
    report=build_postmortem(); PATH.parent.mkdir(exist_ok=True); PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); return report
