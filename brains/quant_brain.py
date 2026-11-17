import numpy as np
from .common import result, pct, norm

def analyze(ctx):
    close=ctx.df["close"].astype(float); ret=close.pct_change().dropna()
    r5=pct(close,5) or 0; r20=pct(close,20) or 0
    vol=float(ret.tail(20).std()) if len(ret)>=20 else 0.015
    momentum=0.60*norm(r5,0.04)+0.40*norm(r20,0.08)
    p=0.5+0.25*momentum
    if vol>0.025: p=0.5+0.75*(p-0.5)
    c=0.50+0.25*min(1,abs(momentum))
    return result("quant",p,c,f"量化因子：5日动量{r5:+.2%}，20日动量{r20:+.2%}，20日波动{vol:.2%}",["动量","波动率","风险收缩"])
