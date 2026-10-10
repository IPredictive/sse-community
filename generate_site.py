import html
from pathlib import Path

from db import init_db, load_daily, load_predictions, load_scored
from ensemble import evidence_quality, adaptive_weights, stabilize_extreme
from context import build_context

OUT = Path(__file__).parent / "site" / "index.html"


def pct(x):
    return f"{float(x):.1%}"


def direction_text(p):
    if p is None:
        return "暂无"
    p = float(p)
    if p >= 0.70:
        return "强烈偏多"
    if p >= 0.60:
        return "偏多"
    if p >= 0.53:
        return "中性偏多"
    if p > 0.47:
        return "中性"
    if p > 0.40:
        return "中性偏空"
    if p > 0.30:
        return "偏空"
    return "强烈偏空"


def tone(p):
    if p is None:
        return "neutral"
    p = float(p)
    if p > 0.53:
        return "bull"
    if p < 0.47:
        return "bear"
    return "neutral"


def bar_width(p):
    if p is None:
        return 50
    return max(4, min(96, float(p) * 100))



def make_line_svg(values, width=900, height=260, pct_axis=False):
    if not values:
        return "<div class='empty-chart'>暂无足够历史数据</div>"
    vals = [float(v) for v in values]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        lo -= 1
        hi += 1
    pad_x, pad_y = 44, 24
    inner_w, inner_h = width - 2 * pad_x, height - 2 * pad_y
    points = []
    for i, v in enumerate(vals):
        x = pad_x + inner_w * (i / max(1, len(vals) - 1))
        y = pad_y + inner_h * (1 - (v - lo) / (hi - lo))
        points.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"{pad_x},{height-pad_y} " + poly + f" {width-pad_x},{height-pad_y}"
    last_x, last_y = points[-1]
    last = vals[-1]
    label = f"{last:.1%}" if pct_axis else f"{last:.4f}"
    return f"""<svg class="line-svg" viewBox="0 0 {width} {height}" role="img">
      <defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-opacity=".25"/><stop offset="100%" stop-opacity="0"/>
      </linearGradient></defs>
      <line x1="{pad_x}" y1="{pad_y}" x2="{pad_x}" y2="{height-pad_y}" class="axis"/>
      <line x1="{pad_x}" y1="{height-pad_y}" x2="{width-pad_x}" y2="{height-pad_y}" class="axis"/>
      <polygon points="{area}" class="area"/>
      <polyline points="{poly}" class="line"/>
      <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4.5" class="point"/>
      <text x="{last_x:.1f}" y="{max(16,last_y-10):.1f}" class="value-label">{html.escape(label)}</text>
    </svg>"""


def main():
    init_db()
    d = load_daily()
    p = load_predictions()
    s = load_scored()

    latest = p.base_date.max() if not p.empty else (d.date.iloc[-1] if not d.empty else "-")
    rows = p[p.base_date == latest] if not p.empty else p

    chief = rows[rows.agent == "CHIEF_ANALYST"]
    if chief.empty:
        chief = rows[rows.agent == "ENSEMBLE"]

    prob = float(chief.prob_up.iloc[0]) if not chief.empty else None
    conf = float(chief.confidence.iloc[0]) if not chief.empty else None
    reason = str(chief.reason.iloc[0]) if not chief.empty else "暂无首席分析"

    price = float(d.close.iloc[-1]) if not d.empty else None
    prev = float(d.close.iloc[-2]) if len(d) > 1 else price
    change = (price / prev - 1) if price and prev else None

    # --- Analyst signals ---
    analyst_order = ["technical", "flow", "macro", "sentiment", "overseas"]
    names_cn = {
        "technical": "技术面",
        "flow": "资金面",
        "macro": "政策面",
        "sentiment": "市场情绪",
        "overseas": "海外环境",
    }
    analyst_rows = {str(r.agent): r for _, r in rows.iterrows()}
    analysts = [analyst_rows[k] for k in analyst_order if k in analyst_rows]

    # --- Decision breakdown: reproduce ensemble's weighting inputs ---
    try:
        live_context = build_context(as_of_date=latest) if latest != "-" else {}
    except Exception:
        live_context = {}
    preds = {k: analyst_rows[k] for k in analyst_order if k in analyst_rows}
    weights = adaptive_weights({
        k: type("Pred", (), {
            "confidence": float(v.confidence),
            "prob_up": float(v.prob_up)
        })() for k, v in preds.items()
    })
    quality = {}
    adjusted = {}
    for k, r in preds.items():
        pred_obj = type("Pred", (), {
            "confidence": float(r.confidence),
            "prob_up": float(r.prob_up)
        })()
        quality[k] = evidence_quality(pred_obj, k, live_context)
        adjusted[k] = stabilize_extreme(float(r.prob_up), quality[k])
        weights[k] *= 0.78 + 0.42 * quality[k]

    total_w = sum(weights.values()) or 1.0
    contributions = {
        k: adjusted[k] * weights[k] / total_w for k in preds
    }
    weighted_base = sum(contributions.values())
    simple_average = sum(float(r.prob_up) for r in preds.values()) / len(preds) if preds else 0.5

    signal_cards = ""
    for k in analyst_order:
        if k not in analyst_rows:
            continue
        r = analyst_rows[k]
        p_up = float(r.prob_up)
        signal_cards += f"""
        <div class="signal-row">
          <div class="signal-name"><span class="signal-dot {tone(p_up)}"></span>{names_cn[k]}</div>
          <div class="signal-track"><span class="{tone(p_up)}" style="width:{bar_width(p_up):.1f}%"></span><i></i></div>
          <div class="signal-value {tone(p_up)}">{pct(p_up)}</div>
        </div>"""

    cards = ""
    for r in analysts:
        p_up = float(r.prob_up)
        conf_a = float(r.confidence)
        t = tone(p_up)
        cards += f"""
        <article class="analyst-card {t}">
          <div class="analyst-head"><span class="agent-dot"></span><span class="aname">{html.escape(str(r.agent)).upper()}</span></div>
          <div class="analyst-prob">{pct(p_up)}</div>
          <div class="mini-track"><span style="width:{bar_width(p_up):.1f}%"></span></div>
          <div class="analyst-meta"><span>{direction_text(p_up)}</span><strong>信心 {pct(conf_a)}</strong></div>
          <p>{html.escape(str(r.reason))}</p>
        </article>"""

    # --- Price chart data ---
    recent60 = d.tail(60)
    price_svg = make_line_svg(recent60.close.tolist() if not recent60.empty else [], pct_axis=False)
    price_dates = recent60.date.tolist() if not recent60.empty else []
    price_values = recent60.close.tolist() if not recent60.empty else []
    first60 = float(price_values[0]) if price_values else price
    last60 = float(price_values[-1]) if price_values else price
    ret60 = (last60 / first60 - 1) if first60 and last60 else 0
    recent20 = d.tail(20)
    first20 = float(recent20.close.iloc[0]) if not recent20.empty else price
    last20 = float(recent20.close.iloc[-1]) if not recent20.empty else price
    ret20 = (last20 / first20 - 1) if first20 and last20 else 0

    # --- Performance trend: rolling 10-prediction accuracy and Brier ---
    perf_dates, perf_acc, perf_brier = [], [], []
    if not s.empty:
        for i in range(len(s)):
            window = s.iloc[max(0, i - 9):i + 1]
            perf_dates.append(str(s.iloc[i].base_date))
            perf_acc.append(float(window.correct.mean()))
            perf_brier.append(float(window.brier.mean()))
    acc_svg = make_line_svg(perf_acc[-60:], pct_axis=True)
    brier_svg = make_line_svg(perf_brier[-60:], pct_axis=False)

    # --- Historical table ---
    history = ""
    if not s.empty:
        for agent, g in s.groupby("agent"):
            history += (
                f"<tr><td><span class='table-agent'>{html.escape(str(agent))}</span></td>"
                f"<td>{len(g)}</td><td>{pct(g.correct.mean())}</td>"
                f"<td>{g.brier.mean():.4f}</td></tr>"
            )

    direction = direction_text(prob)
    chief_tone = tone(prob)
    price_text = f"{price:,.2f}" if price is not None else "-"
    change_text = f"{change:+.2%}" if change is not None else "-"
    prob_text = pct(prob) if prob is not None else "-"
    conf_text = pct(conf) if conf is not None else "-"
    change_cls = "up" if change is not None and change >= 0 else "down"
    conf_width = bar_width(conf)
    gauge_rotation = -90 + (prob or 0.5) * 180

    breakdown_html = "".join(
        f"<div class='break-item'><div class='break-top'><span>{names_cn[k]}</span><strong>权重 {weights[k]:.2f}</strong></div>"
        f"<div class='break-num {tone(preds[k].prob_up)}'>{pct(preds[k].prob_up)}</div>"
        f"<div class='break-bar'><span style='width:{bar_width(contributions[k]):.1f}%'></span></div>"
        f"<div class='break-top' style='margin-top:6px'><span>证据质量 {quality[k]:.0%}</span><span>贡献 {contributions[k]:.1%}</span></div></div>"
        for k in preds
    )

    html_doc = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080b12">
<title>上证预测打擂台</title>
<style>
:root{--bg:#080b12;--panel:#10151f;--panel2:#141b28;--line:#222c3d;--text:#f4f7fb;--muted:#8d98aa;--soft:#c5cedc;--green:#42d392;--red:#ff6576;--blue:#7aa2ff;--gold:#f4c95d}
*{box-sizing:border-box}body{margin:0;color:var(--text);background:radial-gradient(circle at 80% -10%,rgba(91,118,255,.18),transparent 32%),radial-gradient(circle at 10% 15%,rgba(66,211,146,.07),transparent 25%),var(--bg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1240px;margin:auto;padding:30px 20px 64px}.top{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;padding:8px 2px 28px}.brand{display:flex;gap:14px;align-items:center}.logo{width:48px;height:48px;display:grid;place-items:center;border-radius:15px;background:linear-gradient(145deg,#1b2740,#101827);border:1px solid #2c3a55;font-size:24px}h1{margin:0 0 5px;font-size:28px;letter-spacing:-.03em}h2{margin:0;font-size:17px}.muted{color:var(--muted);font-size:13px}.date-pill{border:1px solid var(--line);background:rgba(16,21,31,.75);color:var(--soft);border-radius:999px;padding:9px 13px;font-size:12px;white-space:nowrap}.top-actions{display:flex;align-items:center;gap:9px}.top-login{position:fixed;top:18px;right:18px;z-index:9999;border:1px solid #6d5a25;background:linear-gradient(145deg,#f4c95d,#dcae38);color:#15120a;border-radius:999px;padding:11px 18px;font-size:13px;font-weight:900;cursor:pointer;box-shadow:0 6px 22px rgba(244,201,93,.28);transition:transform .16s,filter .16s;white-space:nowrap}.top-login::before{content:"👤 "}.top-login:hover{transform:translateY(-1px);filter:brightness(1.06)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:linear-gradient(180deg,rgba(20,27,40,.94),rgba(13,18,27,.94));border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 16px 42px rgba(0,0,0,.18)}.metric-label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}.big{font-size:32px;font-weight:800;letter-spacing:-.04em;margin:10px 0 5px}.sub{color:var(--soft);font-size:12px}.up{color:var(--green)}.down{color:var(--red)}.neutral{color:#aab4c4}
.hero-slogan{font-size:clamp(30px,5vw,58px);line-height:1.08;font-weight:800;letter-spacing:-.055em;margin:24px 0 4px}.hero-slogan strong{color:#f4c95d}.chief{margin-top:14px;overflow:hidden;position:relative;background:radial-gradient(circle at 90% 10%,rgba(122,162,255,.16),transparent 30%),linear-gradient(135deg,#141d30,#0e141f);border-color:#2c3d5e}.chief-top{display:flex;justify-content:space-between;align-items:center;gap:16px}.kicker{display:inline-flex;align-items:center;gap:7px;color:#b9c7e4;font-size:12px;border:1px solid #30415f;background:rgba(35,49,78,.45);border-radius:999px;padding:6px 10px}.kicker-dot{width:6px;height:6px;border-radius:50%;background:var(--gold);box-shadow:0 0 12px var(--gold)}.chiefrow{display:grid;grid-template-columns:250px 1fr;gap:28px;align-items:center;margin-top:20px}.prob{font-size:62px;line-height:1;font-weight:850;letter-spacing:-.06em}.chief-direction{margin-top:9px;font-size:15px;font-weight:700}.reason{color:#d8dfeb;font-size:14px;line-height:1.85;max-width:820px}.conf-row{margin-top:14px;display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px}.conf-track,.mini-track{height:6px;background:#202a3a;border-radius:999px;overflow:hidden}.conf-track{width:150px}.conf-track span{display:block;height:100%;width:CONF_WIDTH%;background:linear-gradient(90deg,#5f8cff,#7aa2ff);border-radius:inherit}
.section{margin-top:28px}.section-title{display:flex;justify-content:space-between;align-items:end;margin-bottom:14px}.section-title .hint{color:var(--muted);font-size:12px}
.chart-card{padding:20px}.chart-head{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;margin-bottom:10px}.chart-title{font-size:17px;font-weight:750}.chart-desc{color:var(--muted);font-size:12px;margin-top:5px;line-height:1.5}.chart-stats{display:flex;gap:18px;flex-wrap:wrap}.chart-stat b{font-size:17px}.chart-stat span{display:block;color:var(--muted);font-size:10px;margin-top:3px}.line-svg{width:100%;height:auto;display:block;margin-top:4px}.axis{stroke:#293346;stroke-width:1}.line{fill:none;stroke:#7aa2ff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.area{fill:url(#areaGrad)}.point{fill:#7aa2ff;stroke:#0e141f;stroke-width:3}.value-label{fill:#dce6fa;font-size:12px;font-weight:700;text-anchor:middle}.empty-chart{height:220px;display:grid;place-items:center;color:var(--muted)}
.signal-panel{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}.signal-list{display:flex;flex-direction:column;gap:17px;padding-top:4px}.signal-row{display:grid;grid-template-columns:92px 1fr 55px;gap:12px;align-items:center}.signal-name{font-size:12px;color:#c8d1df}.signal-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;background:#7f8ba0}.signal-dot.bull{background:var(--green)}.signal-dot.bear{background:var(--red)}.signal-track{height:9px;background:#202a3a;border-radius:999px;position:relative;overflow:visible}.signal-track span{position:absolute;left:0;top:0;height:100%;border-radius:999px;background:#69768b}.signal-track span.bull{background:var(--green)}.signal-track span.bear{background:var(--red)}.signal-track i{position:absolute;left:50%;top:-4px;height:17px;width:1px;background:#566175}.signal-value{text-align:right;font-weight:800;font-size:13px}
.gauge{min-height:220px;display:flex;flex-direction:column;align-items:center;justify-content:center}.gauge-ring{width:180px;height:90px;border:15px solid #263144;border-bottom:0;border-radius:180px 180px 0 0;position:relative;overflow:hidden}.gauge-fill{position:absolute;left:-15px;bottom:-15px;width:180px;height:90px;border:15px solid transparent;border-top-color:#7aa2ff;border-radius:180px 180px 0 0;transform-origin:50% 100%;transform:rotate(GAUGE_ROTATIONdeg)}.gauge-center{margin-top:-3px;text-align:center}.gauge-center b{font-size:27px}.gauge-center span{display:block;color:var(--muted);font-size:11px;margin-top:3px}
.breakdown{margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:10px}.break-item{padding:12px;border:1px solid var(--line);border-radius:12px;background:#0d131d}.break-top{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--muted)}.break-top strong{color:#dce4f0}.break-num{font-size:18px;font-weight:800;margin-top:6px}.break-bar{height:5px;background:#202a3a;border-radius:99px;margin-top:7px;overflow:hidden}.break-bar span{display:block;height:100%;background:#657fae;border-radius:inherit}
.analysts{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.analyst-card{min-width:0;background:rgba(16,21,31,.92);border:1px solid var(--line);border-radius:16px;padding:16px}.analyst-head{display:flex;align-items:center;gap:8px}.agent-dot{width:7px;height:7px;border-radius:50%;background:#7f8ba0}.bull .agent-dot{background:var(--green);box-shadow:0 0 10px rgba(66,211,146,.5)}.bear .agent-dot{background:var(--red);box-shadow:0 0 10px rgba(255,101,118,.45)}.aname{color:#aeb9cb;font-size:11px;letter-spacing:.09em;font-weight:800}.analyst-prob{font-size:29px;font-weight:800;margin:14px 0 9px;letter-spacing:-.04em}.mini-track span{display:block;height:100%;border-radius:inherit;background:#65738a}.bull .mini-track span{background:var(--green)}.bear .mini-track span{background:var(--red)}.analyst-meta{display:flex;justify-content:space-between;margin-top:8px;color:var(--muted);font-size:11px}.analyst-meta strong{color:#b8c2d2;font-weight:600}.analyst-card p{color:#aeb8c8;font-size:12px;line-height:1.65;margin:13px 0 0}
.perf-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.perf-label{font-size:12px;color:var(--muted);margin:4px 0 2px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:560px}th,td{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}td{color:#d6deea}.table-agent{font-weight:700;color:#eef2ff}.footer{margin-top:28px;display:flex;justify-content:space-between;gap:12px;color:#68758a;font-size:11px}
@media(max-width:980px){.analysts{grid-template-columns:repeat(2,1fr)}.chiefrow,.signal-panel,.perf-grid{grid-template-columns:1fr}}@media(max-width:700px){.wrap{padding:20px 14px 45px}.top{align-items:flex-start;flex-direction:column;padding-bottom:20px}h1{font-size:24px}.grid{grid-template-columns:1fr}.chiefrow{grid-template-columns:1fr;gap:18px}.prob{font-size:52px}.analysts{grid-template-columns:1fr}.footer{flex-direction:column}.signal-row{grid-template-columns:78px 1fr 48px}}

.human-game{overflow:hidden;position:relative;background:linear-gradient(135deg,rgba(24,35,58,.98),rgba(13,19,29,.98));border-color:#304465}
.human-hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}
.human-kicker{display:inline-flex;padding:6px 10px;border-radius:999px;background:rgba(122,162,255,.12);border:1px solid #304465;color:#b9c7e4;font-size:11px;font-weight:800;letter-spacing:.08em}
.human-hero h2{font-size:25px;margin:12px 0 7px}.human-hero p{color:#aeb9cb;margin:0;font-size:13px;line-height:1.7}
.human-stats{display:flex;gap:10px}.human-stats div{min-width:105px;padding:12px 14px;border:1px solid #293a56;border-radius:14px;background:rgba(7,12,20,.35)}.human-stats span{display:block;color:#8997ab;font-size:10px}.human-stats strong{display:block;margin-top:5px;font-size:18px}
.human-compare{display:grid;grid-template-columns:1fr 70px 1fr;gap:12px;align-items:center;margin-top:20px}.ai-side,.human-side{padding:18px;border-radius:16px;border:1px solid #293a56;background:rgba(7,12,20,.35)}.ai-side span,.human-side>span{display:block;color:#9facbf;font-size:12px}.ai-side b{display:block;font-size:34px;margin:8px 0 2px}.ai-side em{display:block;color:#ff6576;font-style:normal;font-weight:700;font-size:13px}.ai-side small,.human-side small{display:block;color:#77869b;margin-top:10px;font-size:10px}.vs{text-align:center;font-weight:900;color:#f4c95d;font-size:15px}
.vote-buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.vote-buttons button,.leader-head button{border:0;border-radius:15px;padding:15px 16px;font-weight:900;cursor:pointer}.vote-buttons button{position:relative;overflow:hidden;min-height:64px;font-size:16px;color:#fff;background:#182438;border:1px solid #334966;transition:transform .16s,box-shadow .16s,filter .16s}.vote-buttons button:first-child{background:linear-gradient(145deg,#174a3a,#123128);border-color:#318c69}.vote-buttons button:last-child{background:linear-gradient(145deg,#552630,#351a21);border-color:#9a4554}.vote-buttons button:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.12)}.vote-buttons button:active:not(:disabled){transform:scale(.97)}.vote-buttons button.selected{box-shadow:0 0 0 3px #f4c95d inset,0 0 24px rgba(244,201,93,.22);transform:translateY(-2px)}.vote-buttons button.selected::after{content:"✓ 已押";position:absolute;right:8px;top:7px;font-size:10px;color:#f4c95d}.vote-buttons button:disabled{cursor:default;opacity:.55}
.human-result{display:flex;justify-content:space-between;gap:15px;align-items:center;margin-top:14px;padding:14px 16px;border-radius:14px;background:rgba(8,13,21,.7);border:1px solid #31435d;font-size:13px}.human-result b{font-size:14px}.human-result span{color:#9aa8bb}.celebrate{animation:pop .7s ease}.vote-success{animation:successPulse .8s ease}@keyframes pop{50%{transform:scale(1.012)}}@keyframes successPulse{0%{box-shadow:0 0 0 0 rgba(244,201,93,.55)}60%{box-shadow:0 0 0 14px rgba(244,201,93,0)}100%{box-shadow:0 0 0 0 rgba(244,201,93,0)}}
.leaderboard{margin-top:18px;border-top:1px solid #25354d;padding-top:16px}.leader-head{display:flex;justify-content:space-between;align-items:center;gap:10px}.leader-head h3{margin:0;font-size:15px}.leader-head button{background:#f4c95d;color:#15120a;font-size:11px}.leader-row{display:grid;grid-template-columns:30px 1fr 90px 100px;gap:10px;align-items:center;padding:11px 5px;border-bottom:1px solid #1f2a3b}.leader-row span{font-size:16px}.leader-row b{font-size:13px}.leader-row small{color:#8390a2}.leader-row strong{text-align:right;font-size:12px;color:#cbd5e3}.leader-row.top{background:rgba(244,201,93,.04)}.leader-note{color:#6f7d91;font-size:10px;margin-top:10px}
@media(max-width:700px){.human-hero{flex-direction:column}.human-stats{width:100%}.human-stats div{flex:1}.human-compare{grid-template-columns:1fr}.vs{padding:2px}.human-result{flex-direction:column;align-items:flex-start}.leader-row{grid-template-columns:26px 1fr 70px}.leader-row strong{display:none}}
\n
.auth-modal{position:fixed;inset:0;z-index:10000;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(0,0,0,.72);backdrop-filter:blur(5px)}.auth-modal.open{display:flex}.auth-box{width:min(420px,100%);background:#101722;border:1px solid #34445b;border-radius:20px;padding:24px;box-shadow:0 24px 80px rgba(0,0,0,.55)}.auth-head{display:flex;justify-content:space-between;align-items:flex-start}.auth-head h2{margin:0 0 5px}.auth-close{border:0;background:none;color:#9aa8bb;font-size:24px;cursor:pointer}.auth-subtitle{color:#8997aa;font-size:12px;margin-bottom:18px}.auth-tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}.auth-tabs button{border:1px solid #2d3b50;background:#172130;color:#aeb9c9;padding:10px;border-radius:10px;cursor:pointer}.auth-tabs button.active{background:#f4c95d;color:#15120a;font-weight:800}.auth-form{display:grid;gap:11px}.auth-form label,.account-box label{display:grid;gap:6px;color:#9aa8bb;font-size:12px}.auth-form input,.account-box input{width:100%;box-sizing:border-box;border:1px solid #34445b;background:#0b111a;color:#eef3f8;border-radius:10px;padding:11px}.auth-submit{border:0;background:#f4c95d;color:#15120a;border-radius:10px;padding:12px;font-weight:900;cursor:pointer}.auth-link{border:0;background:none;color:#d8b34e;cursor:pointer;font-size:12px}.auth-message{min-height:18px;margin:2px 0;font-size:12px}.auth-message.ok{color:#6ee7a0}.auth-message.err{color:#ff8e8e}.account-view{display:none;gap:12px}.account-box{display:grid;gap:10px}.account-meta{padding:11px;border:1px solid #2b394d;border-radius:10px;background:#0b111a;color:#aeb9c9;font-size:12px}.account-actions{display:grid;gap:8px}.account-actions button{padding:10px;border-radius:10px;border:1px solid #34445b;background:#172130;color:#eef3f8;cursor:pointer}.account-actions button:last-child{color:#ff9b9b}.admin-panel{display:none;gap:9px;margin-top:4px;padding:13px;border:1px solid #6d5a25;border-radius:12px;background:rgba(244,201,93,.06)}.admin-title{font-size:12px;font-weight:900;color:#f4c95d}.admin-panel input{width:100%;box-sizing:border-box;border:1px solid #4b4028;background:#0b111a;color:#eef3f8;border-radius:10px;padding:10px}.admin-credit{border:0!important;background:#f4c95d!important;color:#15120a!important;font-weight:900}.admin-hint{font-size:10px;color:#8997aa;line-height:1.5}@media(max-width:700px){.auth-box{padding:20px}}
</style></head>
<body><main class="wrap">

<header class="top"><div class="brand"><div class="logo">📈</div><div><h1>上证预测打擂台</h1><div class="muted">AI 每日判断 · 你来挑战 · 09:00 前游戏停止预测，游戏使用赠予积分币，不涉及任何实质财富。</div></div></div><div class="top-actions"><div class="date-pill">分析基准日 · __LATEST__</div><button class="top-login" type="button" data-account>登录 / 注册</button></div></header>

<section class="grid">
<div class="card"><div class="metric-label">上证指数 · Latest Close</div><div class="big">__PRICE__</div><div class="sub __CHANGE_CLS__">__CHANGE_TEXT__ <span style="color:var(--muted)">较前一交易日</span></div></div>
<div class="card"><div class="metric-label">AI · Chief Analyst</div><div class="big __CHIEF_TONE__">__PROB__</div><div class="sub">__DIRECTION__ · 下一交易日</div></div>
<div class="card"><div class="metric-label">AI 信心</div><div class="big">__CONF__</div><div class="conf-row"><span>模型综合信心</span><div class="conf-track"><span></span></div></div></div>
</section>

<section class="card chief">
<div class="chief-top"><div class="kicker"><span class="kicker-dot"></span> AI × HUMAN</div><div class="muted">面向下一交易日</div></div>
<div class="hero-slogan">AI 怎么判断？<br><strong>你敢不敢押一边？</strong></div>
<div class="chiefrow"><div><div class="prob __CHIEF_TONE__">__PROB__</div><div class="chief-direction">__DIRECTION__</div></div><div><div class="reason">__REASON__</div><div class="conf-row">模型信心 __CONF__<div class="conf-track"><span></span></div></div></div></div>
</section>



<section class="section human-game" data-human-game>
  <div class="human-hero">
    <div>
      <div class="human-kicker">🎯 YOUR MOVE</div>
      <h2>轮到你了：看多，还是看空？</h2>
      <p>AI 独立判断，你独立下注。每个交易日一次，和 AI 正面对决。</p>
    </div>
    <div class="human-stats">
      <div><span>P币余额</span><strong data-balance>3,000 P</strong></div>
      <div><span>连续参与</span><strong data-streak>0 天</strong></div>
    </div>
  </div>
  <div class="human-compare">
    <div class="ai-side">
      <span>🤖 Chief Analyst</span>
      <b>__PROB__</b>
      <em>__DIRECTION__</em>
      <small>AI 独立预测</small>
    </div>
    <div class="vs">VS</div>
    <div class="human-side">
      <span>👤 你</span>
      <div class="vote-buttons">
        <button type="button" data-vote="bull">🟢 看多</button>
        <button type="button" data-vote="bear">🔴 看空</button>
      </div>
      <small>每次参与消耗 100 P · 09:00 截止</small>
    </div>
  </div>
  <div class="human-result" data-result><b>🎯 选一个方向</b><span>押中赢 P币，押错扣 P币；每天一次。</span></div>
  <div class="leaderboard">
    <div class="leader-head"><h3>🏆 AI × 人类排行榜</h3><button type="button" data-login>保存成绩 / 登录</button></div>
    <div class="leader-row ai-row top" data-ai-row><span>🤖</span><b>Chief Analyst</b><small>AI · 首席</small><strong>__PROB__</strong></div>
    <div class="leader-row ai-row" data-ai-row><span>🤖</span><b>技术面 Analyst</b><small>AI · Technical</small><strong>__TECH_PROB__</strong></div>
    <div class="leader-row ai-row" data-ai-row><span>🤖</span><b>资金面 Analyst</b><small>AI · Flow</small><strong>__FLOW_PROB__</strong></div>
    <div class="leader-row ai-row" data-ai-row><span>🤖</span><b>政策面 Analyst</b><small>AI · Macro</small><strong>__MACRO_PROB__</strong></div>
    <div class="leader-row ai-row" data-ai-row><span>🤖</span><b>市场情绪 Analyst</b><small>AI · Sentiment</small><strong>__SENTIMENT_PROB__</strong></div>
    <div class="leader-row ai-row" data-ai-row><span>🤖</span><b>海外环境 Analyst</b><small>AI · Overseas</small><strong>__OVERSEAS_PROB__</strong></div>
    <div data-human-rows></div>
    <div class="leader-note">AI 六位选手每日独立出战；人类玩家按真实 P币与预测战绩动态排名。AI 与人类积分规则独立。</div>
  </div>
</section>\n
<div class="auth-modal" data-auth-modal aria-hidden="true"><div class="auth-box" role="dialog" aria-modal="true"><div class="auth-head"><div><h2>登录 / 注册</h2><div class="auth-subtitle" data-auth-subtitle>登录后保存你的 P币、预测和排行榜成绩。</div></div><button class="auth-close" type="button" data-auth-close>×</button></div><div class="auth-tabs" data-auth-tabs><button type="button" data-auth-mode="login" class="active">登录</button><button type="button" data-auth-mode="register">注册</button></div><form class="auth-form" data-auth-form><label data-nickname-field style="display:none">昵称<input name="nickname" maxlength="20" autocomplete="nickname"></label><label>邮箱<input name="email" type="email" required autocomplete="email"></label><label>密码<input name="password" type="password" required minlength="8"></label><label data-password2-field style="display:none">确认密码<input name="password2" type="password" minlength="8"></label><button class="auth-submit" type="submit" data-auth-submit>登录</button><button class="auth-link" type="button" data-forgot-password>忘记密码？</button><div class="auth-message" data-auth-message></div></form><div class="account-view" data-account-view><div class="account-box"><div class="account-meta">邮箱：<b data-account-email>—</b><br>余额：<b data-account-balance>0 P</b></div><label>昵称<input data-account-nickname maxlength="20"></label><div class="account-actions"><button type="button" data-save-profile>保存昵称</button><button type="button" data-change-password>修改密码</button><div class="admin-panel" data-admin-panel><div class="admin-title">🛡️ 管理员 P 币充值</div><input data-admin-amount type="number" min="1" step="1" placeholder="充值数量，例如 100000000000"><input data-admin-reason maxlength="80" placeholder="充值备注（可选）" value="管理员充值"><button class="admin-credit" type="button" data-admin-credit>确认充值</button><div class="admin-hint">仅管理员账号显示。充值与 P 币流水在同一事务中完成。</div><div class="auth-message" data-admin-message></div></div><button type="button" data-logout>退出登录</button></div><div class="auth-message" data-account-message></div></div></div></div></div>
\n<section class="section card chart-card">
<div class="chart-head"><div><div class="chart-title">上证指数走势</div><div class="chart-desc">最近 60 个交易日 · 最近 20 日区间表现同步显示</div></div><div class="chart-stats"><div class="chart-stat"><b>__RET20__</b><span>20 日</span></div><div class="chart-stat"><b>__RET60__</b><span>60 日</span></div></div></div>
__PRICE_SVG__
</section>
<footer class="footer"><span>上证预测打擂台</span><span>GitHub Actions 自动生成 · 仅供研究参考，不构成投资建议</span></footer>
</main><script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script><script src="community.js"></script>\n</body></html>"""

    def ai_prob(k):
        return f"{float(analyst_rows[k].prob_up)*100:.1f}%" if k in analyst_rows else "—"
    replacements = {
        "__LATEST__": html.escape(str(latest)),
        "__TECH_PROB__": ai_prob("technical"),
        "__FLOW_PROB__": ai_prob("flow"),
        "__MACRO_PROB__": ai_prob("macro"),
        "__SENTIMENT_PROB__": ai_prob("sentiment"),
        "__OVERSEAS_PROB__": ai_prob("overseas"),
        "__PRICE__": price_text,
        "__CHANGE_CLS__": change_cls,
        "__CHANGE_TEXT__": change_text,
        "__CHIEF_TONE__": chief_tone,
        "__PROB__": prob_text,
        "__DIRECTION__": direction,
        "__CONF__": conf_text,
        "__REASON__": html.escape(reason),
        "__RET20__": f"{ret20:+.2f}%",
        "__RET60__": f"{ret60:+.2f}%",
        "__PRICE_SVG__": price_svg,
    }
    for key, value in replacements.items():
        html_doc = html_doc.replace(key, value)
    html_doc = html_doc.replace("CONF_WIDTH", f"{conf_width:.1f}")
    html_doc = html_doc.replace("GAUGE_ROTATION", f"{gauge_rotation:.1f}")
    html_doc = html_doc.replace("GAUGE_ROTATION", f"{gauge_rotation:.1f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_doc, encoding="utf-8")


if __name__ == "__main__":
    main()
