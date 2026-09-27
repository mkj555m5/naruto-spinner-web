/* ═════════ NARUTO MULTI-SPINNER — Frontend Logic ═════════ */
'use strict';

const $ = (id) => document.getElementById(id);

const state = {
  event: 'naruto',
  polling: null,
  lastLogLen: 0,
  lastHitsLen: 0,
};

/* ─────────── Toast ─────────── */
let toastTimer = null;
function toast(msg, isErr = false) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.toggle('err', isErr);
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
}

/* ─────────── Events grid ─────────── */
const EVENT_UI = [
  { key: 'naruto',  emoji: '🍥', name: 'NARUTO',         payload: '{1:33, 2:1, 3:553, 4:5, 13:2}' },
  { key: 'skywin',  emoji: '☁️', name: 'NARUTO SKYWIN',  payload: '{1:11, 2:1, 3:553, 4:5, 13:2}' },
  { key: 'fist',    emoji: '👊', name: 'NARUTO FIST',    payload: '{1:29, 2:1, 3:553, 4:3, 13:2}' },
  { key: 'sasuke',  emoji: '⚡', name: 'SASUKE BUNDLE',  payload: '{1:91, 2:1, 3:554, 4:5, 13:2}' },
  { key: 'all',     emoji: '🔥', name: '🔥 SPIN ALL EVENTS (1→2→3→4)', payload: 'كل الأحداث بالتتابع', all: true },
  { key: 'custom',  emoji: '🧪', name: 'CUSTOM HEX PAYLOAD', payload: 'payload مخصص', custom: true },
];

function renderEvents() {
  const grid = $('eventGrid');
  grid.innerHTML = '';
  for (const ev of EVENT_UI) {
    const card = document.createElement('div');
    card.className = 'event-card' + (ev.all ? ' all-events' : '') + (ev.custom ? ' custom' : '') +
      (state.event === ev.key ? ' selected' : '');
    card.setAttribute('role', 'radio');
    card.setAttribute('aria-checked', state.event === ev.key ? 'true' : 'false');
    card.tabIndex = 0;
    card.innerHTML = `
      <span class="event-emoji" aria-hidden="true">${ev.emoji}</span>
      <span class="event-name">${ev.name}</span>
      <span class="event-payload">${ev.payload}</span>`;
    const select = () => {
      state.event = ev.key;
      $('customWrap').hidden = ev.key !== 'custom';
      renderEvents();
    };
    card.addEventListener('click', select);
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); } });
    grid.appendChild(card);
  }
}

/* ─────────── Accounts ─────────── */
async function parseAccounts(showMsg = true) {
  const text = $('accountsText').value.trim();
  const msg = $('parseMsg');
  if (!text) {
    $('accCount').textContent = '0 حساب';
    msg.textContent = '';
    return null;
  }
  try {
    const res = await fetch('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accounts_text: text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'فشل التحليل');
    $('accCount').textContent = `${data.count} حساب`;
    if (showMsg) {
      msg.className = 'parse-msg ok';
      msg.textContent = `✓ تم تحليل ${data.count} حساب بنجاح`;
    }
    return data;
  } catch (e) {
    $('accCount').textContent = '0 حساب';
    msg.className = 'parse-msg err';
    msg.textContent = `✗ ${e.message}`;
    return null;
  }
}

/* ─────────── Terminal ─────────── */
const LEVEL_CLASS = {
  info: 't-info', ok: 't-ok', err: 't-err', head: 't-head',
  vrare: 't-vrare', rare: 't-rare', item: 't-item', dim: 'dim',
};

function appendLogs(logs) {
  const term = $('terminal');
  const start = Math.max(0, state.lastLogLen);
  if (logs.length < state.lastLogLen) { term.innerHTML = ''; state.lastLogLen = 0; }
  for (let i = state.lastLogLen; i < logs.length; i++) {
    const l = logs[i];
    const p = document.createElement('p');
    p.className = LEVEL_CLASS[l.level] || 't-info';
    const t = document.createElement('span');
    t.className = 't-time';
    t.textContent = `[${l.t}]`;
    p.appendChild(t);
    p.appendChild(document.createTextNode(' ' + l.msg));
    term.appendChild(p);
  }
  state.lastLogLen = logs.length;
  while (term.children.length > 500) term.removeChild(term.firstChild);
  if ($('autoScroll').checked) term.scrollTop = term.scrollHeight;
}

function renderHits(hits) {
  const list = $('hitsList');
  list.innerHTML = '';
  $('hitsCount').textContent = String(hits.length);
  if (!hits.length) {
    list.innerHTML = '<p class="dim empty-hits">لا توجد جوائز بعد — ابدأ السحب وستظهر هنا فوراً ✨</p>';
    return;
  }
  for (const h of hits.slice().reverse()) {
    const div = document.createElement('div');
    const isVR = h.includes('VERY RARE');
    div.className = 'hit ' + (isVR ? 'hit-vrare' : 'hit-rare');
    div.textContent = h;
    list.appendChild(div);
  }
}

/* ─────────── Polling ─────────── */
function setProgress(done, total) {
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
  $('progressFill').style.width = pct + '%';
  $('progressBar').setAttribute('aria-valuenow', String(pct));
}

async function pollState() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) return;
    const s = await res.json();

    appendLogs(s.logs || []);
    if ((s.hits || []).length !== state.lastHitsLen) {
      renderHits(s.hits || []);
      state.lastHitsLen = (s.hits || []).length;
    }

    $('statVrare').textContent = s.counters.very_rare;
    $('statRare').textContent = s.counters.rare;
    $('statNormal').textContent = s.counters.normal;
    $('statTotal').textContent = s.counters.total_items;

    $('accDone').textContent = s.accounts_done;
    $('accTotal').textContent = s.accounts_total;
    $('batchLabel').textContent = s.batch ? `Batch: ${s.batch}` : '—';
    $('eventLabel').textContent = 'الحدث: ' + (s.event || '—');
    $('tokenLabel').textContent = `Tokens: ${s.tokens_ready}`;
    setProgress(s.accounts_done, s.accounts_total);

    const running = s.running && !s.finished;
    $('startBtn').disabled = running;
    $('stopBtn').disabled = !running;
    $('liveDot').classList.toggle('on', running);
    $('serverStatus').textContent = running ? '● يعمل الآن' : '● متصل';
    $('serverStatus').className = 'badge ' + (running ? 'badge-ok' : 'badge-ok');

    if (!running && state.polling) {
      // keep polling at slower rate to catch final state; job finished
    }
  } catch (e) {
    $('serverStatus').textContent = '● غير متصل';
    $('serverStatus').className = 'badge badge-err';
  }
}

function startPolling() {
  if (state.polling) clearInterval(state.polling);
  state.polling = setInterval(pollState, 1500);
  pollState();
}

/* ─────────── Start / Stop ─────────── */
async function startJob() {
  const msg = $('startMsg');
  const parsed = await parseAccounts(true);
  if (!parsed || !parsed.count) {
    msg.className = 'parse-msg err';
    msg.textContent = '✗ أضف حسابات صحيحة أولاً';
    toast('أضف حسابات صحيحة أولاً', true);
    return;
  }
  const payload = {
    accounts_text: $('accountsText').value.trim(),
    event: state.event,
    custom_hex: state.event === 'custom' ? $('customHex').value.trim() : null,
    concurrency: parseInt($('concurrency').value) || 5,
    batch_size: parseInt($('batchSize').value) || 50,
    login_retry: parseInt($('loginRetry').value) || 3,
    start_from: parseInt($('startFrom').value) || 1,
  };
  if (state.event === 'custom' && !payload.custom_hex) {
    msg.className = 'parse-msg err';
    msg.textContent = '✗ أدخل Hex Payload أولاً';
    return;
  }
  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'فشل البدء');
    state.lastLogLen = 0;
    state.lastHitsLen = 0;
    $('terminal').innerHTML = '';
    $('startMsg').className = 'parse-msg ok';
    $('startMsg').textContent = `🚀 بدأ السحب — ${data.accounts} حساب — الحدث: ${data.event}`;
    toast(`🚀 بدأ السحب على ${data.accounts} حساب!`);
    startPolling();
  } catch (e) {
    msg.className = 'parse-msg err';
    msg.textContent = `✗ ${e.message}`;
    toast(e.message, true);
  }
}

async function stopJob() {
  try {
    const res = await fetch('/api/stop', { method: 'POST' });
    if (!res.ok) {
      const d = await res.json();
      throw new Error(d.detail || 'فشل الإيقاف');
    }
    toast('⏹ تم إرسال أمر الإيقاف');
  } catch (e) {
    toast(e.message, true);
  }
}

/* ─────────── File upload ─────────── */
function handleFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    $('accountsText').value = reader.result;
    parseAccounts(true);
    toast(`📂 تم تحميل الملف: ${file.name}`);
  };
  reader.readAsText(file);
}

/* ─────────── Init ─────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderEvents();

  $('parseBtn').addEventListener('click', () => parseAccounts(true));
  $('clearBtn').addEventListener('click', () => {
    $('accountsText').value = '';
    $('accCount').textContent = '0 حساب';
    $('parseMsg').textContent = '';
    toast('🗑️ تم مسح الحسابات');
  });
  $('startBtn').addEventListener('click', startJob);
  $('stopBtn').addEventListener('click', stopJob);
  $('clearLogBtn').addEventListener('click', () => {
    $('terminal').innerHTML = '';
    state.lastLogLen = 0;
  });
  $('fileInput').addEventListener('change', (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });

  startPolling();
});
