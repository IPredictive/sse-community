import argparse,json
from agents import ALL_AGENTS
from context import build_context
from data import fetch_sse,make_demo
from db import init_db,load_daily,save_prediction,upsert_daily,refresh_predictions_for_date
from ensemble import combine
def predict_for(df,context=None):
    if df.empty:return
    base=df.date.iloc[-1];preds={}
    for a in ALL_AGENTS:
        try:p=a.predict(df,context)
        except Exception as e:print(f"[{a.name}] error: {e}");p=None
        if p:preds[a.name]=p;save_prediction(base,a.name,p.prob_up,p.reason,p.confidence)
    ens=combine(preds,context)
    if ens:
        save_prediction(base,"CHIEF_ANALYST",ens.prob_up,ens.reason,ens.confidence)
        print(f"\n===== SSE DAILY AI REPORT {base} =====")
        for name, pred in preds.items():
            print(f"{name:10s}  上涨概率={pred.prob_up:.1%}  信心={pred.confidence:.1%}  理由={pred.reason}")
        print(f"CHIEF ANALYST 上涨概率={ens.prob_up:.1%}  信心={ens.confidence:.1%}")
        print(f"综合理由：{ens.reason}")
        print("====================================")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--demo",action="store_true");ap.add_argument("--backfill",type=int,default=0);ap.add_argument("--no-news",action="store_true");args=ap.parse_args();init_db();upsert_daily(make_demo() if args.demo else fetch_sse());df=load_daily();ctx={} if args.no_news else build_context(as_of_date=df.date.iloc[-1])
    for i in range(args.backfill,0,-1):predict_for(df.iloc[:len(df)-i],{} if args.backfill else ctx)
    refresh_predictions_for_date(df.date.iloc[-1])
    predict_for(df,ctx);print(json.dumps({"latest_date":df.date.iloc[-1],"context":ctx},ensure_ascii=False))
if __name__=="__main__":main()
