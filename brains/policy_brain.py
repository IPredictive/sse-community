from .common import result, news_score

def analyze(ctx):
    items=(ctx.context.get("macro_items",[]) or [])+(ctx.context.get("news_items",[]) or [])
    s=news_score(items,["政策","改革","支持","提振","扩大内需","科技","产业政策","资本市场"],["制裁","关税","监管收紧","限制","处罚","风险"])
    p=0.5+0.16*max(-1,min(1,s)); c=0.42+0.23*min(1,abs(s))
    return result("policy",p,c,f"政策传导信号={s:+.2f}；重点观察政策→行业→资金→指数链条",[x.get("title","") for x in items[:5]])
