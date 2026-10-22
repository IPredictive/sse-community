"""Explainable, low-dependency market regime detection for SSE daily forecasts.

This is a diagnostic feature only: it annotates forecasts but does not alter
forecast probabilities or agent weights until out-of-sample tests justify that.
"""
import numpy as np
import pandas as pd


def classify_market_regime(daily):
    if daily is None or len(daily) < 60 or "close" not in daily.columns:
        return {
            "label": "数据不足",
            "trend20": None,
            "trend60": None,
            "volatility20": None,
            "detail": "至少需要60个交易日收盘数据",
        }

    close = pd.to_numeric(daily["close"], errors="coerce").dropna().astype(float)
    if len(close) < 60 or (close <= 0).any():
        return {
            "label": "数据异常",
            "trend20": None,
            "trend60": None,
            "volatility20": None,
            "detail": "收盘价样本不足或存在非正价格",
        }

    returns = close.pct_change().dropna()
    last = float(close.iloc[-1])
    sma20 = float(close.tail(20).mean())
    sma60 = float(close.tail(60).mean())
    trend20 = last / float(close.iloc[-20]) - 1.0
    trend60 = last / float(close.iloc[-60]) - 1.0
    volatility20 = float(returns.tail(20).std(ddof=1) * np.sqrt(252))

    # Prefer risk state when volatility is elevated; otherwise use price trend.
    if volatility20 >= 0.28:
        label = "高波动风险"
    elif trend20 >= 0.025 and last > sma20 and sma20 > sma60:
        label = "上行趋势"
    elif trend20 <= -0.025 and last < sma20 and sma20 < sma60:
        label = "下行趋势"
    else:
        label = "震荡/趋势转换"

    detail = (
        f"20日变化{trend20:+.2%}，60日变化{trend60:+.2%}，"
        f"20日年化波动率{volatility20:.1%}；仅作状态识别，不代表涨跌保证"
    )
    return {
        "label": label,
        "trend20": trend20,
        "trend60": trend60,
        "volatility20": volatility20,
        "detail": detail,
    }
