import time
import numpy as np
import pandas as pd


def _clean(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    cols = ["date", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in cols):
        return pd.DataFrame()
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return (
        df[cols]
        .dropna(subset=["date", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _retry(name, loader, attempts=2, delay=2):
    """Retry a source briefly; log each failure but let fallback sources run."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            df = _clean(loader())
            if not df.empty:
                return df
            last_error = RuntimeError("source returned no usable rows")
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            print(f"[data] {name} attempt {attempt}/{attempts} failed: {last_error}; retrying")
            time.sleep(delay)
    print(f"[data] {name} failed after {attempts} attempts: {last_error}")
    return pd.DataFrame()


def _eastmoney():
    import requests

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": "1.000001",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "0",
        "beg": "19900101",
        "end": "20500101",
        "lmt": "10000",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json,text/plain,*/*",
        "Connection": "close",
    }
    response = requests.get(url, params=params, timeout=15, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if payload.get("rc") not in (None, 0):
        raise RuntimeError(f"Eastmoney API rc={payload.get('rc')}")
    rows = ((payload.get("data") or {}).get("klines") or [])
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
    return pd.DataFrame(out)


def _tencent_direct():
    """Direct Tencent daily K-line fallback, independent of AKShare wrappers."""
    import requests

    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": "sh000001,day,,,800,qfq"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Referer": "https://gu.qq.com/",
        "Accept": "application/json,text/plain,*/*",
    }
    response = requests.get(url, params=params, timeout=15, headers=headers)
    response.raise_for_status()
    payload = response.json()
    item = ((payload.get("data") or {}).get("sh000001") or {})
    rows = item.get("qfqday") or item.get("day") or item.get("hfqday") or []
    out = []
    for row in rows:
        if len(row) >= 6:
            out.append({
                "date": row[0],
                "open": row[1],
                "close": row[2],
                "high": row[3],
                "low": row[4],
                "volume": row[5],
            })
    return pd.DataFrame(out)


def _yahoo_chart():
    """Public Yahoo chart endpoint as an independent last-resort history source."""
    import requests

    url = "https://query1.finance.yahoo.com/v8/finance/chart/000001.SS"
    params = {"range": "max", "interval": "1d", "events": "history"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Accept": "application/json",
    }
    response = requests.get(url, params=params, timeout=20, headers=headers)
    response.raise_for_status()
    payload = response.json()
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        raise RuntimeError(f"Yahoo chart returned no result: {payload.get('chart', {}).get('error')}")
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    dates = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert("Asia/Shanghai").strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": dates,
        "open": quote.get("open", []),
        "high": quote.get("high", []),
        "low": quote.get("low", []),
        "close": quote.get("close", []),
        "volume": quote.get("volume", []),
    })


def fetch_sse():
    sources = []

    # Try independent feeds. Keep the freshest valid trading date, not simply
    # the first endpoint that responds.
    candidates = [
        ("eastmoney-direct", _eastmoney),
    ]

    try:
        import akshare as ak
        candidates.extend([
            ("eastmoney-akshare", lambda: ak.stock_zh_index_daily_em(
                symbol="sh000001", start_date="19900101", end_date="20500101"
            )),
            ("sina-akshare", lambda: ak.stock_zh_index_daily(symbol="sh000001")),
            ("tencent-akshare", lambda: ak.stock_zh_index_daily_tx(symbol="sh000001").rename(
                columns={"amount": "volume"}
            )),
        ])
    except Exception as exc:
        print(f"[data] AKShare import failed: {exc}")

    # Direct fallbacks avoid relying on AKShare's wrapper availability.
    candidates.extend([
        ("tencent-direct", _tencent_direct),
        ("yahoo-chart", _yahoo_chart),
    ])

    for name, loader in candidates:
        df = _retry(name, loader, attempts=2, delay=2)
        if not df.empty:
            latest = df["date"].max()
            sources.append((latest, name, df))
            print(f"[data] source={name}, latest_date={latest}, rows={len(df)}")

    if not sources:
        raise RuntimeError("Unable to fetch Shanghai Composite historical data from all configured sources")

    # Prefer the newest date; when dates tie, keep the earlier (primary) source.
    latest, source, df = max(sources, key=lambda item: item[0])
    today = pd.Timestamp.now(tz="Asia/Shanghai").date().strftime("%Y-%m-%d")
    print(f"[data] selected={source}, latest_date={latest}, rows={len(df)}")
    if latest < today:
        print(f"[data] WARNING: market feed latest={latest}, Shanghai date={today}; using latest available trading date")
    else:
        print(f"[data] freshness check passed: latest market date={latest}, Shanghai date={today}")

    return df.tail(1200).reset_index(drop=True)


def make_demo(n=400, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n + 5)[-n:]
    close = 3000 * np.exp(np.cumsum(rng.normal(0, .01, n)))
    op = close * (1 + rng.normal(0, .002, n))
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": op,
        "high": np.maximum(op, close) * 1.003,
        "low": np.minimum(op, close) * .997,
        "close": close,
        "volume": rng.integers(2e8, 5e8, n),
    })
