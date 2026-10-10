import json, os, urllib.request

def call_llm(role, task, payload):
    key=os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    model=os.getenv("OPENAI_MODEL")
    if not model:
        print("LLM skipped: OPENAI_MODEL is not set")
        return None
    prompt=(
        "你是专业的中国A股研究员。你的任务是分析下一交易日上证指数。"
        "只使用提供的数据和信息，不编造事实，不使用未来信息。"
        "请严格返回JSON，不要Markdown代码块。"
        '{"prob_up":0到1之间的数字,"confidence":0到1之间的数字,"reason":"不超过120字"}。'
        f"\n你的角色：{role}\n任务：{task}\n输入数据：{json.dumps(payload,ensure_ascii=False)}"
    )
    try:
        body={"model":model,"input":[{"role":"user","content":prompt}]}
        req=urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            method="POST")
        with urllib.request.urlopen(req,timeout=60) as r:
            obj=json.loads(r.read())
        text=obj.get("output_text","").strip()
        if not text:
            parts=[]
            for item in obj.get("output",[]):
                for c in item.get("content",[]):
                    if c.get("type")=="output_text": parts.append(c.get("text",""))
            text="".join(parts).strip()
        if text.startswith("```"):
            text=text.strip("`").replace("json\n","",1).strip()
        result=json.loads(text)
        p=float(result["prob_up"]); c=float(result.get("confidence",0.6))
        if 0<=p<=1 and 0<=c<=1:
            return p,c,str(result.get("reason","AI分析"))
    except Exception as e:
        print(f"LLM {role} skipped: {e}")
    return None
