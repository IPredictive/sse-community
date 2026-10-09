import json
from agents import ALL_AGENTS
from context import build_context
from data import fetch_sse
from db import init_db, load_daily, save_prediction, upsert_daily, refresh_predictions_for_date
from ensemble import combine

def main():
    init_db()
    df_new = fetch_sse()
    upsert_daily(df_new)
    df = load_daily()
    if df.empty:
        raise RuntimeError("No daily market data available")
    base_date = str(df.date.iloc[-1])[:10]
    context = build_context(as_of_date=base_date)
    refresh_predictions_for_date(base_date)
    preds = {}
    for agent in ALL_AGENTS:
        try:
            prediction = agent.predict(df, context)
        except Exception as exc:
            print(f"[{agent.name}] failed: {exc}")
            prediction = None
        if prediction:
            preds[agent.name] = prediction
            save_prediction(base_date, agent.name, prediction.prob_up, prediction.reason, prediction.confidence)
    chief = combine(preds, context)
    if chief:
        save_prediction(base_date, "CHIEF_ANALYST", chief.prob_up, chief.reason, chief.confidence)
    print(json.dumps({"latest_date":base_date,"agents":list(preds),"chief_probability":chief.prob_up if chief else None},ensure_ascii=False))

if __name__ == "__main__":
    main()
