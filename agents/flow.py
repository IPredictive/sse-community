from .base import Agent, Prediction
from .quant import clamp, confidence_from_score, direction_text, sigmoid

class FlowAgent(Agent):
    name = "flow"
    def predict(self,df,context=None):
        if len(df)<40: return None
        c=df.close.astype(float); v=df.volume.astype(float); ret=c.pct_change()
        vol20=float(v.rolling(20).mean().iloc[-1]); vr=float(v.iloc[-1]/vol20) if vol20 else 1.0
        vr5=float(v.tail(5).mean()/vol20) if vol20 else 1.0
        up_vol=float(v[ret>0].tail(20).mean()) if (ret>0).tail(20).any() else vol20
        down_vol=float(v[ret<0].tail(20).mean()) if (ret<0).tail(20).any() else vol20
        pressure=(up_vol-down_vol)/(up_vol+down_vol or 1)
        ret5=float(c.pct_change(5).iloc[-1]); ret20=float(c.pct_change(20).iloc[-1]); up_days=int((ret.tail(10)>0).sum())
        score=0.0
        score += 0.95*clamp((vr-1)/0.6,-1,1); score += 0.70*clamp((vr5-1)/0.5,-1,1)
        score += 1.00*clamp(pressure/0.25,-1,1); score += 0.65*clamp(ret5/0.04,-1,1)
        score += 0.40*clamp(ret20/0.10,-1,1); score += 0.35*((up_days-5)/5)
        p=clamp(sigmoid(score*0.65),0.08,0.92)
        conf=confidence_from_score(score,0.9 if 0.75<vr<1.35 else 1.0)
        reason=(f"量价{direction_text(p)}；当日量比20日={vr:.2f}，5日均量比={vr5:.2f}；涨跌量能差={pressure:+.2f}；5日动量={ret5:.1%}；近10日上涨{up_days}天")
        return Prediction(p,reason,conf)
