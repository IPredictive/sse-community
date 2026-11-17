"""HTML dashboard for the A9 nine-brain score and risk center."""
import html

A9_NAMES = {
    "technical": "技术脑", "quant": "量化脑", "market_structure": "市场结构脑",
    "macro": "宏观经济脑", "policy": "政策政治脑", "geopolitical": "地缘军事脑",
    "global": "全球市场脑", "money_sentiment": "资金情绪脑",
}
TRADITIONAL_NAMES = {
    "technical": "技术面", "flow": "资金面", "macro": "宏观面",
    "sentiment": "市场情绪", "overseas": "海外市场", "CHIEF_ANALYST": "传统首席",
}
REGIME_ORDER = ("上行趋势", "震荡/趋势转换", "下行趋势")


def _safe(value):
    return html.escape(str(value if value is not None else "—"))


def _pct(value):
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "—"


def _metric_text(metrics):
    if not metrics:
        return "待结算", "样本 0"
    return _pct(metrics.get("accuracy")), f"样本 {metrics.get('samples', 0)}"


def _status(metrics):
    if not metrics or int(metrics.get("samples", 0)) < 8:
        return "样本不足", "pending"
    accuracy = float(metrics.get("accuracy", 0))
    brier = float(metrics.get("brier", 1))
    recent = float(metrics.get("recent20_accuracy", accuracy))
    if accuracy < .45 or brier > .30 or recent < accuracy - .10:
        return "异常观察", "warning"
    return "运行正常", "ok"


def _risk_snapshot(predictions, a9=True):
    prefix = "A9_" if a9 else ""
    keys = list(A9_NAMES) if a9 else list(TRADITIONAL_NAMES)
    values = []
    for key in keys:
        row = predictions.get(prefix + key)
        if row is not None:
            try:
                values.append(float(row["prob_up"]))
            except (KeyError, TypeError, ValueError):
                pass
    if len(values) < 2:
        return None
    spread = max(values) - min(values)
    bullish = sum(p > .5 for p in values)
    bearish = len(values) - bullish
    dissent = min(bullish, bearish)
    return {
        "count": len(values), "spread": spread, "dissent": dissent,
        "triggered": spread >= .35,
    }


def build_brain_dashboard(scorecard, predictions, latest_date, current_regime):
    """Build a self-contained responsive dashboard section."""
    scorecard = scorecard or {}
    predictions = predictions or {}
    a9_scores = scorecard.get("a9_specialists", {})
    legacy_scores = scorecard.get("brains", {})
    regime_scores = scorecard.get("regime_breakdown", {})

    # Current nine-brain probabilities and settled outcome statistics.
    a9_rows = []
    for key, name in A9_NAMES.items():
        live = predictions.get("A9_" + key)
        metrics = a9_scores.get(key, {}).get("global")
        acc, samples = _metric_text(metrics)
        status, status_class = _status(metrics)
        probability = _pct(live.get("prob_up")) if live else "待生成"
        a9_rows.append(
            f'<div class="nb-brain-row"><b>{_safe(name)}</b>'
            f'<strong>{probability}</strong><span>{acc}</span><small>{samples}</small>'
            f'<em class="nb-status {status_class}">{status}</em></div>'
        )
    chief_live = predictions.get("A9_SUPER_CHIEF")
    chief_score = scorecard.get("a9_chief", {}).get("global")
    if chief_score is None:
        chief_score = legacy_scores.get("A9_SUPER_CHIEF")
    chief_acc, chief_samples = _metric_text(chief_score)
    a9_rows.append(
        f'<div class="nb-brain-row nb-chief-row"><b>九脑超级首席</b>'
        f'<strong>{_pct(chief_live.get("prob_up")) if chief_live else "待生成"}</strong>'
        f'<span>{chief_acc}</span><small>{chief_samples}</small>'
        f'<em class="nb-status {_status(chief_score)[1]}">{_status(chief_score)[0]}</em></div>'
    )

    # Traditional agents are kept separate; never borrow their outcomes for A9.
    traditional_rows = []
    for key, name in TRADITIONAL_NAMES.items():
        live = predictions.get(key)
        metrics = legacy_scores.get(key)
        acc, samples = _metric_text(metrics)
        status, cls = _status(metrics)
        traditional_rows.append(
            f'<div class="nb-compare-row"><b>{_safe(name)}</b>'
            f'<strong>{_pct(live.get("prob_up")) if live else "—"}</strong>'
            f'<span>{acc}</span><small>{samples}</small>'
            f'<em class="nb-status {cls}">{status}</em></div>'
        )

    # Market regime reliability: show only measured records and make small samples explicit.
    regimes = []
    regime_names = list(REGIME_ORDER)
    for brain, per_regime in regime_scores.items():
        for regime in per_regime:
            if regime not in regime_names:
                regime_names.append(regime)
    for regime in regime_names:
        candidates = []
        for brain, per_regime in regime_scores.items():
            metrics = per_regime.get(regime)
            if metrics and int(metrics.get("samples", 0)) >= 8:
                candidates.append((float(metrics.get("brier", 1)), brain, metrics))
        candidates.sort(key=lambda item: (item[0], -float(item[2].get("accuracy", 0))))
        if candidates:
            _, winner, metrics = candidates[0]
            display = A9_NAMES.get(winner.removeprefix("A9_"), TRADITIONAL_NAMES.get(winner, winner))
            regimes.append(
                f'<div class="nb-regime-row"><b>{_safe(regime)}</b>'
                f'<span>当前样本较充分的领先脑：{_safe(display)}</span>'
                f'<strong>准确率 {_pct(metrics.get("accuracy"))}</strong>'
                f'<small>Brier {float(metrics.get("brier", 0)):.3f} · n={metrics.get("samples", 0)}</small></div>'
            )
        else:
            regimes.append(
                f'<div class="nb-regime-row"><b>{_safe(regime)}</b>'
                f'<span>样本不足，暂不评选领先脑</span><small>每个脑至少需要 8 条该状态的已结算预测</small></div>'
            )

    # Anomaly watch is a transparent monitoring heuristic, not an automatic weight change.
    anomaly_items = []
    for brain, metrics in legacy_scores.items():
        status, cls = _status(metrics)
        if cls == "warning":
            anomaly_items.append(
                f'<div class="nb-alert-row"><b>{_safe(TRADITIONAL_NAMES.get(brain, brain))}</b>'
                f'<span>准确率 {_pct(metrics.get("accuracy"))} · Brier {float(metrics.get("brier", 0)):.3f} · n={metrics.get("samples", 0)}</span>'
                f'<em>异常观察</em></div>'
            )
    for brain, item in a9_scores.items():
        metrics = item.get("global")
        status, cls = _status(metrics)
        if cls == "warning":
            anomaly_items.append(
                f'<div class="nb-alert-row"><b>{_safe(A9_NAMES.get(brain, brain))}</b>'
                f'<span>准确率 {_pct(metrics.get("accuracy"))} · Brier {float(metrics.get("brier", 0)):.3f} · n={metrics.get("samples", 0)}</span>'
                f'<em>异常观察</em></div>'
            )
    if not anomaly_items:
        anomaly_items.append('<div class="nb-empty">目前没有达到异常观察阈值的脑；样本不足的脑不代表表现正常。</div>')

    a9_risk = _risk_snapshot(predictions, True)
    traditional_risk = _risk_snapshot(predictions, False)
    active_risk = a9_risk or traditional_risk
    risk_source = "A9 九脑" if a9_risk else "传统五专业脑" if traditional_risk else "暂无足够实时预测"
    if active_risk:
        spread_text = _pct(active_risk["spread"])
        risk_state = "高分歧风险" if active_risk["triggered"] else "分歧在阈值内"
        risk_class = "warning" if active_risk["triggered"] else "ok"
        risk_detail = f'参与 {active_risk["count"]} 个脑 · 方向分歧 {active_risk["dissent"]} 个 · 阈值 35%'
    else:
        spread_text, risk_state, risk_class, risk_detail = "—", "等待预测数据", "pending", "至少需要两个专业脑的实时预测"
    historical_risk = scorecard.get("risk_review") or {}
    historical_risk_text = (
        f'最近已结算日 { _safe(historical_risk.get("base_date")) }：'
        f'概率差 { _pct(historical_risk.get("probability_spread")) }，'
        f'{"触发复核" if historical_risk.get("triggered") else "未触发"}'
        if historical_risk else "尚无已结算风险审查记录"
    )

    # Side-by-side evidence counts prevent comparing A9 with legacy rows as if they were the same cohort.
    a9_total = sum(int(v.get("samples", 0)) for v in a9_scores.values())
    legacy_total = sum(int(v.get("samples", 0)) for v in legacy_scores.values())
    walk = scorecard.get("walk_forward") or {}
    walk_note = (
        f'严格样本外比较：等权 Brier {float(walk.get("equal_weight_brier", 0)):.4f}；'
        f'自适应 Brier {float(walk.get("adaptive_weight_brier", 0)):.4f}；'
        f'评估日期 {walk.get("evaluation_dates", 0)}'
        if walk else "样本外权重评估尚在积累"
    )

    return f"""
<section class="nb-center" id="brain-center">
  <div class="nb-head">
    <div><div class="nb-kicker">A9 · NINE-BRAIN INTELLIGENCE</div>
      <h2>九脑实战评分与风险中心</h2>
      <p>预测基准日 {_safe(latest_date)} · 当前市场状态 {_safe(current_regime)} · 只用已结算结果评分</p>
    </div>
    <div class="nb-risk-chip {risk_class}"><span>实时分歧</span><b>{spread_text}</b><strong>{risk_state}</strong></div>
  </div>
  <div class="nb-risk-banner {risk_class}"><b>风险审查 · {risk_state}</b><span>{_safe(risk_source)}：{_safe(risk_detail)}</span><small>{_safe(historical_risk_text)}</small></div>
  <div class="nb-panel">
    <div class="nb-panel-title"><h3>① A9 九脑实时预测与独立成绩</h3><span>概率 · 准确率 · 已结算样本</span></div>
    <div class="nb-table-head"><span>分析脑</span><span>当前上涨概率</span><span>历史准确率</span><span>样本数</span><span>状态</span></div>
    {''.join(a9_rows)}
    <p class="nb-footnote">A9 八个专业脑与九脑超级首席独立记录；未成熟的预测不计入准确率。</p>
  </div>
  <div class="nb-two-col">
    <div class="nb-panel">
      <div class="nb-panel-title"><h3>② 不同市场状态下谁更可靠</h3><span>至少 8 个样本才列为候选</span></div>
      {''.join(regimes)}
      <p class="nb-footnote">按 Brier 分数由低到高识别领先者；样本不足不排名。</p>
    </div>
    <div class="nb-panel">
      <div class="nb-panel-title"><h3>③ 异常脑监控</h3><span>透明监控规则</span></div>
      {''.join(anomaly_items)}
      <p class="nb-footnote">样本数至少 8，且准确率低于 45%、Brier 高于 0.30 或近 20 次准确率较总体低 10 个百分点，触发观察；不自动修改权重。</p>
    </div>
  </div>
  <div class="nb-panel">
    <div class="nb-panel-title"><h3>④ 传统 AI 与 A9 独立成绩对照</h3><span>两套样本分别统计，不混算</span></div>
    <div class="nb-compare-grid">
      <div><h4>A9 九脑系统 <small>已结算专业脑样本合计 {a9_total}</small></h4>
        <div class="nb-compare-header"><span>智能体</span><span>实时概率</span><span>准确率</span><span>样本</span><span>状态</span></div>
        {''.join(a9_rows)}
      </div>
      <div><h4>传统分析系统 <small>已结算样本合计 {legacy_total}</small></h4>
        <div class="nb-compare-header"><span>智能体</span><span>实时概率</span><span>准确率</span><span>样本</span><span>状态</span></div>
        {''.join(traditional_rows)}
      </div>
    </div>
    <p class="nb-footnote">{_safe(walk_note)}。样本外表现尚未证明自适应权重优于等权时，系统保持中性学习权重。</p>
  </div>
  <div class="nb-footnote nb-disclaimer">数据口径：仅纳入下一交易日收盘价已知的预测；A9 与传统脑分开计分。异常观察是风险提示，不构成投资建议，也不代表未来收益。</div>
</section>
"""
