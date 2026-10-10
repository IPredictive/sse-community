/**
 * SSE Community backend — Google Apps Script.
 * Setup:
 * 1) Create a Google Spreadsheet and copy its ID into Script Properties as SPREADSHEET_ID.
 * 2) Set ADMIN_KEY in Script Properties to a long random secret.
 * 3) Deploy as Web app, Execute as: Me; access: Anyone.
 * 4) Set the deployed /exec URL in site/community.js (GAS_API_URL).
 *
 * This backend uses POST JSON. Test browser cross-origin access before production rollout.
 */
const TABLES = {
  Users: ['id','email','nickname','salt','password_hash','balance','created_at'],
  Sessions: ['token_hash','user_id','expires_at'],
  Votes: ['id','user_id','trading_date','direction','stake','status','created_at','settled_at','won'],
  Transactions: ['id','user_id','amount','reason','created_at'],
  AiPredictions: ['trading_date','agent','prob_up','confidence','reason','synced_at']
};

function doGet() {
  return json_({ok:true,service:'SSE Community API',version:1,actions:['register','login','me','profile','vote','leaderboard','syncAi','settle']});
}
function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const action = String(body.action || '');
    let result;
    switch (action) {
      case 'register': result = register_(body); break;
      case 'login': result = login_(body); break;
      case 'me': result = me_(body.token); break;
      case 'profile': result = profile_(body.token, body.nickname); break;
      case 'vote': result = vote_(body.token, body.tradingDate, body.direction); break;
      case 'leaderboard': result = leaderboard_(body.token); break;
      case 'syncAi': result = syncAi_(body); break;
      case 'settle': result = settle_(body); break;
      case 'logout': result = logout_(body.token); break;
      default: throw new Error('UNKNOWN_ACTION');
    }
    return json_({ok:true,data:result});
  } catch (err) {
    return json_({ok:false,error:String(err && err.message || err)});
  }
}
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
function ss_() {
  const id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!id) throw new Error('SETUP_REQUIRED: Set SPREADSHEET_ID in Apps Script Project Settings.');
  const ss = SpreadsheetApp.openById(id);
  Object.keys(TABLES).forEach(name => {
    let sh = ss.getSheetByName(name);
    if (!sh) { sh = ss.insertSheet(name); sh.appendRow(TABLES[name]); }
    else if (sh.getLastRow() === 0) sh.appendRow(TABLES[name]);
  });
  return ss;
}
function rows_(name) {
  const sh = ss_().getSheetByName(name);
  if (sh.getLastRow() < 2) return [];
  const vals = sh.getDataRange().getValues();
  const headers = vals.shift().map(String);
  return vals.map((r,i) => {
    const o = { _row:i+2 };
    headers.forEach((h,j) => o[h] = r[j]);
    return o;
  });
}
function append_(name, obj) {
  const sh = ss_().getSheetByName(name);
  const headers = TABLES[name];
  sh.appendRow(headers.map(h => obj[h] === undefined ? '' : obj[h]));
}
function updateRow_(name, rowNum, obj) {
  const sh = ss_().getSheetByName(name);
  const headers = TABLES[name];
  sh.getRange(rowNum,1,1,headers.length).setValues([headers.map(h => obj[h] === undefined ? '' : obj[h])]);
}
function id_() { return Utilities.getUuid(); }
function now_() { return new Date(); }
function normalizeEmail_(s) {
  const email = String(s || '').trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('INVALID_EMAIL');
  return email;
}
function passwordHash_(password, salt) {
  const p = String(password || '');
  if (p.length < 8 || p.length > 128) throw new Error('PASSWORD_LENGTH_8_TO_128');
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, salt + ':' + p, Utilities.Charset.UTF_8);
  return Utilities.base64EncodeWebSafe(bytes);
}
function randomToken_() {
  return Utilities.getUuid().replace(/-/g,'') + Utilities.getUuid().replace(/-/g,'');
}
function tokenHash_(token) {
  return Utilities.base64EncodeWebSafe(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(token || ''), Utilities.Charset.UTF_8));
}
function issueSession_(userId) {
  const token = randomToken_();
  append_('Sessions',{token_hash:tokenHash_(token),user_id:userId,expires_at:new Date(Date.now()+30*24*60*60*1000)});
  return token;
}
function userByToken_(token) {
  if (!token) throw new Error('LOGIN_REQUIRED');
  const h = tokenHash_(token);
  const s = rows_('Sessions').find(x => x.token_hash === h && new Date(x.expires_at).getTime() > Date.now());
  if (!s) throw new Error('SESSION_EXPIRED');
  const u = rows_('Users').find(x => x.id === s.user_id);
  if (!u) throw new Error('USER_NOT_FOUND');
  return u;
}
function publicUser_(u) {
  return {id:u.id,email:u.email,nickname:u.nickname,balance:Number(u.balance || 0),createdAt:u.created_at};
}
function register_(b) {
  const email = normalizeEmail_(b.email);
  const nickname = String(b.nickname || '新玩家').trim().slice(0,20) || '新玩家';
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (rows_('Users').some(u => u.email === email)) throw new Error('EMAIL_EXISTS');
    const salt = randomToken_();
    const u = {id:id_(),email,nickname,salt,password_hash:passwordHash_(b.password,salt),balance:3000,created_at:now_()};
    append_('Users',u);
    append_('Transactions',{id:id_(),user_id:u.id,amount:3000,reason:'新用户注册奖励',created_at:now_()});
    return {user:publicUser_(u),token:issueSession_(u.id)};
  } finally { lock.releaseLock(); }
}
function login_(b) {
  const email = normalizeEmail_(b.email);
  const u = rows_('Users').find(x => x.email === email);
  if (!u || u.password_hash !== passwordHash_(b.password,u.salt)) throw new Error('INVALID_CREDENTIALS');
  return {user:publicUser_(u),token:issueSession_(u.id)};
}
function me_(token) { return publicUser_(userByToken_(token)); }
function profile_(token,nickname) {
  const u = userByToken_(token);
  u.nickname = String(nickname || '').trim().slice(0,20) || '新玩家';
  updateRow_('Users',u._row,u);
  return publicUser_(u);
}
function vote_(token,tradingDate,direction) {
  const u = userByToken_(token);
  const date = String(tradingDate || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('INVALID_TRADING_DATE');
  if (!['bull','bear'].includes(direction)) throw new Error('INVALID_DIRECTION');
  const now = new Date();
  const todaySg = Utilities.formatDate(now,'Asia/Singapore','yyyy-MM-dd');
  const hourSg = Number(Utilities.formatDate(now,'Asia/Singapore','H'));
  if (date < todaySg || (date === todaySg && hourSg >= 9)) throw new Error('VOTING_CLOSED');
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (rows_('Votes').some(v => v.user_id === u.id && v.trading_date === date)) throw new Error('ALREADY_VOTED');
    if (Number(u.balance) < 100) throw new Error('INSUFFICIENT_BALANCE');
    u.balance = Number(u.balance)-100; updateRow_('Users',u._row,u);
    append_('Transactions',{id:id_(),user_id:u.id,amount:-100,reason:'预测投票入场',created_at:now_()});
    const vote = {id:id_(),user_id:u.id,trading_date:date,direction,stake:100,status:'pending',created_at:now_(),settled_at:'',won:''};
    append_('Votes',vote);
    return {tradingDate:date,direction,balance:u.balance,status:'pending'};
  } finally { lock.releaseLock(); }
}
function leaderboard_(token) {
  userByToken_(token);
  const users = rows_('Users'), votes = rows_('Votes');
  return users.map(u => {
    const settled = votes.filter(v => v.user_id === u.id && v.status === 'settled');
    const wins = settled.filter(v => v.won === true || String(v.won) === 'TRUE').length;
    return {user_id:u.id,nickname:u.nickname,p_balance:Number(u.balance||0),accuracy:settled.length ? wins/settled.length*100 : 0,played:settled.length};
  }).sort((a,b)=>b.p_balance-a.p_balance || b.accuracy-a.accuracy).slice(0,50);
}
function isAdmin_(key) {
  const expected = PropertiesService.getScriptProperties().getProperty('ADMIN_KEY');
  if (!expected || String(key || '') !== expected) throw new Error('ADMIN_AUTH_FAILED');
}
function syncAi_(b) {
  isAdmin_(b.adminKey);
  const date = String(b.tradingDate || '');
  const list = Array.isArray(b.predictions) ? b.predictions : [];
  const sh = ss_().getSheetByName('AiPredictions');
  list.forEach(p => {
    const agent = String(p.agent || '').slice(0,40);
    const prob = Number(p.prob_up);
    if (!agent || !isFinite(prob) || prob < 0 || prob > 1) return;
    const existing = rows_('AiPredictions').find(r => r.trading_date === date && r.agent === agent);
    const row = {trading_date:date,agent,prob_up:prob,confidence:Number(p.confidence||0),reason:String(p.reason||'').slice(0,1000),synced_at:now_()};
    if (existing) updateRow_('AiPredictions',existing._row,row); else append_('AiPredictions',row);
  });
  return {saved:list.length};
}
function settle_(b) {
  isAdmin_(b.adminKey);
  const date = String(b.tradingDate || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !['bull','bear'].includes(b.outcome)) throw new Error('INVALID_SETTLEMENT');
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    const votes = rows_('Votes').filter(v => v.trading_date === date && v.status !== 'settled');
    votes.forEach(v => {
      const won = v.direction === b.outcome;
      const u = rows_('Users').find(x => x.id === v.user_id);
      if (!u) return;
      // Correct vote returns stake plus a 100 P reward; wrong vote loses stake.
      if (won) {
        u.balance = Number(u.balance || 0) + 200;
        updateRow_('Users',u._row,u);
        append_('Transactions',{id:id_(),user_id:u.id,amount:200,reason:'投票命中结算',created_at:now_()});
      }
      v.status='settled'; v.settled_at=now_(); v.won=won;
      updateRow_('Votes',v._row,v);
    });
    return {settled:votes.length,tradingDate:date,outcome:b.outcome};
  } finally { lock.releaseLock(); }
}
function logout_(token) {
  const h = tokenHash_(token);
  const s = rows_('Sessions').find(x => x.token_hash === h);
  if (s) ss_().getSheetByName('Sessions').deleteRow(s._row);
  return {loggedOut:true};
}
