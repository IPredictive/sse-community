import numpy as np
from .common import result, pct, norm

def analyze(ctx):
    df=ctx.df; close=df["close"].astype(float); regime=ctx.regime
    r20=pct(close,20) or 0; r60=pct(close,60) or 0
    breadth=norm(r20,0.06)*0.55+norm(r60,0.12)*0.45
    p=0.5+0.22*breadth
    if regime.get("label")=="高波动风险": p=0.5+0.75*(p-0.5)
    c=0.55+0.20*abs(breadth)
    return result("market_structure",p,c,f"市场结构：20日{r20:+.2%}，60日{r60:+.2%}，状态={regime.get('label','未知')}", ["指数趋势","波动状态"])
