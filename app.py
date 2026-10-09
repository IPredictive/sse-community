import os
import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from functools import wraps

from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

from db import connection, init_db, load_daily, load_predictions

application = Flask(__name__)
application.secret_key = os.getenv("SECRET_KEY", "please-set-a-long-random-secret-in-cpanel")

PAGE = r"""
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>狮城胖叔·上证预测打擂台</title>
<style>
:root{color-scheme:dark;--bg:#0a0f18;--panel:#141c2a;--line:#2a3548;--text:#f4f7fb;--muted:#9aa8bc;--gold:#f4c95d;--green:#47d7a0;--red:#ff7182}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#1a2c49 0,transparent 34%),var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1050px;margin:auto;padding:28px 18px 60px}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.brand{font-weight:850;font-size:clamp(22px,4vw,32px)}.muted{color:var(--muted);font-size:13px}.pill{border:1px solid var(--line);border-radius:999px;padding:8px 12px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin-top:18px}.card{background:linear-gradient(160deg,#172235,#101722);border:1px solid var(--line);border-radius:18px;padding:20px}.hero{margin-top:22px;border-color:#4a452e;background:linear-gradient(135deg,#262719,#141c2a)}h2{margin:0 0 12px;font-size:18px}.big{font-size:42px;font-weight:850;letter-spacing:-1.5px}.gold{color:var(--gold)}.mutedline{color:#c0cad9;line-height:1.7;font-size:14px}.btn{display:inline-block;background:var(--gold);color:#17140b;border:0;border-radius:10px;padding:11px 15px;font-weight:800;text-decoration:none;cursor:pointer}.btn.secondary{background:#27344a;color:var(--text);border:1px solid var(--line)}input{width:100%;margin:6px 0 13px;padding:12px;border-radius:10px;border:1px solid var(--line);background:#0b111b;color:var(--text)}label{font-size:13px;color:var(--muted)}form{margin:0}.signal{padding:13px 0;border-bottom:1px solid var(--line)}.signal:last-child{border:0}.bar{height:7px;background:#263146;border-radius:8px;overflow:hidden;margin-top:9px}.bar span{display:block;height:100%;background:var(--gold)}.notice{margin-top:14px;padding:12px 14px;background:#1b2a3e;border-radius:12px;color:#cbd8ec;font-size:14px}.error{color:#ff9ba6}.good{color:#70e5b5}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line);font-size:13px}th{color:var(--muted)}.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin-top:14px}
</style></head><body><main>
<div class="top"><div><div class="brand">📈 狮城胖叔·上证预测打擂台</div><div class="muted">独立社区 · 量化分析 · 人工投票 · 积分榜</div></div>
<div>{% if user %}<span class="pill">{{ user.username }} · {{ user.points }} P币</span> <a class="btn secondary" href="{{ url_for('logout') }}">退出</a>{% else %}<a class="btn secondary" href="#account">登录 / 注册</a>{% endif %}</div></div>
<div class="card hero"><div class="muted">首席分析师 · 规则量化模型</div>
{% if chief %}<div class="big gold">{{ "%.1f"|format(chief.prob_up*100) }}%</div><div><b>{{ direction(chief.prob_up) }}</b> · 信心 {{ "%.1f"|format(chief.confidence*100) }}%</div><p class="mutedline">{{ chief.reason }}</p><div class="muted">分析基准日：{{ chief.base_date }}</div>
{% else %}<div class="big gold">等待首次分析</div><p class="mutedline">网站已经准备好，首次运行分析程序并写入数据库后，这里会显示首席分析师的预测。</p>{% endif %}</div>
<div class="grid"><section class="card"><h2>上证指数</h2>{% if latest %}<div class="big">{{ "%.2f"|format(latest.close) }}</div><div class="muted">最近数据日期：{{ latest.date }}</div>{% else %}<div class="mutedline">尚未导入行情数据</div>{% endif %}</section>
<section class="card"><h2>人工投票</h2><div class="mutedline">预测下一交易日涨跌。每位用户每个目标日期可投票一次，投票截止时间为目标日北京时间 09:00。</div>
{% if user %}<form method="post" action="{{ url_for('vote') }}"><button class="btn" name="direction" value="bull">看多 ↑</button> <button class="btn secondary" name="direction" value="bear">看空 ↓</button></form>{% else %}<a class="btn" href="#account">登录后参与</a>{% endif %}
<div class="muted" style="margin-top:10px">目标日期：{{ target_date }} · 看多 {{ bull_count }} / 看空 {{ bear_count }}</div></section>
<section class="card"><h2>社区排行榜</h2>{% if leaders %}<table><tr><th>排名</th><th>用户</th><th>P币</th></tr>{% for x in leaders %}<tr><td>{{ loop.index }}</td><td>{{ x.username }}</td><td>{{ x.points }}</td></tr>{% endfor %}</table>{% else %}<div class="mutedline">注册后即可进入排行榜。新用户初始拥有 3000 P币。</div>{% endif %}</section></div>
<div class="two"><section class="card"><h2>五位分析师</h2>{% if analysts %}{% for a in analysts %}<div class="signal"><div style="display:flex;justify-content:space-between;gap:10px"><b>{{ agent_names.get(a.agent,a.agent) }}</b><b>{{ "%.1f"|format(a.prob_up*100) }}%</b></div><div class="bar"><span style="width:{{ a.prob_up*100 }}%"></span></div><div class="mutedline">{{ a.reason }}</div></div>{% endfor %}{% else %}<div class="mutedline">首次运行每日量化任务后显示。</div>{% endif %}</section>
<section class="card" id="account"><h2>账户</h2>{% if user %}<div class="mutedline">欢迎回来，{{ user.username }}。你的初始积分为 3000 P币。</div>{% else %}<form method="post" action="{{ url_for('register') }}"><label>注册用户名（3–20位字母、数字或下划线）</label><input name="username" required minlength="3" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" autocomplete="username"><label>密码（至少8位）</label><input type="password" name="password" required minlength="8" autocomplete="new-password"><button class="btn" type="submit">注册并领取 3000 P币</button></form><hr style="border-color:var(--line);margin:20px 0"><form method="post" action="{{ url_for('login') }}"><label>已有账号：用户名</label><input name="username" required autocomplete="username"><label>密码</label><input type="password" name="password" required autocomplete="current-password"><button class="btn secondary" type="submit">登录</button></form>{% endif %}</section></div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="notice {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<p class="muted" style="margin-top:22px">预测仅供研究与交流，不构成投资建议。社区投票和 AI 量化预测分别展示，互不替代。</p>
</main></body></html>
"""

AGENT_NAMES = {"technical":"技术面","flow":"资金面","macro":"政策面","sentiment":"市场情绪","overseas":"海外环境"}

def direction(p):
    p = float(p)
    if p >= .70: return "强烈偏多"
    if p >= .60: return "偏多"
    if p >= .53: return "中性偏多"
    if p > .47: return "中性"
    if p > .40: return "中性偏空"
    if p > .30: return "偏空"
    return "强烈偏空"

def get_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,username,points FROM users WHERE id=%s", (uid,))
            return cur.fetchone()

def next_weekday():
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    d = today + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d

def page():
    init_db()
    user = get_user()
    preds = load_predictions()
    chief = None
    analysts = []
    if not preds.empty:
        latest_date = preds["base_date"].max()
        rows = preds[preds["base_date"] == latest_date].copy()
        rows["base_date"] = rows["base_date"].astype(str)
        cs = rows[rows["agent"].isin(["CHIEF_ANALYST", "ENSEMBLE"])]
        if not cs.empty:
            chief = cs.iloc[0].to_dict()
        analysts = [r.to_dict() for _, r in rows[rows["agent"].isin(["technical","flow","macro","sentiment","overseas"])].iterrows()]
    daily = load_daily()
    latest = daily.iloc[-1].to_dict() if not daily.empty else None
    if latest:
        latest["date"] = str(latest["date"])
    target = next_weekday()
    bull_count = bear_count = 0
    leaders = []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT direction,COUNT(*) AS n FROM votes WHERE target_date=%s GROUP BY direction", (target.isoformat(),))
            for row in cur.fetchall():
                if row["direction"] == "bull": bull_count = row["n"]
                else: bear_count = row["n"]
            cur.execute("SELECT username,points FROM users ORDER BY points DESC, created_at ASC LIMIT 10")
            leaders = cur.fetchall()
    return render_template_string(PAGE, user=user, chief=chief, analysts=analysts,
        agent_names=AGENT_NAMES, direction=direction, latest=latest,
        target_date=target.isoformat(), bull_count=bull_count, bear_count=bear_count, leaders=leaders)

@application.route("/")
def home():
    try:
        return page()
    except Exception:
        application.logger.exception("Website request failed")
        return ("网站正在初始化。请检查 cPanel Python App 的环境变量：DB_HOST、DB_NAME、DB_USER、DB_PASSWORD、SECRET_KEY。不要把数据库密码发到聊天中。", 500)

@application.route("/health")
def health():
    try:
        init_db()
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        return {"status":"ok","database":"connected"}
    except Exception:
        application.logger.exception("Health check failed")
        return {"status":"error","database":"not connected"}, 500

@application.post("/register")
def register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username) or len(password) < 8:
        flash("用户名须为3–20位字母、数字或下划线，密码至少8位。", "error")
        return redirect(url_for("home") + "#account")
    try:
        init_db()
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users(username,password_hash,points) VALUES(%s,%s,3000)",
                            (username, generate_password_hash(password)))
                user_id = cur.lastrowid
                cur.execute("INSERT INTO point_ledger(user_id,change_amount,reason) VALUES(%s,3000,'注册初始积分')", (user_id,))
        session["user_id"] = user_id
        flash("注册成功！已发放 3000 P币。", "good")
    except Exception as e:
        if "Duplicate" in str(e) or "1062" in str(e):
            flash("这个用户名已被使用，请换一个。", "error")
        else:
            application.logger.exception("Registration failed")
            flash("注册暂时失败，请稍后重试。", "error")
    return redirect(url_for("home"))

@application.post("/login")
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    try:
        init_db()
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id,password_hash FROM users WHERE username=%s", (username,))
                row = cur.fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["id"]
            flash("登录成功。", "good")
        else:
            flash("用户名或密码不正确。", "error")
    except Exception:
        application.logger.exception("Login failed")
        flash("登录暂时失败，请稍后重试。", "error")
    return redirect(url_for("home"))

@application.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@application.post("/vote")
def vote():
    user = get_user()
    if not user:
        flash("请先登录再投票。", "error")
        return redirect(url_for("home") + "#account")
    direction_value = request.form.get("direction")
    if direction_value not in ("bull", "bear"):
        flash("投票选项无效。", "error")
        return redirect(url_for("home"))
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    target = next_weekday()
    deadline = datetime.combine(target, time(9, 0), tzinfo=ZoneInfo("Asia/Shanghai"))
    if now >= deadline:
        flash("当前投票窗口已关闭，请等待下一个交易日投票。", "error")
        return redirect(url_for("home"))
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO votes(user_id,target_date,direction) VALUES(%s,%s,%s)",
                            (user["id"], target.isoformat(), direction_value))
        flash("投票成功！每个目标日期只能投票一次。", "good")
    except Exception as e:
        if "Duplicate" in str(e) or "1062" in str(e):
            flash("你已经为这个目标日期投过票了。", "error")
        else:
            application.logger.exception("Vote failed")
            flash("投票暂时失败，请稍后重试。", "error")
    return redirect(url_for("home"))

if __name__ == "__main__":
    application.run()
