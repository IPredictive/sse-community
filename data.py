import requests
import pandas as pd

def fetch_sse():
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {"secid":"1.000001","fields1":"f1,f2,f3,f4,f5,f6","fields2":"f51,f52,f53,f54,f55,f56","klt":"101","fqt":"1","beg":"19900101","end":"20500101"}
    response = requests.get(url, params=params, timeout=25, headers={"User-Agent":"Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json().get("data") or {}
    rows = []
    for line in payload.get("klines") or []:
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({"date":parts[0],"open":parts[1],"close":parts[2],"high":parts[3],"low":parts[4],"volume":parts[5]})
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("Eastmoney did not return Shanghai Composite daily data")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ("open","high","low","close","volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["date","open","high","low","close","volume"]].dropna(subset=["date","close"]).sort_values("date").drop_duplicates("date").tail(1200).reset_index(drop=True)
