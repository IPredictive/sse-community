from .common import result

def analyze(ctx):
    items=ctx.context.get("news_items",[]) or []
    pos=("放量","资金流入","北向","融资","ETF","成交额","增量资金")
    neg=("资金流出","缩量","减仓","赎回","抛售")
    score=0.0
    for x in items[:12]:
        t=x.get("title",""); score += sum(t.count(k) for k in pos)-sum(t.count(k) for k in neg)
    score=max(-1,min(1,score/8.0)); p=0.5+0.18*score; c=0.40+0.20*abs(score)
    return result("money_sentiment",p,c,f"资金/情绪净信号={score:+.2f}；新闻资金词与市场成交信息联合观察",[x.get("title","") for x in items[:4]])
