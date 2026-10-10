import numpy as np,pandas as pd

def _clean(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    cols = ["date","open","high","low","close","volume"]
    if not all(c in df.columns for c in cols):
        return pd.DataFrame()
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[cols].dropna(subset=["date","close"]).sort_values("date").drop_duplicates("date")

def _eastmoney():
    import requests
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": "1.000001",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56",
        "klt": "101",
        "fqt": "1",
        "beg": "19900101",
        "end": "20500101",
    }
    r = requests.get(url, params=params, timeout=20, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    data = r.json().get("data") or {}
    rows = data.get("klines") or []
    out = []
    for row in rows:
        parts = row.split(",")
        if len(parts) >= 6:
            out.append({
                "date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
            })
    return _clean(pd.DataFrame(out))

def fetch_sse():
    sources = []

    # Direct Eastmoney history feed. This is independent of AKShare's
    # function wrappers and is used first so a stale wrapper cannot freeze
    # the dashboard at an old trading date.
    try:
        df = _eastmoney()
        if not df.empty:
            sources.append((df["date"].max(), "eastmoney-direct", df))
    except Exception as e:
        print(f"[data] eastmoney-direct failed: {e}")

    import akshare as ak
    for name, loader in [
        ("eastmoney-akshare", lambda: ak.stock_zh_index_daily_em(
            symbol="sh000001", start_date="19900101", end_date="20500101"
        )),
        ("sina", lambda: ak.stock_zh_index_daily(symbol="sh000001")),
    ]:
        try:
            clean = _clean(loader())
            if not clean.empty:
                sources.append((clean["date"].max(), name, clean))
        except Exception as e:
            print(f"[data] {name} failed: {e}")

    # Tencent is the final fallback.
    try:
        df = ak.stock_zh_index_daily_tx(symbol="sh000001")
        df = df.rename(columns={"amount": "volume"})
        clean = _clean(df)
        if not clean.empty:
            sources.append((clean["date"].max(), "tencent", clean))
    except Exception as e:
        print(f"[data] tencent failed: {e}")

    if not sources:
        raise RuntimeError("Unable to fetch Shanghai Composite historical data")

    latest, source, df = max(sources, key=lambda x: x[0])
    print(f"[data] selected={source}, latest_date={latest}, rows={len(df)}")

    # Never silently pretend stale data is today's market data.
    today = pd.Timestamp.now(tz="Asia/Shanghai").date()
    if latest < today.strftime("%Y-%m-%d"):
        print(f"[data] market feed latest={latest}; today={today}; using latest available trading date")
    return df.tail(1200).reset_index(drop=True)

def make_demo(n=400,seed=7):
    rng=np.random.default_rng(seed);dates=pd.bdate_range(end=pd.Timestamp.today().normalize(),periods=n+5)[-n:];close=3000*np.exp(np.cumsum(rng.normal(0,.01,n)));op=close*(1+rng.normal(0,.002,n));return pd.DataFrame({"date":dates.strftime("%Y-%m-%d"),"open":op,"high":np.maximum(op,close)*1.003,"low":np.minimum(op,close)*.997,"close":close,"volume":rng.integers(2e8,5e8,n)})
