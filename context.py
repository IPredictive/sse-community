import json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET, time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

def _get(url,timeout=12):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 sse-community/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return r.read()

def _parse_dt(value):
    if not value: return None
    try:
        from email.utils import parsedate_to_datetime
        dt=parsedate_to_datetime(value)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception: return None

def _clean_title(title):
    t=re.sub(r"\s+"," ",str(title or "")).strip()
    t=re.sub(r"\s+[-|｜]\s+(新浪财经|东方财富|证券时报网|财联社|每日经济新闻|手机新浪网|财富号|雪球|证券之星)$","",t)
    return t.strip(" -|｜")

def _norm_title(title):
    return re.sub(r"[^\w\u4e00-\u9fff]+","",_clean_title(title).lower())

def _similar(a,b):
    if not a or not b:return 0.0
    grams=lambda s:{s[i:i+2] for i in range(max(1,len(s)-1))}
    A,B=grams(a),grams(b)
    return len(A&B)/max(1,len(A|B))

def _freshness_weight(dt,now=None,half_life_hours=36):
    if not dt:return 0.45
    now=now or datetime.now(timezone.utc)
    age=max(0.0,(now-dt).total_seconds()/3600)
    return max(0.08,2**(-age/half_life_hours))

def google_news(query,limit=12,max_age_days=14,cutoff=None):
    try:
        url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":query,"hl":"zh-CN","gl":"CN","ceid":"CN:zh-Hans"})
        root=ET.fromstring(_get(url)); now=cutoff or datetime.now(timezone.utc); items=[]
        for x in root.findall("./channel/item"):
            title=x.findtext("title"); link=x.findtext("link"); pub=_parse_dt(x.findtext("pubDate")); clean=_clean_title(title)
            if not clean: continue
            if pub and cutoff is not None and pub > cutoff: continue
            if pub and (now-pub).total_seconds()>max_age_days*86400: continue
            if any(bad in clean for bad in ("股票股价","行情_走势图_资讯","股价_行情_走势图","搜索结果")): continue
            if any(_norm_title(clean)==_norm_title(old["title"]) or _similar(_norm_title(clean),_norm_title(old["title"]))>=0.78 for old in items): continue
            items.append({"title":clean,"published_at":pub.isoformat() if pub else None,"freshness_weight":round(_freshness_weight(pub,now),4),"link":link})
            if len(items)>=limit: break
        return items
    except Exception as e:
        print("news fetch skipped:",e); return []

def yahoo_return(symbol,days=5,as_of_date=None):
    try:
        if as_of_date:
            target=datetime.strptime(str(as_of_date)[:10],"%Y-%m-%d").replace(tzinfo=timezone.utc)
            end=int((target+timedelta(days=1)).timestamp()); start=int((target-timedelta(days=max(10,days*2))).timestamp())
        else:
            end=int(time.time()); start=end-days*86400
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={start}&period2={end}&interval=1d"
        obj=json.loads(_get(url)); res=obj["chart"]["result"][0]; vals=[]
        for t,c in zip(res.get("timestamp",[]),res["indicators"]["quote"][0]["close"]):
            if c is None: continue
            if as_of_date and datetime.fromtimestamp(t,tz=timezone.utc).date().isoformat()>str(as_of_date)[:10]: continue
            vals.append(float(c))
        return vals[-1]/vals[-2]-1 if len(vals)>=2 else None
    except Exception as e:
        print(f"Yahoo {symbol} skipped:",e); return None

def _collect_news(queries,limit=12,require_any=None,exclude_any=None,cutoff=None):
    items=[]; seen=set()
    for q in queries:
        for item in google_news(q,limit=8,cutoff=cutoff):
            title=item.get("title","")
            if require_any and not any(k in title for k in require_any): continue
            if exclude_any and any(k in title for k in exclude_any): continue
            key=_norm_title(title)
            if key in seen or any(_similar(key,_norm_title(old["title"]))>=0.78 for old in items): continue
            seen.add(key); items.append(item)
            if len(items)>=limit:return items
    return items

def build_context(as_of_date=None):
    cutoff=None
    if as_of_date:
        cutoff=datetime.strptime(str(as_of_date)[:10],"%Y-%m-%d").replace(hour=23,minute=59,second=59,tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
    overseas={}; symbols={"标普500":"^GSPC","纳斯达克":"^IXIC","恒生指数":"^HSI","美元人民币":"CNY=X"}
    for k,sym in symbols.items():
        r=yahoo_return(sym,as_of_date=as_of_date)
        if r is not None: overseas[k]=r
    news_items=_collect_news(["A股","上证指数","沪深股市","中国股市","A股 市场"],limit=12,require_any=["A股","上证","沪深","中国股市","股市"],exclude_any=["日本股市","日本央行","韩国股市","美股","纳斯达克","标普500","港股"],cutoff=cutoff)
    macro_items=_collect_news(["中国央行 货币政策","国务院 财政政策","中国宏观经济 股市","降准 降息 A股","中国资产 机构"],limit=12,require_any=["中国","央行","国务院","财政","货币","A股","沪深","中国资产","宏观经济"],exclude_any=["日本股市","日本央行","韩国股市","美股","纳斯达克","标普500","港股"],cutoff=cutoff)
    return {"news_items":news_items,"macro_items":macro_items,"news_titles":[x["title"] for x in news_items],"macro_titles":[x["title"] for x in macro_items],"overseas":overseas}
