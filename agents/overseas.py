import numpy as np
from .base import Agent, Prediction
from .quant import clamp, confidence_from_score, direction_text, sigmoid

class OverseasAgent(Agent):
    name = "overseas"
    def predict(self,df,context=None):
        vals={k:float(v) for k,v in (context or {}).get("overseas",{}).items() if isinstance(v,(int,float)) and np.isfinite(v)}
        if not vals: return Prediction(0.5,"暂无海外市场数据，外部环境保持中性",0.35)
        score=0.0; details=[]
        for k,v in vals.items():
            if "美元人民币" in k: score += -0.75*clamp(v/0.01,-1,1)
            elif "恒生" in k: score += 0.85*clamp(v/0.025,-1,1)
            elif "纳斯达克" in k: score += 0.70*clamp(v/0.025,-1,1)
            elif "标普" in k: score += 0.60*clamp(v/0.02,-1,1)
            details.append(f"{k}{v:+.2%}")
        p=clamp(sigmoid(score*0.72),0.15,0.85); conf=confidence_from_score(score,0.9 if len(vals)<3 else 1.0)
        return Prediction(p,f"海外环境{direction_text(p)}；{'；'.join(details)}",conf)
