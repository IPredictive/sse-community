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
  AiPredictions: ['trading_date','agent','prob_up','confidence','reason','synced_at'],
  Settlements: ['trading_date','outcome','index_close','previous_close','settled_at'],
  WeeklyRewards: ['week_start','week_end','user_id','amount','reason','created_at']
};

function doGet() {
  return json_({ok:true,service:'SSE Community API',version:1,actions:['register','login','me','profile','vote','leaderboard','syncAi','settle']});
}
function doPost(e) {
  try {
    let body = {};
    const raw = (e && e.postData && e.postData.contents) || '';
    if (raw) {
      try { body = JSON.parse(raw); }
      catch (_) { body = Object.assign({}, (e && e.parameter) || {}); }
    } else {
      body = Object.assign({}, (e && e.parameter) || {});
    }
    const action = String(body.action || '');
    let result;
    switch (action) {
      case 'register': result = register_(body); break;
      case 'login': result = login_(body); break;
      case 'me': result = me_(body.token); break;
      case 'myVote': result = myVote_(body.token, body.tradingDate); break;
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
function dateKey_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) {
    return Utilities.formatDate(value, 'Asia/Singapore', 'yyyy-MM-dd');
  }
  const s = String(value || '').trim();
  const m = s.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : s;
}
function nextVoteDate_() {
  const now = new Date();
  const today = Utilities.formatDate(now, 'Asia/Singapore', 'yyyy-MM-dd');
  const hour = Number(Utilities.formatDate(now, 'Asia/Singapore', 'H'));
  const dow = Number(Utilities.formatDate(now, 'Asia/Singapore', 'u')); // Mon=1 ... Sun=7
  const parts = today.split('-').map(Number);
  let d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  if (!(dow >= 1 && dow <= 5 && hour < 9)) d.setUTCDate(d.getUTCDate() + 1);
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  return Utilities.formatDate(d, 'UTC', 'yyyy-MM-dd');
}
function myVote_(token, tradingDate) {
  const u = userByToken_(token);
  const date = dateKey_(tradingDate);
  const v = rows_('Votes').find(x => x.user_id === u.id && dateKey_(x.trading_date) === date);
  return v ? {tradingDate:date,direction:v.direction,status:v.status} : null;
}
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
  const expectedDate = nextVoteDate_();
  if (date !== expectedDate) throw new Error('INVALID_TRADING_DATE');
  if (date < todaySg || (date === todaySg && hourSg >= 9)) throw new Error('VOTING_CLOSED');
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (rows_('Votes').some(v => v.user_id === u.id && dateKey_(v.trading_date) === date)) throw new Error('ALREADY_VOTED');
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
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(date) || !['bull','bear','flat'].includes(b.outcome)) throw new Error('INVALID_SETTLEMENT');
  return settleDate_(date, b.outcome, Number(b.indexClose || 0), Number(b.previousClose || 0));
}
function settleDate_(date, outcome, indexClose, previousClose) {
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (rows_('Settlements').some(s => dateKey_(s.trading_date) === date)) {
      return {settled:0,tradingDate:date,outcome,alreadySettled:true};
    }
    const votes = rows_('Votes').filter(v => dateKey_(v.trading_date) === date && v.status !== 'settled');
    let settled = 0;
    votes.forEach(v => {
      const won = outcome === 'flat' ? false : v.direction === outcome;
      const u = rows_('Users').find(x => x.id === v.user_id);
      if (!u) return;
      if (won) {
        // Return the original 100 P stake plus 200 P profit = 300 P total.
        u.balance = Number(u.balance || 0) + 300;
        updateRow_('Users',u._row,u);
        append_('Transactions',{id:id_(),user_id:u.id,amount:100,reason:'猜对：退还下注本金',created_at:now_()});
        append_('Transactions',{id:id_(),user_id:u.id,amount:200,reason:'猜对奖励',created_at:now_()});
      }
      v.status='settled'; v.settled_at=now_(); v.won=won;
      updateRow_('Votes',v._row,v);
      settled++;
    });
    append_('Settlements',{trading_date:date,outcome,index_close:indexClose || '',previous_close:previousClose || '',settled_at:now_()});
    awardStreakBonuses_(date);
    return {settled,tradingDate:date,outcome,alreadySettled:false};
  } finally { lock.releaseLock(); }
}
function awardStreakBonuses_(date) {
  const users = rows_('Users');
  const votes = rows_('Votes').filter(v => v.status === 'settled')
    .sort((a,b) => dateKey_(b.trading_date).localeCompare(dateKey_(a.trading_date)));
  users.forEach(u => {
    const mine = votes.filter(v => v.user_id === u.id);
    const index = mine.findIndex(v => dateKey_(v.trading_date) === date);
    if (index < 0 || !(mine[index].won === true || String(mine[index].won) === 'TRUE')) return;
    let streak = 0;
    for (let i=index; i<mine.length; i++) {
      if (mine[i].won === true || String(mine[i].won) === 'TRUE') streak++;
      else break;
    }
    // Pay at each third consecutive correct prediction; transaction reason makes it auditable.
    if (streak > 0 && streak % 3 === 0) {
      const reason = '连续猜对3次奖励（截至' + date + '）';
      if (!rows_('Transactions').some(t => t.user_id === u.id && t.reason === reason)) {
        const fresh = rows_('Users').find(x => x.id === u.id);
        fresh.balance = Number(fresh.balance || 0) + 300;
        updateRow_('Users',fresh._row,fresh);
        append_('Transactions',{id:id_(),user_id:u.id,amount:300,reason,created_at:now_()});
      }
    }
  });
}
function fetchIndexKlines_() {
  const url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000001&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20200101&end=20500101&lmt=100';
  const response = UrlFetchApp.fetch(url,{muteHttpExceptions:true});
  if (response.getResponseCode() !== 200) throw new Error('INDEX_DATA_HTTP_' + response.getResponseCode());
  const payload = JSON.parse(response.getContentText());
  if (!payload || !payload.data || !Array.isArray(payload.data.klines)) throw new Error('INDEX_DATA_UNAVAILABLE');
  return payload.data.klines.map(line => {
    const p = String(line).split(',');
    return {date:p[0],close:Number(p[2])};
  }).filter(x => /^\\d{4}-\\d{2}-\\d{2}$/.test(x.date) && isFinite(x.close)).sort((a,b)=>a.date.localeCompare(b.date));
}
function autoSettleDaily() {
  const klines = fetchIndexKlines_();
  const byDate = {};
  klines.forEach((k,i) => { if (i > 0) byDate[k.date] = {close:k.close,previous:klines[i-1].close}; });
  const pendingDates = [...new Set(rows_('Votes').filter(v => v.status !== 'settled').map(v => dateKey_(v.trading_date)))].sort();
  const results = [];
  pendingDates.forEach(date => {
    const k = byDate[date];
    if (!k || rows_('Settlements').some(s => dateKey_(s.trading_date) === date)) return;
    const outcome = k.close > k.previous ? 'bull' : (k.close < k.previous ? 'bear' : 'flat');
    results.push(settleDate_(date,outcome,k.close,k.previous));
  });
  return {checked:pendingDates.length,settled:results};
}
function awardWeeklyChampion() {
  const now = new Date();
  const today = Utilities.formatDate(now,'Asia/Singapore','yyyy-MM-dd');
  const dow = Number(Utilities.formatDate(now,'Asia/Singapore','u'));
  // Run on Monday: award the previous Monday-Sunday week.
  if (dow !== 1) return {awarded:false,reason:'NOT_MONDAY'};
  const p = today.split('-').map(Number);
  const endDate = new Date(Date.UTC(p[0],p[1]-1,p[2])); endDate.setUTCDate(endDate.getUTCDate()-1);
  const startDate = new Date(endDate.getTime()); startDate.setUTCDate(startDate.getUTCDate()-6);
  const weekStart = Utilities.formatDate(startDate,'UTC','yyyy-MM-dd');
  const weekEnd = Utilities.formatDate(endDate,'UTC','yyyy-MM-dd');
  if (rows_('WeeklyRewards').some(r => r.week_start === weekStart && r.reason === '每周冠军奖励')) return {awarded:false,reason:'ALREADY_AWARDED'};
  const users = rows_('Users'), votes = rows_('Votes').filter(v => v.status === 'settled' && dateKey_(v.trading_date) >= weekStart && dateKey_(v.trading_date) <= weekEnd);
  const stats = users.map(u => {
    const mine = votes.filter(v => v.user_id === u.id);
    const wins = mine.filter(v => v.won === true || String(v.won) === 'TRUE').length;
    return {u,played:mine.length,wins,accuracy:mine.length ? wins/mine.length : 0};
  }).filter(x => x.played > 0).sort((a,b)=>b.wins-a.wins || b.accuracy-a.accuracy || Number(b.u.balance||0)-Number(a.u.balance||0));
  if (!stats.length) return {awarded:false,reason:'NO_SETTLED_VOTES',weekStart,weekEnd};
  const winner = stats[0].u;
  const fresh = rows_('Users').find(u => u.id === winner.id);
  fresh.balance = Number(fresh.balance || 0) + 1000;
  updateRow_('Users',fresh._row,fresh);
  append_('Transactions',{id:id_(),user_id:fresh.id,amount:1000,reason:'每周冠军奖励 ' + weekStart + ' 至 ' + weekEnd,created_at:now_()});
  append_('WeeklyRewards',{week_start:weekStart,week_end:weekEnd,user_id:fresh.id,amount:1000,reason:'每周冠军奖励',created_at:now_()});
  return {awarded:true,userId:fresh.id,nickname:fresh.nickname,amount:1000,weekStart,weekEnd};
}
function installAutoSettlementTriggers() {
  // Idempotently replace only this feature's triggers.
  ScriptApp.getProjectTriggers().filter(t => ['autoSettleDaily','awardWeeklyChampion'].includes(t.getHandlerFunction())).forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('autoSettleDaily').timeBased().everyDays(1).atHour(17).nearMinute(15).inTimezone('Asia/Singapore').create();
  ScriptApp.newTrigger('awardWeeklyChampion').timeBased().everyDays(1).atHour(9).nearMinute(15).inTimezone('Asia/Singapore').create();
  return {installed:true,daily:'17:00-18:00 Singapore time',weekly:'Mondays around 09:00 Singapore time'};
}
function logout_(token) {
  const h = tokenHash_(token);
  const s = rows_('Sessions').find(x => x.token_hash === h);
  if (s) ss_().getSheetByName('Sessions').deleteRow(s._row);
  return {loggedOut:true};
}
