import argparse
import json
import os

from agents import ALL_AGENTS
from context import build_context
from data import fetch_sse, make_demo
from db import init_db, load_daily, save_prediction, upsert_daily, refresh_predictions_for_date, save_agnes_review
from ensemble import combine
from agnes_brain import review_forecast, format_review
from market_regime import classify_market_regime


def predict_for(df, context=None, enable_agnes_review=False):
    if df.empty:
        return
    base = df.date.iloc[-1]
    preds = {}
    for agent in ALL_AGENTS:
        try:
            prediction = agent.predict(df, context)
        except Exception as exc:
            print(f"[{agent.name}] error: {exc}")
            prediction = None
        if prediction:
            preds[agent.name] = prediction
            save_prediction(base, agent.name, prediction.prob_up, prediction.reason, prediction.confidence)

    ensemble = combine(preds, context)
    if ensemble:
        # Phase 1 fusion: AGNES reviews and challenges the analysis, but does not
        # change the ensemble probability until the review has been backtested.
        if enable_agnes_review:
            review = review_forecast(base, df, preds, ensemble, context)
            # Keep AGNES as an independent reviewer: store its structured output
            # separately so it can be audited/backtested without changing the ensemble probability.
            if not os.getenv("AGNES_API_KEY", "").strip():
                review_status = "skipped"
                review_error = "AGNES_API_KEY is not configured"
            elif review:
                review_status = "completed"
                review_error = None
            else:
                review_status = "unavailable"
                review_error = "API key configured, but no valid review was returned; see AGNES log"
            save_agnes_review(
                base, review_status,
                model=(os.getenv("AGNES_MODEL") or "agnes-3.0-flash").strip(),
                review=review,
                error=review_error,
            )
            print(f"[AGNES-AUDIT] date={base} status={review_status} model={(os.getenv('AGNES_MODEL') or 'agnes-3.0-flash').strip()}")
            review_note = format_review(review)
            if review_note:
                ensemble.reason = (str(ensemble.reason) + "；" + review_note)[:1200]

        save_prediction(base, "CHIEF_ANALYST", ensemble.prob_up, ensemble.reason, ensemble.confidence)
        print(f"\n===== SSE DAILY AI REPORT {base} =====")
        for name, prediction in preds.items():
            print(
                f"{name:10s}  上涨概率={prediction.prob_up:.1%}  "
                f"信心={prediction.confidence:.1%}  理由={prediction.reason}"
            )
        print(f"CHIEF ANALYST 上涨概率={ensemble.prob_up:.1%}  信心={ensemble.confidence:.1%}")
        print(f"综合理由：{ensemble.reason}")
        print("====================================")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--backfill", type=int, default=0)
    parser.add_argument("--no-news", action="store_true")
    args = parser.parse_args()

    init_db()
    upsert_daily(make_demo() if args.demo else fetch_sse())
    df = load_daily()
    if df.empty:
        raise RuntimeError("No SSE index data available; refusing to generate an empty forecast.")

    context = {} if args.no_news else build_context(as_of_date=df.date.iloc[-1])
    context["market_regime"] = classify_market_regime(df)
    regime = context["market_regime"]
    print("[MARKET-REGIME] " + regime["label"] + ": " + regime["detail"])
    for offset in range(args.backfill, 0, -1):
        predict_for(df.iloc[: len(df) - offset], {} if args.backfill else context, enable_agnes_review=False)

    refresh_predictions_for_date(df.date.iloc[-1])
    predict_for(df, context, enable_agnes_review=True)
    print(json.dumps({"latest_date": df.date.iloc[-1], "context": context}, ensure_ascii=False))


if __name__ == "__main__":
    main()
