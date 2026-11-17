from .common import result

def analyze(ctx):
    o=ctx.context.get("overseas",{}) or {}
    sp=float(o.get("标普500",0)); nq=float(o.get("纳斯达克",0)); hk=float(o.get("恒生指数",0)); fx=float(o.get("美元人民币",0))
    score=0.35*sp+0.30*nq+0.25*hk-0.10*fx
    p=0.5+0.28*max(-1,min(1,score/0.03)); c=0.45+0.25*min(1,abs(score)/0.03)
    return result("global",p,c,f"全球风险雷达：标普{sp:+.2%}，纳指{nq:+.2%}，恒指{hk:+.2%}，美元人民币{fx:+.2%}",[f"global_score={score:+.3%}"])
