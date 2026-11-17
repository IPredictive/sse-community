import numpy as np
from .common import result

def analyze(ctx):
    c=ctx.df["close"].astype(float)
    def ma(n): return float(c.tail(n).mean()) if len(c)>=n else None
    m5,m20,m60=ma(5),ma(20),ma(60); last=float(c.iloc[-1])
    score=0
    if m5 and last>m5: score+=0.25
    if m20 and last>m20: score+=0.30
    if m60 and last>m60: score+=0.25
    if m5 and m20 and m5>m20: score+=0.20
    p=0.5+0.38*score if score>=0 else 0.5+0.38*score
    c=0.48+0.35*abs(score)
    return result("technical",p,c,f"技术面：收盘{last:.2f}；MA5={m5:.2f}，MA20={m20:.2f}，MA60={m60:.2f}",["均线趋势","价格位置"])
