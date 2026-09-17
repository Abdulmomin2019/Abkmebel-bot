#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_web.py — "ABK MEBEL" Telegram Mini App.

Bu — botning ichida ochiladigan ilova (BotFather ilovasiga o'xshash): pastda tab
tugmalari, ichida bo'limlar, hamma narsa tugmalar bilan. Telegram'da botdagi
«🏢 AI-Ofis / Ilova» tugmasi bosilganda shu sahifa ochiladi.

Bo'limlar:
    🏢 AI-Ofis   — xodimlar (odam qiyofasida), tanaffuslar, jurnal
    📋 Narxlar   — xizmatlar va narxlar
    ✍️ Buyurtma  — 6 qadamli anketani ko'rsatish
    📍 Manzil    — Plus Code, xarita/marshrut tugmalari, ish vaqti
    🤖 Bot       — bot nima qila oladi (qo'llanma)
    📊 Panel     — admin uchun: statistika, xodimlar, jurnal

Server manzillari (bot_manager.py ichida):
    GET /app          -> shu sahifa
    (ofis bo'limi /ofis/data bilan yangilanadi)
"""

import json


def render_app(data, live=False, admin=False, session=""):
    """Mini App sahifasini yasaydi.

    admin=True  — egasi (admin) uchun: 🏢 Ofis (odam qiyofasidagi jonli ofis) va 📊 Panel
    admin=False — mijozlar uchun: faqat 📋 Narxlar, ✍️ Buyurtma, 📍 Manzil, 🤖 Bot
    """
    if not admin:
        data = dict(data)                     # mijozga xodimlar/jurnal ko'rsatilmaydi
        data.pop("agents", None)
        data.pop("log", None)
    agents = data.get("agents", [])
    office_html = _office_section(agents, data, admin=admin, session=session)
    price_html = _price_section(data)
    order_html = _order_section(data)
    address_html = _address_section(data)
    bot_html = _bot_section(data)
    panel_html = _panel_section(data)

    return TEMPLATE.replace("__OFFICE__", office_html) \
                   .replace("__PRICE__", price_html) \
                   .replace("__ORDER__", order_html) \
                   .replace("__ADDRESS__", address_html) \
                   .replace("__BOT__", bot_html) \
                   .replace("__PANEL__", panel_html) \
                   .replace("__COMPANY__", data.get("company", "ABK MEBEL")) \
                   .replace("__CONTACT__", data.get("contact", "@abkmebel")) \
                   .replace("__TIME__", data.get("time", "")) \
                   .replace("__DATE__", data.get("date", "")) \
                   .replace("__LIVE__", "true" if live else "false") \
                   .replace("__SNAPSHOT__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__ADMIN__", "true" if admin else "false") \
                   .replace("__SESSION__", session or "") \
                   .replace("__ACTIVE_OFFICE__", " active" if admin else "") \
                   .replace("__HIDDEN_OFFICE__", "" if admin else " hidden") \
                   .replace("__HIDDEN_PANEL__", "" if admin else " hidden")


def _looks(agents):
    """Har bir xodimga rang (ilovadagi bilan bir xil)."""
    colors = {"postchi": "#3b82f6", "menejer": "#a855f7", "ofis": "#14b8a6", "suhbat": "#f59e0b"}
    return {a["key"]: colors.get(a["key"], "#64748b") for a in agents}


def _office_section(agents, data, admin=False, session=""):
    """🏢 Ofis bo'limi.

    Admin uchun: /ofis sahifasi (xodimlar ODAM QIYOFASIDA, ish stoli, monitor,
    tanaffus — hammasi jonli) ilova ichida ochiladi.
    Mijozlar uchun bu bo'lim umuman ko'rsatilmaydi.
    """
    if not admin:
        return '<div class="muted">🔒 Bu bo\'lim faqat admin uchun.</div>'
    src = "/ofis?embed=1" + ("&t=" + session if session else "")
    return (f'<iframe class="oframe" id="oframe" src="{src}" loading="lazy" '
            f'referrerpolicy="same-origin"></iframe>')


def _office_cards(agents, data):
    """Xodimlar kartalari (📊 Panel bo'limi uchun)."""
    colors = _looks(agents)
    cards = []
    for a in agents:
        metrics = "".join(f'<div class="m"><b>{m["value"]}</b><span>{m["label"]}</span></div>'
                          for m in a.get("metrics", []))
        cards.append(f'''
      <div class="card agent" data-agent="{a['key']}" style="--c:{colors[a['key']]}">
        <div class="ahead">
          <div class="face" style="--c:{colors[a['key']]}">{a['emoji']}</div>
          <div class="aname"><b>{a['name']}</b><span>{a.get('status_label','')}</span></div>
        </div>
        <p class="task">{a.get('task','')}</p>
        <div class="metrics">{metrics}</div>
        <button class="btn wide ask" data-ask="{a['key']}" style="--c:{colors[a['key']]}">
          💬 Savol berish / buyruq berish</button>
      </div>''')
    schedule = "".join(
        f'<div class="slot {"done" if s.get("sent") else ""}"><b>{s["time"]}</b>'
        f'<span>{s["label"]}</span><i>{"✅" if s.get("sent") else "⏳"}</i></div>'
        for s in data.get("schedule", []))
    log = "".join(
        f'<div class="logrow"><b>{e["time"]}</b><span>{e.get("emoji","•")}</span>'
        f'<span>{e["action"]}</span></div>' for e in data.get("log", [])) or \
        '<div class="logrow empty">Bugun hali amal bo\'lmagan</div>'
    return f'''
  <div class="headline">{data.get('headline','')}</div>
  <div class="grid">{''.join(cards)}</div>
  <h3>📢 Kanal holati</h3>
  <div class="slots">{schedule}</div>
  <h3>📋 Bugungi jurnal</h3>
  <div class="log">{log}</div>'''


def _price_section(data):
    return f'''
  <h3>📋 Xizmatlar va narxlar</h3>
  <div class="card">
    <b>🗂 BAZIS-Mebel loyihasi</b>
    <p>3D ko'rinish + detallar + to'liq smeta (material, kromka, furnitura).</p>
    <div class="pricebig">material m² uchun 2$</div>
    <p class="muted">10 m² loyiha ≈ 20$ · aniq summa o'lchovdan keyin aytiladi.</p>
  </div>
  <div class="card">
    <b>⚙️ FastReport shablon va skriptlar</b>
    <p>Hisobotlaringiz uchun tayyor shablon va skriptlar, o'rnatishda yordam.</p>
    <p class="muted">Narx ish hajmiga qarab kelishiladi.</p>
  </div>
  <div class="card">
    <b>🧮 Narx kalkulyatori</b>
    <p class="muted">Xonangiz m² ini bilsangiz — summani darhol hisoblab beramiz.</p>
    <button class="btn wide" data-jump="calc">🧮 Kalkulyatorga o'tish</button>
  </div>'''


def _order_section(data):
    steps = []
    for s in data.get("order_steps", []) or DEFAULT_STEPS:
        q = s.get("q", s) if isinstance(s, dict) else str(s)
        steps.append(f'<div class="step"><i>{len(steps) + 1}</i><span>{q}</span></div>')
    return f'''
  <h3>✍️ Buyurtma berish — 6 qadam</h3>
  <div class="card">
    <p class="muted">Anketani to'ldirsangiz, dalolatnoma loyihasi tayyorlab beriladi.
    Har bir qadamni botda ketma-ket yozasiz.</p>
    {''.join(steps)}
    <button class="btn wide" data-jump="order">✍️ Buyurtmani botda boshlash</button>
  </div>'''


DEFAULT_STEPS = [
    "Ism-familiya (kim uchun tayyorlanadi)",
    "Telefon raqami",
    "Mebel turi va bo'linishlar",
    "Aniq o'lchamlar (gabarit)",
    "Material va furnitura (LDSP/MDF, rang, qalinlik, kromka, mexanizmlar)",
    "Muddat (qachonga kerak)",
]


def _address_section(data):
    return f'''
  <h3>📍 Manzil va ish vaqti</h3>
  <div class="card">
    <b>ABK MEBEL — Plus Code: 9754+W32, Toshkent</b>
    <p class="muted">{data.get('hours','09:00 – 18:00, har kuni')}</p>
    <div class="row2">
      <a class="btn" target="_blank" rel="noopener"
         href="https://maps.google.com/?q=9754%2BW32%20Tashkent">🗺 Xaritada ochish</a>
      <a class="btn" target="_blank" rel="noopener"
         href="https://www.google.com/maps/dir/?api=1&destination=9754%2BW32%20Tashkent">🚕 Marshrut</a>
    </div>
    <p class="muted">Aloqa: {data.get('contact','@abkmebel')} (telefon raqami yo'q — faqat Telegram)</p>
  </div>'''


def _bot_section(data):
    return '''
  <h3>🤖 Bot nima qila oladi</h3>
  <div class="card">
    <ul class="list">
      <li>💬 Narx, kromka, FastReport, muddat, smeta haqidagi savollarga darhol javob</li>
      <li>🗣 Xato yozilgan savollarni ham tushunadi: «pryikt qanchaga chizasan» → narx aytadi</li>
      <li>🧮 Narx kalkulyatori (m² → summa)</li>
      <li>✍️ 6 qadamli buyurtma anketasi + dalolatnoma loyihasi</li>
      <li>📍 Manzil, xarita va marshrut</li>
      <li>🖼 Namuna loyihalar</li>
      <li>📊 Har kuni 18:30 da egasiga hisobot</li>
    </ul>
  </div>
  <h3>⌨️ Komandalar</h3>
  <div class="card cmds">
    <code>/narx</code><code>/manzil</code><code>/buyurtma</code><code>/ofis</code>
    <code>/agents</code><code>/guruh</code><code>/help</code>
  </div>'''


def _panel_section(data):
    ch = data.get("channel", {})
    return f'''
  <h3>📊 Panel (bot egasi uchun)</h3>
  <div class="card">
    <div class="stats">
      <div class="m"><b>{ch.get('members','—')}</b><span>kanal a'zosi</span></div>
      <div class="m"><b>{data.get('orders_month',0)}</b><span>buyurtma (30 kun)</span></div>
      <div class="m"><b>{data.get('pending_orders',0)}</b><span>javob kutayotgan</span></div>
      <div class="m"><b>{data.get('agents_working',0)}/{len(data.get('agents',[]))}</b><span>xodim ishda</span></div>
    </div>
    <p class="muted">{data.get('next_report','')}</p>
    <button class="btn wide" data-jump="ofis">🏢 Xodimlar holatini ko'rish</button>
  </div>
  {_office_cards(data.get("agents", []), data) if data.get("agents") else ""}'''


TEMPLATE = r"""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>__COMPANY__ — ilova</title>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="logo">АБ</div>
    <div class="ttl"><b>__COMPANY__</b><span id="sub">__DATE__ · __TIME__</span></div>
    <div class="live">__LIVE__<span>jonli</span></div>
  </header>

  <main id="views">
    <section class="view__ACTIVE_OFFICE__" id="v-ofis"__HIDDEN_OFFICE__>__OFFICE__</section>
    <section class="view" id="v-price">__PRICE__</section>
    <section class="view" id="v-order">__ORDER__</section>
    <section class="view" id="v-address">__ADDRESS__</section>
    <section class="view" id="v-bot">__BOT__</section>
    <section class="view" id="v-panel"__HIDDEN_PANEL__>__PANEL__</section>
  </main>

  <nav class="tabs">
    <button class="tab__ACTIVE_OFFICE__" data-v="ofis" data-admin="1"__HIDDEN_OFFICE__>🏢<span>Ofis</span></button>
    <button class="tab" data-v="price">📋<span>Narxlar</span></button>
    <button class="tab" data-v="order">✍️<span>Buyurtma</span></button>
    <button class="tab" data-v="address">📍<span>Manzil</span></button>
    <button class="tab" data-v="bot">🤖<span>Bot</span></button>
    <button class="tab" data-v="panel" data-admin="1"__HIDDEN_PANEL__>📊<span>Panel</span></button>
  </nav>
</div>

<div class="modal" id="modal" hidden>
  <div class="mcard">
    <div class="mhead"><b id="mname">AI-xodim</b><button id="mclose">✕</button></div>
    <div class="chat" id="chat"></div>
    <div class="mchips" id="chips"></div>
    <div class="minput">
      <input id="minput" placeholder="Savol yoki buyruq yozing…">
      <button id="msend">➤</button>
    </div>
  </div>
</div>

<script>
const LIVE = __LIVE__;
const ADMIN = __ADMIN__;
const SESSION = "__SESSION__";
const DATA = __SNAPSHOT__;
const AG = {};
(DATA.agents || []).forEach(a => AG[a.key] = a);

/* --- tablar --- */
function show(v) {
  document.querySelectorAll('.view').forEach(s => s.classList.toggle('active', s.id === 'v-' + v));
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.v === v));
  window.scrollTo({top: 0, behavior: 'smooth'});
  if (window.Telegram && Telegram.WebApp) Telegram.WebApp.HapticFeedback?.selectionChanged?.();
}
document.querySelectorAll('.tab').forEach(b => b.onclick = () => show(b.dataset.v));
const JUMP = {calc: 'price', order: 'order', ofis: 'ofis'};
document.addEventListener('click', e => {
  const j = e.target.closest('[data-jump]');
  if (j) show(JUMP[j.dataset.jump] || 'ofis');
});

/* --- Telegram Mini App --- */
let TG = null;
try {
  TG = window.Telegram ? window.Telegram.WebApp : null;
  if (TG) { TG.ready(); TG.expand(); TG.setHeaderColor?.('#0d1526'); TG.setBackgroundColor?.('#080e1a'); }
} catch (e) {}

/* --- Kim kirgan? Faqat ADMIN ofisni ko'radi --- */
function unlockOffice(token) {
  if (!token) return;
  const ofis = document.getElementById('v-ofis');
  if (ofis && !ofis.querySelector('iframe')) {
    ofis.innerHTML = '<iframe class="oframe" src="/ofis?embed=1&t=' +
      encodeURIComponent(token) + '" referrerpolicy="same-origin"></iframe>';
  }
  document.querySelectorAll('[data-admin]').forEach(el => el.removeAttribute('hidden'));
  const v = document.getElementById('v-ofis');
  if (v) v.classList.add('active');
  const nav = document.querySelector('.tab[data-v="ofis"]');
  if (nav) nav.classList.add('active');
  document.querySelector('.tab[data-v="price"]')?.classList.remove('active');
  document.querySelectorAll('.view').forEach(s => { if (s.id !== 'v-ofis') s.classList.remove('active'); });
  fetch('/app/panel' + (token ? '?t=' + encodeURIComponent(token) : ''))
    .then(r => r.ok ? r.text() : '')
    .then(html => { if (html) document.getElementById('v-panel').innerHTML = html; })
    .catch(() => {});
}

async function whoami() {
  if (ADMIN) return;
  const init = (TG && TG.initData) || '';
  if (!init) return;                       // brauzerda ochilgan — mijoz ko'rinishi qoladi
  try {
    const r = await fetch('/app/me', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                      body: JSON.stringify({initData: init})});
    const j = await r.json();
    if (j && j.admin) unlockOffice(j.token);
  } catch (e) {}
}
whoami();

/* --- vaqt --- */
setInterval(() => {
  const d = new Date(), hh = String(d.getHours()).padStart(2,'0'), mm = String(d.getMinutes()).padStart(2,'0');
  const s = document.getElementById('sub');
  if (s) s.textContent = s.textContent.replace(/\d\d:\d\d/, hh + ':' + mm);
}, 20000);

/* --- jonli yangilash --- */
async function refresh() {
  if (!LIVE) return;
  try {
    const r = await fetch('/ofis/data?_=' + Date.now());
    if (!r.ok) return;
    const d = await r.json();
    const hl = document.querySelector('.headline');
    if (hl && d.headline) hl.textContent = d.headline;
    (d.agents || []).forEach(a => {
      const card = document.querySelector('.agent[data-agent="' + a.key + '"]');
      if (!card) return;
      card.querySelector('.aname span').textContent = a.status_label || '';
      card.querySelector('.task').textContent = a.task || '';
      (a.metrics || []).forEach(m => {
        const el = card.querySelector('.m b');
      });
    });
    const box = document.querySelector('.log');
    if (box && d.log) box.innerHTML = d.log.map(e =>
      '<div class="logrow"><b>' + e.time + '</b><span>' + e.emoji + '</span><span>' +
      e.action + '</span></div>').join('');
  } catch (e) {}
}
if (LIVE) { setInterval(refresh, 10000); }

/* --- xodim bilan suhbat --- */
function chatAdd(side, text, emoji) {
  const box = document.getElementById('chat');
  const d = document.createElement('div');
  d.className = 'cmsg ' + side;
  d.innerHTML = (emoji ? '<span class="cav">' + emoji + '</span>' : '') +
                '<div class="cbub">' + String(text).replace(/\n/g, '<br>') + '</div>';
  box.appendChild(d); box.scrollTop = box.scrollHeight;
}
function has(t, w) { return w.some(x => new RegExp('(^|[^\\w\'])' + x, 'i').test(t)); }
function localReply(k, text) {
  const a = AG[k] || {}, t = (text || '').toLowerCase();
  if (!t) return {reply: 'Savolingizni yozing 🙂'};
  if (has(t, ['salom','assalom','xayrli'])) return {reply: 'Assalomu alaykum! Men — ' + a.name + '. ' + (a.task || '')};
  if (has(t, ['narx','qancha','summa','hisob','kromka'])) return {reply: 'Loyiha narxi: material kvadratiga 2$. 10 m² ≈ 20$.'};
  if (has(t, ['manzil','qayerda','xarita','vaqt'])) return {reply: '📍 9754+W32, Toshkent. Ish vaqti: 09:00–18:00, har kuni.'};
  if (has(t, ['nima','qilyapsan','holat'])) return {reply: 'Men hozir: ' + (a.status_label||'') + ' · ' + (a.task||'')};
  if (has(t, ['nechta','natija','hisobot'])) return {reply: 'Bugungi natijalarim: ' + (a.metrics||[]).map(m => m.label + ': ' + m.value).join(' · ')};
  if (has(t, ['tanaffus','kofe','suv','ovqat'])) return {reply: '☕ Tanaffus qilib olaman!', action: 'break:coffee'};
  return {reply: 'Savolni tushunmadim 🤔 Quyidagilardan birini sinab ko\'ring.'};
}
async function ask(k, text) {
  if (LIVE) {
    try {
      const kk = (() => { try { return localStorage.getItem('officeKey') || ''; } catch (e) { return ''; } })();
      const r = await fetch('/ofis/ask', {method: 'POST',
        headers: Object.assign({'Content-Type': 'application/json'}, kk ? {'X-Office-Key': kk} : {}),
        body: JSON.stringify({agent: k, text})});
      if (r.ok) return await r.json();
    } catch (e) {}
  }
  return localReply(k, text);
}
const ASKS = {
  postchi: ['Nima qilyapsan?', 'Keyingi post qachon?', '🗂 Postni hozir tashla'],
  menejer: ['Nima qilyapsan?', 'Narx qancha?', 'Ish vaqti qanday?'],
  ofis: ['Manzil qayerda?', 'Bugungi natijalar', '☕ Tanaffus qil'],
  suhbat: ['Xato yozilgan savolni tushunasanmi?', 'Premium emoji nima beradi?'],
};
let CUR = null;
function openChat(k) {
  const a = AG[k] || {}; CUR = k;
  document.getElementById('mname').textContent = a.emoji + ' ' + a.name;
  const box = document.getElementById('chat'); box.innerHTML = '';
  chatAdd('bot', 'Assalomu alaykum! Men — ' + a.name + '. ' + (a.duty || '') + '\n\nSavol yozing yoki tugmani bosing 👇', a.emoji);
  const chips = document.getElementById('chips'); chips.innerHTML = '';
  (ASKS[k] || []).concat(['☕ Tanaffus qil', '⏸ To\'xta', '▶️ Ishla']).forEach(t => {
    const b = document.createElement('button'); b.className = 'chip'; b.textContent = t;
    b.onclick = () => send(t); chips.appendChild(b);
  });
  document.getElementById('modal').hidden = false;
}
async function send(text) {
  if (!text || !CUR) return;
  chatAdd('me', text);
  const r = await ask(CUR, text);
  chatAdd('bot', r.reply || '…', (AG[CUR] || {}).emoji);
  if (window.Telegram && Telegram.WebApp) Telegram.WebApp.HapticFeedback?.impactOccurred?.('light');
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-ask]');
  if (a) { openChat(a.dataset.ask); e.stopPropagation(); }
});
document.getElementById('mclose').onclick = () => document.getElementById('modal').hidden = true;
document.getElementById('modal').onclick = e => { if (e.target.id === 'modal') document.getElementById('modal').hidden = true; };
document.getElementById('msend').onclick = () => { const i = document.getElementById('minput'); send(i.value.trim()); i.value = ''; };
document.getElementById('minput').addEventListener('keydown', e => {
  if (e.key === 'Enter') { send(e.target.value.trim()); e.target.value = ''; }
});
</script>
</body>
<style>
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent }
  html,body { margin:0; background:#080e1a; color:#e8eef7;
    font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif }
  .app { max-width:560px; margin:0 auto; padding:12px 12px 84px }
  .top { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:16px;
    background:linear-gradient(150deg,#182642,#101a2e); border:1px solid #23344f; margin-bottom:12px }
  .logo { width:40px; height:40px; border-radius:12px; display:flex; align-items:center;
    justify-content:center; font-weight:800; color:#1a1206;
    background:linear-gradient(140deg,#f0cf7a,#b3872c) }
  .ttl { flex:1 } .ttl b { display:block; font-size:15px } .ttl span { font-size:11.5px; color:#8fa6c4 }
  .live { font-size:0; } .live span { font-size:10.5px; color:#7ee0a0; background:#122a1f;
    border:1px solid #2c5f42; border-radius:20px; padding:3px 8px }
  .view { display:none } .view.active { display:block; animation:fade .22s ease }
  @keyframes fade { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:none } }
  h3 { font-size:13.5px; margin:16px 2px 8px; color:#cfe0ee }
  .headline { font-size:12.5px; color:#9fb6d4; background:rgba(24,38,62,.6); border:1px dashed #2c4666;
    border-radius:12px; padding:8px 11px; margin-bottom:10px }
  .grid { display:grid; grid-template-columns:1fr; gap:10px }
  .card { background:linear-gradient(160deg,rgba(22,35,58,.95),rgba(13,21,36,.95));
    border:1px solid #223350; border-radius:16px; padding:12px }
  .card.agent { border-left:3px solid var(--c) }
  .ahead { display:flex; align-items:center; gap:10px }
  .face { width:36px; height:36px; border-radius:11px; background:var(--c); display:flex;
    align-items:center; justify-content:center; font-size:18px }
  .aname b { display:block; font-size:14px } .aname span { font-size:11px; color:#8fa6c4 }
  .task { font-size:12px; color:#a9c0dc; margin:9px 0 8px; line-height:1.5 }
  .metrics { display:flex; gap:6px; margin-bottom:10px }
  .m { flex:1; background:rgba(12,20,36,.9); border:1px solid #1e2c46; border-radius:11px;
    padding:6px; text-align:center }
  .m b { display:block; font-size:14px; color:#ffd97a } .m span { font-size:10px; color:#8fa6c4 }
  .btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; cursor:pointer;
    border:1px solid #2b3f63; background:rgba(19,30,50,.95); color:#e8eef7; font-size:12.5px;
    padding:10px 12px; border-radius:12px; text-decoration:none; font-weight:600 }
  .btn.wide { width:100% } .btn:active { transform:scale(.985) }
  .btn.ask { background:linear-gradient(140deg,var(--c),color-mix(in srgb,var(--c) 60%, #000)); border:0; color:#fff }
  .row2 { display:flex; gap:8px; margin:10px 0 } .row2 .btn { flex:1 }
  .slots { display:flex; flex-direction:column; gap:5px }
  .slot { display:flex; gap:8px; font-size:12px; background:rgba(14,24,40,.85); border:1px solid #1b2942;
    border-radius:10px; padding:7px 9px }
  .slot b { color:#7fb2e8; width:42px } .slot span { flex:1; color:#cfe0f3 }
  .slot.done { border-color:#2c5f42 }
  .log { display:flex; flex-direction:column; gap:5px; max-height:320px; overflow:auto }
  .logrow { display:flex; gap:7px; font-size:12px; color:#cfe0f3; background:rgba(14,24,40,.85);
    border:1px solid #1b2942; border-radius:10px; padding:6px 9px }
  .logrow b { color:#7fb2e8 } .logrow.empty { color:#7d92ad }
  .pricebig { font-size:20px; font-weight:800; color:#ffd97a; margin:8px 0 }
  .muted { font-size:12px; color:#8fa6c4; line-height:1.55 }
  .step { display:flex; gap:9px; align-items:flex-start; font-size:12.5px; color:#cfe0f3;
    padding:7px 0; border-bottom:1px solid #1b2942 }
  .step i { width:20px; height:20px; flex:0 0 auto; border-radius:50%; background:#1e3a60;
    color:#9fd0ff; font-size:11px; font-style:normal; display:flex; align-items:center; justify-content:center }
  .list { margin:0; padding-left:18px; font-size:12.5px; color:#cfe0f3; line-height:1.75 }
  .cmds { display:flex; flex-wrap:wrap; gap:6px }
  .cmds code { background:#0f1b2e; border:1px solid #1b2942; border-radius:8px; padding:4px 8px; font-size:12px }
  .stats { display:grid; grid-template-columns:1fr 1fr; gap:8px }

  .tabs { position:fixed; left:0; right:0; bottom:0; display:flex; justify-content:space-around;
    background:rgba(12,20,34,.97); border-top:1px solid #223350; padding:6px 4px calc(6px + env(safe-area-inset-bottom)) }
  [hidden] { display:none !important }
  .oframe { display:block; width:100%; height:calc(100vh - 128px); border:0; border-radius:16px;
            background:#0b1220; box-shadow:0 10px 30px rgba(0,0,0,.35) }
  .tab { background:none; border:0; color:#7d92ad; font-size:17px; display:flex; flex-direction:column;
    align-items:center; gap:2px; cursor:pointer; padding:4px 8px; border-radius:10px }
  .tab span { font-size:9.5px } .tab.active { color:#ffd97a; background:rgba(255,217,122,.08) }

  .modal { position:fixed; inset:0; background:rgba(4,8,16,.75); display:flex; align-items:flex-end;
    justify-content:center; z-index:60 }
  .modal[hidden] { display:none }
  .mcard { width:100%; max-width:560px; background:linear-gradient(170deg,#16233a,#0d1526);
    border:1px solid #26375a; border-radius:18px 18px 0 0; padding:12px; max-height:88vh; display:flex;
    flex-direction:column; gap:9px }
  .mhead { display:flex; align-items:center; gap:8px }
  .mhead b { flex:1; font-size:14px }
  .mhead button { background:none; border:0; color:#8fa6c4; font-size:16px; cursor:pointer }
  .chat { flex:1; min-height:150px; max-height:44vh; overflow:auto; display:flex; flex-direction:column; gap:7px;
    background:rgba(8,14,26,.7); border:1px solid #1b2942; border-radius:13px; padding:9px }
  .cmsg { display:flex; gap:7px; align-items:flex-end } .cmsg.me { flex-direction:row-reverse }
  .cav { width:24px; height:24px; border-radius:8px; background:#1e3a60; display:flex; align-items:center;
    justify-content:center; font-size:13px; flex:0 0 auto }
  .cbub { max-width:80%; font-size:12.5px; line-height:1.5; padding:8px 10px; border-radius:12px;
    background:#1b2942; border:1px solid #27395a }
  .cmsg.me .cbub { background:#2b5c9c; color:#fff; border-color:transparent }
  .mchips { display:flex; flex-wrap:wrap; gap:6px }
  .chip { border:1px solid #2b3f63; background:rgba(19,30,50,.95); color:#cfe0f3; font-size:11.5px;
    padding:6px 10px; border-radius:20px; cursor:pointer }
  .minput { display:flex; gap:7px }
  .minput input { flex:1; background:#0c1729; border:1px solid #26375a; color:#e8eef7; border-radius:12px;
    padding:11px; font-size:13px; font-family:inherit }
  .minput button { border:0; width:46px; border-radius:12px; cursor:pointer; font-size:15px; color:#08101d;
    background:linear-gradient(140deg,#f0cf7a,#b3872c) }
</style>
</html>
"""
