// Community + account system for SSE dashboard, backed by Google Apps Script.
(() => {
  const GAS_API_URL = "https://script.google.com/macros/s/AKfycby_6rP60PYTK0zXqVsRwvFap8dYoS2ElJpK1pxnx28c0v4c_jInjGr926Zqm8q7xCzwzA/exec";
  const TOKEN_KEY = "sse_community_session";
  const root = document.querySelector("[data-human-game]");
  if (!root) return;

  let initialized = true, voteInFlight = false, cachedUser = null;
  const balance = root.querySelector("[data-balance]");
  const streak = root.querySelector("[data-streak]");
  const result = root.querySelector("[data-result]");
  const buttons = [...root.querySelectorAll("[data-vote]")];
  const login = root.querySelector("[data-login]");
  const humanRows = root.querySelector("[data-human-rows]");
  const modal = document.querySelector("[data-auth-modal]");
  const accountButtons = [...document.querySelectorAll("[data-account],[data-login]")];
  const closeBtn = modal?.querySelector("[data-auth-close]");
  const tabs = [...(modal?.querySelectorAll("[data-auth-mode]") || [])];
  const form = modal?.querySelector("[data-auth-form]");
  const tabsWrap = modal?.querySelector("[data-auth-tabs]");
  const accountView = modal?.querySelector("[data-account-view]");
  const nicknameField = modal?.querySelector("[data-nickname-field]");
  const password2Field = modal?.querySelector("[data-password2-field]");
  const submit = modal?.querySelector("[data-auth-submit]");
  const message = modal?.querySelector("[data-auth-message]");
  const accountMessage = modal?.querySelector("[data-account-message]");
  const accountEmail = modal?.querySelector("[data-account-email]");
  const accountBalance = modal?.querySelector("[data-account-balance]");
  const accountNickname = modal?.querySelector("[data-account-nickname]");
  const subtitle = modal?.querySelector("[data-auth-subtitle]");
  const adminPanel = modal?.querySelector("[data-admin-panel]");
  let authMode = "login";

  async function api(action, values = {}) {
    const payload = new URLSearchParams();
    payload.set("action", action);
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== null) payload.set(key, String(value));
    });
    const response = await fetch(GAS_API_URL, { method: "POST", body: payload, redirect: "follow" });
    if (!response.ok) throw new Error("服务器返回 HTTP " + response.status);
    const json = await response.json();
    if (!json.ok) throw new Error(json.error || "请求失败");
    return json.data;
  }
  function getToken() { try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (_) { return ""; } }
  function saveToken(token) { try { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY); } catch (_) {} }
  function sgNow() { return new Date(Date.now() + 8 * 60 * 60 * 1000); }
  function dateKey(d) { return d.toISOString().slice(0, 10); }
  function nextWeekday() {
    const d = sgNow();
    // Before 09:00 on a weekday, the target is today's session; otherwise use the next weekday.
    if (!(d.getUTCDay() >= 1 && d.getUTCDay() <= 5 && d.getUTCHours() < 9)) {
      d.setUTCDate(d.getUTCDate() + 1);
      while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
    }
    return dateKey(d);
  }
  function beforeCutoff(tradingDate) {
    const now = sgNow(), today = dateKey(now);
    if (today < tradingDate) return true;
    if (today > tradingDate) return false;
    return now.getUTCHours() < 9;
  }
  function escapeHtml(v) {
    return String(v ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
  }
  async function currentUser() {
    const token = getToken();
    if (!token) { cachedUser = null; return null; }
    try { cachedUser = await api("me", { token }); return cachedUser; }
    catch (_) { saveToken(""); cachedUser = null; return null; }
  }
  function showModal(mode = "login") {
    if (!modal) return;
    modal.classList.add("open"); modal.setAttribute("aria-hidden", "false"); setMode(mode);
  }
  function hideModal() { modal?.classList.remove("open"); modal?.setAttribute("aria-hidden", "true"); }
  function setMode(mode) {
    authMode = mode;
    const account = mode === "account";
    if (tabsWrap) tabsWrap.style.display = account ? "none" : "grid";
    if (form) form.style.display = account ? "none" : "grid";
    if (accountView) accountView.style.display = account ? "grid" : "none";
    tabs.forEach(t => t.classList.toggle("active", t.dataset.authMode === mode));
    if (account) {
      if (subtitle) subtitle.textContent = "管理你的登录资料、P币和排行榜身份。";
      return;
    }
    if (subtitle) subtitle.textContent = mode === "login" ? "登录后保存你的 P币、预测和排行榜成绩。" : "创建正式账户，注册即得 3000 P 币。";
    if (nicknameField) nicknameField.style.display = mode === "register" ? "block" : "none";
    if (password2Field) password2Field.style.display = mode === "register" ? "block" : "none";
    if (submit) submit.textContent = mode === "login" ? "登录" : "注册";
    if (form?.elements?.password) form.elements.password.autocomplete = mode === "login" ? "current-password" : "new-password";
    if (message) { message.textContent = ""; message.className = "auth-message"; }
  }
  function authMsg(text, ok = false) {
    if (!message) return;
    message.textContent = text; message.className = "auth-message " + (ok ? "ok" : "err");
  }
  async function refreshAccountButton() {
    const user = await currentUser();
    accountButtons.forEach(b => { b.textContent = user ? "👤 我的账户" : "登录 / 注册"; });
    return user;
  }
  async function openAccount() {
    const user = await refreshAccountButton();
    if (!user) showModal("login");
    else { showModal("account"); await loadAccount(user); }
  }
  async function loadAccount(user) {
    if (!user) return;
    if (accountEmail) accountEmail.textContent = user.email || "—";
    if (accountBalance) accountBalance.textContent = Number(user.balance || 0).toLocaleString() + " P";
    if (accountNickname) accountNickname.value = user.nickname || "新玩家";
    if (accountMessage) { accountMessage.textContent = ""; accountMessage.className = "auth-message"; }
    if (adminPanel) adminPanel.style.display = "none";
  }
  async function loadLeaderboard() {
    if (!humanRows) return;
    const token = getToken();
    if (!token) { humanRows.innerHTML = '<div class="leader-note">登录后查看玩家排行榜</div>'; return; }
    try {
      const rows = await api("leaderboard", { token });
      humanRows.innerHTML = (rows || []).slice(0, 10).map((x, i) => {
        const medal = ["🥇", "🥈", "🥉"][i] || (i + 1);
        return '<div class="leader-row ' + (cachedUser && x.user_id === cachedUser.id ? "top" : "") + '"><span>' + medal + '</span><b>' +
          escapeHtml(cachedUser && x.user_id === cachedUser.id ? "你" : (x.nickname || "玩家")) + '</b><small>👤 玩家 · ' +
          Number(x.accuracy || 0).toFixed(1) + '%</small><strong>' + Number(x.p_balance || 0).toLocaleString() + ' P</strong></div>';
      }).join("") || '<div class="leader-note">暂无玩家成绩</div>';
    } catch (e) {
      humanRows.innerHTML = '<div class="leader-note">排行榜暂时无法加载，请稍后重试。</div>';
    }
  }
  async function render() {
    const user = await currentUser();
    await refreshAccountButton();
    if (!user) {
      if (balance) balance.textContent = "登录后";
      if (streak) streak.textContent = "—";
      buttons.forEach(b => { b.disabled = false; b.classList.remove("selected"); });
      if (result) result.innerHTML = "<b>🎯 登录后参与</b><span>注册或登录后，P币和每日预测会保存到你的账户。</span>";
      await loadLeaderboard();
      return;
    }
    const tradingDate = nextWeekday();
    let prediction = null;
    let predictionCheckFailed = false;
    try {
      prediction = await api("myVote", { token: getToken(), tradingDate });
    } catch (_) {
      // Fail closed: if the server cannot confirm whether a vote exists, do not allow another attempt.
      predictionCheckFailed = true;
    }
    if (balance) balance.textContent = Number(user.balance || 0).toLocaleString() + " P";
    buttons.forEach(b => {
      b.disabled = predictionCheckFailed || !!prediction || !beforeCutoff(tradingDate);
      b.classList.toggle("selected", b.dataset.vote === prediction?.direction);
    });
    if (result) {
      if (predictionCheckFailed) result.innerHTML = "<b>⚠️ 暂时无法确认投票状态</b><span>为避免重复扣除 P 币，投票按钮已暂时锁定。请刷新网页后重试。</span>";
      else if (!beforeCutoff(tradingDate) && !prediction) result.innerHTML = "<b>⏰ 投票已截止</b><span>每天 09:00（UTC+8）锁定。</span>";
      else if (prediction) result.innerHTML = "<b>今天已提交：" + (prediction.direction === "bull" ? "🟢 看多" : "🔴 看空") + "</b><span>等待目标交易日收盘结算。</span>";
      else result.innerHTML = "<b>🎯 今天还没有押</b><span>选一个方向，100 P 入场，结果将在结算后公布。</span>";
    }
    await loadLeaderboard();
  }

  buttons.forEach(btn => btn.addEventListener("click", async () => {
    if (voteInFlight) return;
    const token = getToken();
    if (!token) { showModal("login"); authMsg("请先登录或注册，登录后才能投票。"); return; }
    const tradingDate = nextWeekday();
    if (!beforeCutoff(tradingDate)) return;
    voteInFlight = true;
    if (result) result.innerHTML = "<b>⏳ 云端处理中…</b><span>正在提交 100 P 投票，请勿重复点击。</span>";
    buttons.forEach(b => b.disabled = true);
    try {
      await api("vote", { token, tradingDate, direction: btn.dataset.vote });
      root.classList.add("celebrate", "vote-success");
      if (result) result.innerHTML = "<b>🔥 投票成功！</b><span>" + (btn.dataset.vote === "bull" ? "你投了看多" : "你投了看空") + " · 100 P 已扣除，等待结算！</span>";
      setTimeout(() => root.classList.remove("celebrate", "vote-success"), 900);
    } catch (e) {
      const m = e.message || "未知错误";
      if (result) result.innerHTML = "<b>提交失败</b><span>" +
        (m.includes("ALREADY_VOTED") ? "你已经投过票了。" : m.includes("VOTING_CLOSED") ? "投票已截止。" :
        m.includes("INSUFFICIENT_BALANCE") ? "P币余额不足。" : escapeHtml(m)) + "</span>";
    } finally { voteInFlight = false; await render(); }
  }));

  accountButtons.forEach(b => b.addEventListener("click", openAccount));
  closeBtn?.addEventListener("click", hideModal);
  modal?.addEventListener("click", e => { if (e.target === modal) hideModal(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideModal(); });
  tabs.forEach(t => t.addEventListener("click", () => setMode(t.dataset.authMode)));

  form?.addEventListener("submit", async e => {
    e.preventDefault();
    const email = form.elements.email.value.trim();
    const password = form.elements.password.value;
    const nickname = form.elements.nickname?.value.trim() || "新玩家";
    if (password.length < 8) { authMsg("密码至少 8 位。"); return; }
    if (authMode === "register" && password !== form.elements.password2.value) { authMsg("两次密码不一致。"); return; }
    if (submit) { submit.disabled = true; submit.textContent = authMode === "login" ? "登录中…" : "注册中…"; }
    try {
      if (authMode === "login") {
        const data = await api("login", { email, password });
        saveToken(data.token);
        authMsg("登录成功。", true);
        await render();
        setTimeout(hideModal, 500);
      } else {
        const data = await api("register", { email, password, nickname });
        saveToken(data.token);
        cachedUser = data.user;
        authMsg("注册成功！已赠送 3000 P 币。", true);
        await render();
        setTimeout(async () => { setMode("account"); await loadAccount(await currentUser()); }, 500);
      }
    } catch (e) {
      const m = e.message || "操作失败，请稍后再试。";
      authMsg(m.includes("EMAIL_EXISTS") ? "这个邮箱已经注册，请直接登录。" :
        m.includes("INVALID_CREDENTIALS") ? "邮箱或密码不正确。" :
        m.includes("INVALID_EMAIL") ? "请输入有效的邮箱地址。" : escapeHtml(m));
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = authMode === "login" ? "登录" : "注册"; }
    }
  });

  modal?.querySelector("[data-save-profile]")?.addEventListener("click", async () => {
    const token = getToken(); if (!token) return;
    const nickname = (accountNickname?.value || "").trim().slice(0, 20) || "新玩家";
    try {
      const user = await api("profile", { token, nickname });
      cachedUser = user;
      if (accountMessage) { accountMessage.textContent = "账户资料已保存。"; accountMessage.className = "auth-message ok"; }
      await render(); await loadAccount(user);
    } catch (e) {
      if (accountMessage) { accountMessage.textContent = "保存失败：" + (e.message || "未知错误"); accountMessage.className = "auth-message err"; }
    }
  });
  modal?.querySelector("[data-change-password]")?.addEventListener("click", () => {
    if (accountMessage) {
      accountMessage.textContent = "修改密码功能尚未接入，请暂时妥善保管注册密码。";
      accountMessage.className = "auth-message";
    }
  });
  modal?.querySelector("[data-forgot-password]")?.addEventListener("click", () => {
    authMsg("忘记密码功能尚未接入；请先确保记住注册密码。");
  });
  adminPanel?.setAttribute("hidden", "hidden");
  modal?.querySelector("[data-logout]")?.addEventListener("click", async () => {
    const token = getToken();
    try { if (token) await api("logout", { token }); } catch (_) {}
    saveToken(""); cachedUser = null; hideModal(); await render();
  });
  if (login) login.addEventListener("click", openAccount);
  buttons.forEach(b => { b.disabled = false; });
  render().catch(() => {
    if (result) result.innerHTML = "<b>账户系统暂时无法连接</b><span>请刷新页面后重试；如果持续出现，请检查后端跨域连接。</span>";
  });
})();