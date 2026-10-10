import numpy as np
from .base import Agent, Prediction
from .quant import atr, clamp, confidence_from_score, direction_text, rsi, sigmoid

class TechnicalAgent(Agent):
    name="technical"

    def predict(self, df, context=None):
        if len(df) < 60:
            return None
        c=df.close.astype(float)
        h=df.high.astype(float)
        l=df.low.astype(float)
        ma5=c.rolling(5).mean().iloc[-1]
        ma20=c.rolling(20).mean().iloc[-1]
        ma60=c.rolling(60).mean().iloc[-1]
        ema12=c.ewm(span=12,adjust=False).mean()
        ema26=c.ewm(span=26,adjust=False).mean()
        macd=ema12-ema26
        signal=macd.ewm(span=9,adjust=False).mean()
        hist=macd-signal
        hist_now=float(hist.iloc[-1]); hist_prev=float(hist.iloc[-2])
        rv=rsi(c,14)
        ret5=float(c.pct_change(5).iloc[-1])
        ret20=float(c.pct_change(20).iloc[-1])
        ret60=float(c.pct_change(60).iloc[-1])
        atr_pct=atr(df,14)/float(c.iloc[-1])
        bb_mid=c.rolling(20).mean(); bb_std=c.rolling(20).std()
        upper=bb_mid+2*bb_std; lower=bb_mid-2*bb_std
        bb_pos=(float(c.iloc[-1])-float(lower.iloc[-1]))/(float(upper.iloc[-1]-lower.iloc[-1]) or 1)
        score=0.0
        score += 1.25 if ma5>ma20 else -1.25
        score += 0.85 if ma20>ma60 else -0.85
        score += 0.70 if hist_now>0 else -0.70
        score += 0.45 if hist_now>hist_prev else -0.45
        score += 0.75*clamp((rv-50)/20,-1,1)
        score += 0.65*clamp(ret5/0.04,-1,1)
        score += 0.45*clamp(ret20/0.10,-1,1)
        score += 0.25*clamp(ret60/0.18,-1,1)
        if bb_pos > 0.92: score -= 0.45
        elif bb_pos < 0.08: score += 0.35
        p=clamp(sigmoid(score*0.72),0.08,0.92)
        evidence=1.0 if abs(ma5-ma20)/float(c.iloc[-1])>0.006 else 0.8
        conf=confidence_from_score(score,evidence)
        reason=(f"趋势{direction_text(p)}；MA5={'高于' if ma5>ma20 else '低于'}MA20，"
                f"MA20={'高于' if ma20>ma60 else '低于'}MA60；MACD柱{('改善' if hist_now>hist_prev else '走弱')}；"
                f"RSI={rv:.0f}；5日动量={ret5:.1%}；波动率={atr_pct:.1%}")
        return Prediction(p,reason,conf)
