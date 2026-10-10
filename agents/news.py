from .base import Agent, Prediction
from .quant import clamp, confidence_from_score, direction_text, title_sentiment

def _items(context,key,fallback):
    c=context or {}
    items=c.get(key)
    if items:return items[:20]
    return [{"title":x,"freshness_weight":1.0} for x in c.get(fallback,[])[:20]]

class SentimentAgent(Agent):
    name="sentiment"
    def predict(self,df,context=None):
        items=_items(context,"news_items","news_titles")
        if not items:return Prediction(0.5,"暂无新闻数据，情绪保持中性",0.35)
        s,e,num=title_sentiment(items)
        p=clamp(0.5+0.34*s,0.12,0.88)
        conf=confidence_from_score(s*2.0,e)
        return Prediction(p,f"读取{num}条去重新闻；时间衰减加权后情绪{direction_text(p)}，综合情绪分={s:+.2f}",conf)

class MacroAgent(Agent):
    name="macro"
    def predict(self,df,context=None):
        items=_items(context,"macro_items","macro_titles")
        if not items:return Prediction(0.5,"暂无宏观政策新闻，宏观判断保持中性",0.35)
        s,e,num=title_sentiment(items)
        p=clamp(0.5+0.30*s,0.15,0.85)
        conf=confidence_from_score(s*1.7,e)
        return Prediction(p,f"读取{num}条去重宏观/政策新闻；时间衰减加权后政策环境{direction_text(p)}，情绪分={s:+.2f}",conf)
