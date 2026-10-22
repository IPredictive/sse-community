"""Optional AGNES AI review layer for SSE forecasts.

This is an advisory layer: it may explain conflicts and risks, but it does not
change the deterministic ensemble probability. If configuration is absent or
the endpoint fails, the existing pipeline continues unchanged.

Configuration (GitHub Actions Secrets / Variables):
  AGNES_API_URL   Full OpenAI-compatible chat-completions endpoint URL
  AGNES_API_KEY   Secret API key
  AGNES_MODEL     Model identifier
"""
import json
import os
import urllib.request
from typing import Any


def _response_text(payload: dict[str, Any]) -> str:
    """Read common OpenAI-compatible chat or Responses API response shapes."""
    choices = payload.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "".join(
                str(part.get("text", "")) for part in content
                if isinstance(part, dict)
            ).strip()

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts = []
    for item in payload.get("output") or []:
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                parts.append(str(part.get("text", "")))
    return "".join(parts).strip()


def review_forecast(base_date, df, predictions, ensemble, context=None):
    """Return a concise advisory review, or None when AGNES is not configured."""
    endpoint = (os.getenv("AGNES_API_URL") or "https://apihub.agnes-ai.com/v1/chat/completions").strip()
    api_key = (os.getenv("AGNES_API_KEY") or "").strip()
    model = (os.getenv("AGNES_MODEL") or "agnes-3.0-flash").strip()
    if not api_key:
        print("[AGNES] review skipped: AGNES_API_KEY is not configured")
        return None

    try:
        latest = df.iloc[-1]
        previous_close = float(df.iloc[-2]["close"]) if len(df) >= 2 else None
        latest_close = float(latest["close"])
        daily_return = (
            (latest_close / previous_close - 1.0) if previous_close else None
        )
        analyst_rows = []
        for name, pred in predictions.items():
            analyst_rows.append({
                "agent": name,
                "prob_up": round(float(pred.prob_up), 4),
                "confidence": round(float(pred.confidence), 4),
                "reason": str(pred.reason)[:350],
            })

        ctx = context or {}
        news = [
            str(item.get("title", ""))[:180]
            for item in (ctx.get("news_items") or [])[:8]
            if isinstance(item, dict) and item.get("title")
        ]
        macro = [
            str(item.get("title", ""))[:180]
            for item in (ctx.get("macro_items") or [])[:6]
            if isinstance(item, dict) and item.get("title")
        ]
        payload_for_review = {
            "market": {
                "index": "上证指数",
                "as_of_date": str(base_date),
                "close": latest_close,
                "latest_daily_return": round(daily_return, 6) if daily_return is not None else None,
            },
            "analysts": analyst_rows,
            "ensemble": {
                "prob_up": round(float(ensemble.prob_up), 4),
                "confidence": round(float(ensemble.confidence), 4),
                "reason": str(ensemble.reason)[:900],
            },
            "news_titles": news,
            "macro_titles": macro,
            "overseas_returns": ctx.get("overseas") or {},
        }
        system_prompt = (
            "你是 AGNES AI，负责审查中国上证指数的多智能体研究报告。"
            "你是独立审查员，不是交易执行器。只能使用输入数据，不要编造事实或补充未提供的实时行情。"
            "重点检查分析师分歧、证据不足、新闻时效、可能的反方解释和主要风险。"
            "不要更改或重新计算综合上涨概率，不要输出买卖指令。"
            "只返回严格 JSON，字段为："
            '{"assessment":"不超过70字的总体审查","counterarguments":["最多2条反方观点"],'
            '"risk_flags":["最多3条风险或数据限制"],"evidence_gaps":["最多2条待验证信息"]}。'
            "每条简短、具体；若证据不足，明确说明。"
        )
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload_for_review, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "max_tokens": 420,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=18) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        raw = _response_text(response_payload)
        if raw.startswith("```"):
            raw = raw.strip("`").replace("json\\n", "", 1).strip()
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("AGNES response is not a JSON object")

        def clean_list(value, limit):
            if not isinstance(value, list):
                return []
            return [str(item).strip()[:180] for item in value if str(item).strip()][:limit]

        review = {
            "assessment": str(result.get("assessment", "")).strip()[:280],
            "counterarguments": clean_list(result.get("counterarguments"), 2),
            "risk_flags": clean_list(result.get("risk_flags"), 3),
            "evidence_gaps": clean_list(result.get("evidence_gaps"), 2),
        }
        if not any(review.values()):
            raise ValueError("AGNES response contains no usable review fields")
        print("[AGNES] advisory review completed")
        return review
    except Exception as exc:
        # Do not let an external model outage block daily predictions.
        print(f"[AGNES] review unavailable; keeping existing ensemble unchanged: {type(exc).__name__}: {exc}")
        return None


def format_review(review):
    """Compact Chinese note suitable for the existing dashboard reason field."""
    if not review:
        return ""
    parts = []
    if review.get("assessment"):
        parts.append("AGNES审查：" + review["assessment"])
    if review.get("counterarguments"):
        parts.append("反方观点：" + "；".join(review["counterarguments"]))
    if review.get("risk_flags"):
        parts.append("风险提示：" + "；".join(review["risk_flags"]))
    if review.get("evidence_gaps"):
        parts.append("待核实：" + "；".join(review["evidence_gaps"]))
    return "｜".join(parts)[:700]
