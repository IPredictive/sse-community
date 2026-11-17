"""Responsive HTML view for the daily brain performance and risk time series."""
import html

A9_NAMES = {
    "A9_technical": "A9 技术脑", "A9_quant": "A9 量化脑",
    "A9_market_structure": "A9 市场结构脑", "A9_macro": "A9 宏观经济脑",
    "A9_policy": "A9 政策政治脑", "A9_geopolitical": "A9 地缘军事脑",
    "A9_global": "A9 全球市场脑", "A9_money_sentiment": "A9 资金情绪脑",
    "A9_SUPER_CHIEF": "A9 超级首席",
}
TRADITIONAL_NAMES = {
    "technical": "传统技术面", "flow": "传统资金面", "macro": "传统宏观面",
    "sentiment": "传统市场情绪", "overseas": "传统海外市场",
    "CHIEF_ANALYST": "传统首席",
}


def _spark(values, suffix="%"):
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return "<span class='ph-empty'>样本积累中</span>"
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    pts = []
    for i, value in enumerate(vals):
        x = 2 + i * 116 / (len(vals)-1)
        y = 25 - (value-lo) / span * 20
        pts.append(f"{x:.1f},{y:.1f}")
    label = f"{vals[-1]:.1%}" if suffix == "%" else f"{vals[-1]:.4f}"
    return (f"<svg class='ph-spark' viewBox='0 0 120 30' role='img' aria-label='滚动趋势'>"
            f"<polyline points='{' '.join(pts)}' fill='none' stroke='#7db8ff' "
            f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
            f"<text x='118' y='9' text-anchor='end'>{html.escape(label)}</text></svg>")


def build_performance_dashboard(history):
    history = history or {}
    records = history.get("records", [])
    risks = history.get("risk_history", [])
    rows = []
    by_agent = {}
    for item in records:
        by_agent.setdefault(item.get("agent"), []).append(item)
    for agent, items in sorted(by_agent.items(), key=lambda pair: (pair[1][-1].get("family"), pair[0])):
        latest = items[-1]
        name = A9_NAMES.get(agent, TRADITIONAL_NAMES.get(agent, agent))
        acc = [x["rolling20_accuracy"] for x in items[-60:]]
        brier = [x["rolling20_brier"] for x in items[-60:]]
        regime = latest.get("regime", "未知")
        rows.append(
            "<div class='ph-row'>"
            f"<b>{html.escape(name)}</b><span>{html.escape(latest['date'])}</span>"
            f"<span>{html.escape(regime)}</span>"
            f"<strong>{latest['rolling20_accuracy']:.1%}</strong>{_spark(acc)}"
            f"<strong>{latest['rolling20_brier']:.4f}</strong>{_spark(brier, 'brier')}"
            f"<small>累计 n={latest['samples']} · 当日 Brier {latest['daily_brier']:.4f}</small>"
            "</div>"
        )
    if not rows:
        rows.append("<div class='ph-empty'>等待第一批预测完成下一交易日结算；不会用未结算数据绘制准确率。</div>")
    risk_rows = []
    for item in risks[-15:]:
        risk_rows.append(
            f"<div class='ph-risk-row'><b>{html.escape(item['date'])}</b>"
            f"<span>{'A9 九脑' if item['family']=='A9' else '传统专业脑'}</span>"
            f"<strong>{item['probability_spread']:.1%}</strong>"
            f"<span>{item['direction_disagreement']} 个方向分歧</span>"
            f"<em class='{'hot' if item['triggered'] else ''}'>"
            f"{'触发 35% 风险线' if item['triggered'] else '风险线内'}</em></div>"
        )
    if not risk_rows:
        risk_rows.append("<div class='ph-empty'>暂无可计算的多脑风险记录。</div>")
    comparison = history.get("paired_comparison", {})
    paired_n = int(comparison.get("paired_dates", 0))
    if paired_n:
        a9m = comparison.get("a9") or {}
        oldm = comparison.get("traditional") or {}
        comparison_html = (
            f"<div class='ph-compare-grid'><div><b>A9 SUPER CHIEF</b>"
            f"<strong>准确率 {a9m.get('accuracy', 0):.1%} · Brier {a9m.get('brier', 0):.4f}</strong></div>"
            f"<div><b>传统 CHIEF_ANALYST</b>"
            f"<strong>准确率 {oldm.get('accuracy', 0):.1%} · Brier {oldm.get('brier', 0):.4f}</strong></div></div>"
        )
    else:
        comparison_html = "<div class='ph-empty'>尚无同日期成熟配对样本，暂不比较胜负。</div>"
    status_labels = {
        "collecting": "样本积累中，暂不比较胜负",
        "provisional_comparison": "仅作描述性观察，尚未达到判断门槛",
        "evidence_favors_a9": "配对 Brier 证据倾向 A9（仍需持续监测）",
        "evidence_favors_traditional": "配对 Brier 证据倾向传统 AI",
        "no_clear_brier_advantage": "目前没有明确的 Brier 优势证据",
    }
    if paired_n < 30:
        gate_text = f"已积累 {paired_n}/30 个配对样本；尚不展示胜负结论。"
    elif paired_n < 60:
        gate_text = f"已积累 {paired_n}/60 个配对样本；当前仅作描述性观察。"
    else:
        ci = comparison.get("paired_brier_delta_ci95_block5")
        ci_text = f"；Brier 差值 95% 区间 [{ci[0]:.5f}, {ci[1]:.5f}]" if ci else ""
        gate_text = f"{status_labels.get(comparison.get('status'), '评估中')}（{paired_n} 个配对日期）{ci_text}。"

    a9_n = sum(1 for x in records if x.get("family") in ("A9", "A9_SUPER_CHIEF"))
    legacy_n = sum(1 for x in records if x.get("family") == "traditional")
    return f"""
<section class="ph-center" id="brain-performance">
 <div class="ph-head"><div><span>DAILY PERFORMANCE · OUTCOME TRACKER</span>
 <h2>九脑每日表现曲线与风险时间轴</h2>
 <p>按预测日期逐日留痕；只在下一交易日收盘后计分。当前历史记录 {len(records)} 条，风险记录 {len(risks)} 天。</p></div>
 <a href="./brain-performance-history.json" target="_blank" rel="noopener">查看完整历史 JSON ↗</a></div>
 <div class="ph-legend"><span>滚动 20 次准确率</span><span>滚动 20 次 Brier</span>
 <span>A9 记录 {a9_n} 条</span><span>传统 AI 记录 {legacy_n} 条</span></div>
 <div class="ph-table-head"><span>分析脑</span><span>最近结算日</span><span>当时市场状态</span><span>滚动准确率</span><span>准确率曲线</span><span>滚动 Brier</span><span>Brier 曲线</span></div>
 {''.join(rows)}
 <div class="ph-compare"><h3>A9 与传统 AI：同日期独立结算对照</h3>
 <p>{html.escape(gate_text)}</p>{comparison_html}
 <p>市场状态分层：{html.escape('；'.join(f"{k} n={v.get('samples',0)} ({v.get('evidence_status')})" for k,v in comparison.get('regimes',{}).items()) or '样本积累中')}</p>
 <p>规则：至少 60 个同日期成熟配对样本，并以 5 日移动区块 Bootstrap 95% 区间不跨 0 才提示方向性证据；这仍不是收益保证。</p></div>
 <div class="ph-risk"><h3>每日多脑分歧与风险变化</h3><p>同一预测日优先检查 A9 专业脑；A9 不足两个时才使用传统专业脑。概率最大差达到 35 个百分点即触发复核。</p>
 {''.join(risk_rows)}</div>
 <div class="ph-note">比较纪律：A9 与传统 AI 独立统计；A9 需先积累成熟结算样本，再做同日期、同市场状态的配对样本外比较。未达到证据门槛时只显示“积累中”，不宣称优胜。</div>
</section>
"""
