from .common import result, news_score

def analyze(ctx):
    items=ctx.context.get("macro_items",[])
    s=news_score(items,["降准","降息","宽松","刺激","增长","稳增长","消费","财政"],["加息","收紧","下行","衰退","风险","房地产下行"])
    p=0.5+0.18*max(-1,min(1,s)); c=0.45+0.25*min(1,abs(s))
    return result("macro",p,c,f"宏观政策信号={s:+.2f}，基于最新宏观新闻与政策标题",[x.get("title","") for x in items[:4]])
