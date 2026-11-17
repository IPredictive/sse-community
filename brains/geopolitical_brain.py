from .common import result, news_score

def analyze(ctx):
    items=ctx.context.get("news_items",[]) or []
    s=news_score(items,["缓和","谈判","合作","稳定","降温"],["冲突","战争","升级","制裁","关税","台湾","中东","乌克兰","航运"])
    # geopolitical signals are deliberately damped: headlines alone cannot imply a market crash.
    p=0.5+0.12*max(-1,min(1,s)); c=0.35+0.18*min(1,abs(s))
    return result("geopolitical",p,c,f"地缘风险净信号={s:+.2f}；采用低权重，避免把单条新闻等同于市场方向",[x.get("title","") for x in items[:5]])
