#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
office_web.py — "AI-OFIS" ilovasi.

Har bir xodim — haqiqiy odam qiyofasida: kompyuter oldida ishlaydi, klaviaturada
yozadi, ko'zlari pirpiraydi. Ish orasida tanaffus qiladi:
    ☕ kofe ichadi,  💧 kulerdan muzdek suv oladi,  🍽 ovqatlanadi.

YANGI: har bir xodim bilan shu yerda suhbatlashish mumkin —
xodimni bosib "💬 Savol berish" oynasini ochasiz, savol yozasiz yoki
buyruq berasiz (masalan "post tashla", "tanaffus qil", "hisobot").

Foydalanish:
    tools/build_office.py       -> ai-ofis.html (namunali nusxa, oflayn ishlaydi)
    serverda:  GET  /ofis       -> jonli sahifa (10 sekundda yangilanadi)
               GET  /ofis/data  -> JSON
               POST /ofis/ask   -> xodimga savol/buyruq ({"agent","text"})
"""

import json

# Har bir xodimga tashqi ko'rinish: ko'ylak rangi, soch rangi, teri rangi, soch turi
LOOKS = {
    "postchi": {"shirt": "#3b82f6", "shirt2": "#2563eb", "hair": "#2b2118", "skin": "#f2c39b",
                "hairstyle": "short", "accent": "#3b82f6"},
    "menejer": {"shirt": "#a855f7", "shirt2": "#7c3aed", "hair": "#3b2a1e", "skin": "#e8b487",
                "hairstyle": "bun", "accent": "#a855f7"},
    "ofis": {"shirt": "#14b8a6", "shirt2": "#0d9488", "hair": "#1f2937", "skin": "#f7d0ae",
             "hairstyle": "long", "accent": "#14b8a6"},
    "suhbat": {"shirt": "#f59e0b", "shirt2": "#d97706", "hair": "#4a2f1a", "skin": "#eab894",
               "hairstyle": "cap", "accent": "#f59e0b"},
}
DEFAULT_LOOK = {"shirt": "#64748b", "shirt2": "#475569", "hair": "#2b2118", "skin": "#f2c39b",
                "hairstyle": "short", "accent": "#64748b"}


def _hair(style, color):
    """Soch turi (SVG)."""
    if style == "bun":
        return (f'<path d="M34 30 q12 -16 32 0 q-6 -6 -16 -4 q-10 -2 -16 4 z" fill="{color}"/>'
                f'<circle cx="66" cy="22" r="7" fill="{color}"/>')
    if style == "long":
        return (f'<path d="M39 32 q5 -19 21 -19 q16 0 21 19 q-9 -10 -21 -10 q-12 0 -21 10 z" '
                f'fill="{color}"/>'
                f'<path d="M37 34 q-4 20 1 33 q4 -11 3 -22 q-1 -7 -4 -11 z" fill="{color}"/>'
                f'<path d="M83 34 q4 20 -1 33 q-4 -11 -3 -22 q1 -7 4 -11 z" fill="{color}"/>')
    if style == "cap":
        return (f'<path d="M30 28 q6 -18 20 -18 q14 0 20 18 z" fill="{color}"/>'
                f'<rect x="28" y="26" width="46" height="5" rx="2.5" fill="{color}"/>')
    return (f'<path d="M32 30 q4 -18 18 -18 q14 0 18 18 q-8 -8 -18 -8 q-10 0 -18 8 z" fill="{color}"/>')


def _character(a):
    """Bitta xodimning odam qiyofasi (SVG) — yuzi va tanasi to'liq ko'rinadi."""
    look = LOOKS.get(a.get("key"), DEFAULT_LOOK)
    hair = _hair(look["hairstyle"], look["hair"])
    return f'''
    <svg class="human" viewBox="0 0 120 150" xmlns="http://www.w3.org/2000/svg">
      <ellipse class="shadow" cx="60" cy="143" rx="26" ry="5"/>
      <g class="legs">
        <rect class="leg" x="46" y="104" width="12" height="38" rx="6" fill="{look['shirt2']}"/>
        <rect class="leg leg2" x="62" y="104" width="12" height="38" rx="6" fill="{look['shirt2']}"/>
        <rect x="42" y="138" width="18" height="8" rx="4" fill="#1f2937"/>
        <rect x="60" y="138" width="18" height="8" rx="4" fill="#1f2937"/>
      </g>
      <g class="torso">
        <path d="M40 62 q20 -8 40 0 l4 46 q-24 8 -48 0 z" fill="{look['shirt']}"/>
        <path d="M52 62 q8 6 16 0 l0 12 q-8 5 -16 0 z" fill="{look['shirt2']}" opacity=".75"/>
      </g>
      <g class="arms">
        <rect class="arm arm-l" x="30" y="68" width="11" height="36" rx="5.5" fill="{look['shirt2']}"/>
        <rect class="arm arm-r" x="79" y="68" width="11" height="36" rx="5.5" fill="{look['shirt2']}"/>
      </g>
      <g class="head">
        <circle cx="60" cy="42" r="21" fill="{look['skin']}"/>
        <path d="M39 42 q0 -22 21 -22 q21 0 21 22 q-6 -10 -21 -10 q-15 0 -21 10 z" fill="{look['hair']}"
              opacity=".35"/>
        {hair}
        <g class="eyes">
          <circle class="eye" cx="52" cy="42" r="2.6" fill="#1f2937"/>
          <circle class="eye" cx="68" cy="42" r="2.6" fill="#1f2937"/>
        </g>
        <path class="mouth" d="M55 51 q5 4 10 0" stroke="#8a5a3b" stroke-width="2" fill="none"
              stroke-linecap="round"/>
      </g>
      <g class="hand-item">
        <text x="86" y="90" font-size="22">☕</text>
      </g>
      <g class="zzz">
        <text x="84" y="28" font-size="15">💤</text>
      </g>
    </svg>'''


MACHINE_ICONS = {
    "coffee": '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="18" rx="3" fill="#3a5party"/>'
              '<rect x="4" y="3" width="16" height="18" rx="3" fill="#3a567f"/>'
              '<rect x="6" y="5" width="12" height="6" rx="2" fill="#0d1728"/>'
              '<rect x="10" y="12" width="4" height="2" rx="1" fill="#8ec5ff"/>'
              '<path d="M8 15h8v3a3 3 0 0 1-3 3h-2a3 3 0 0 1-3-3z" fill="#c98b52"/></svg>',
    "water": '<svg viewBox="0 0 24 24"><path d="M9 2h6v7H9z" fill="#5fb0e8" opacity=".85"/>'
             '<rect x="7" y="9" width="10" height="12" rx="2" fill="#2e4468"/>'
             '<rect x="11" y="12" width="2" height="4" rx="1" fill="#8ec5ff"/>'
             '<circle cx="12" cy="19" r="1.5" fill="#ffd97a"/></svg>',
    "food": '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="14" rx="9" ry="4" fill="#dbe7f3"/>'
            '<ellipse cx="12" cy="13" rx="6" ry="2.6" fill="#f0b46a"/>'
            '<rect x="3" y="4" width="2" height="9" rx="1" fill="#cfd8e5"/>'
            '<rect x="19" y="4" width="2" height="9" rx="1" fill="#cfd8e5"/></svg>',
}

def _station(a, idx):
    """Bitta xodimning ish joyi (sahna) — xodim to'liq ko'rinadi, monitor yon tomonda."""
    look = LOOKS.get(a.get("key"), DEFAULT_LOOK)
    task = a.get("task", "") or ""
    brief = task if len(task) <= 26 else task[:24].rstrip() + "…"
    metrics = "".join(
        '<div class="metric"><span class="mnum" data-k="' + a["key"] + "-" + m["key"] + '">'
        + str(m["value"]) + '</span><span class="mlabel">' + m["label"] + "</span></div>"
        for m in a.get("metrics", []))
    return f'''
      <div class="station" data-agent="{a['key']}" data-index="{idx}" style="--accent:{look['accent']}">
        <div class="scene">
          <div class="wall"></div>
          <div class="floor"></div>
          <div class="window"><span class="sky"></span><span class="cloud c1"></span>
            <span class="cloud c2"></span><span class="frame"></span></div>
          <div class="clock-face" data-clock="{a['key']}"><b>09:00</b></div>
          <div class="wallart"></div>
          <div class="plant"><i></i><b></b></div>
          <div class="corner">
            <div class="machine" data-m="coffee" title="Kofe mashinasi">{MACHINE_ICONS['coffee']}</div>
            <div class="machine" data-m="water" title="Kuler — muzdek suv">{MACHINE_ICONS['water']}</div>
            <div class="machine" data-m="food" title="Tushlik">{MACHINE_ICONS['food']}</div>
          </div>
          <div class="chair"></div>
          <div class="human-wrap">{_character(a)}</div>
          <div class="desk">
            <div class="desk-top"></div>
            <div class="desk-body"></div>
            <div class="monitor">
              <div class="screen">
                <div class="row r1"></div><div class="row r2"></div><div class="row r3"></div>
              </div>
            </div>
            <div class="monitor-stand"></div>
            <div class="kbd"></div>
            <div class="mouse"></div>
            <div class="cup">☕<span class="steam"></span></div>
          </div>
          <div class="bubble" data-bubble="{a['key']}">{brief}</div>
          <div class="badge"><b>{a['emoji']} {a['name']}</b><span>{a.get('role','')}</span></div>
          <div class="statusbar">
            <span class="taskchip" data-task="{a['key']}">{a.get('task','')}</span>
            <button class="askbtn" type="button" data-ask="{a['key']}">💬 Savol berish</button>
          </div>
        </div>
        <div class="metrics">{metrics}</div>
      </div>'''


EMBED_CSS = """
/* Ilova ichida (iframe) ochilganda: sarlavha va ortiqcha bo'shliqlar yashiriladi */
body.embed > .app > header { display: none !important }
body.embed > .app { padding-top: 10px !important; max-width: 100% !important }
body.embed .headline { margin-top: 4px !important }
body.embed .brand p { display: none }
"""


def lock_html():
    """Ofis bo'limi faqat admin uchun — boshqalarga shu sahifa ko'rsatiladi."""
    return """<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔒 Faqat admin uchun</title>
<style>
 body{margin:0;background:#080e1a;color:#e6eefc;font-family:system-ui,Segoe UI,Roboto,sans-serif;
      display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px}
 .box{max-width:520px;background:linear-gradient(170deg,#141f36,#0d1526);border:1px solid #24314f;
      border-radius:20px;padding:28px 26px;text-align:center}
 .ic{font-size:52px;margin-bottom:10px}
 h1{font-size:21px;margin:0 0 10px}
 p{color:#9fb6d4;font-size:14.5px;line-height:1.65;margin:0 0 14px}
 a{display:inline-block;margin-top:6px;background:#2563eb;color:#fff;text-decoration:none;
   padding:11px 18px;border-radius:12px;font-weight:600}
</style></head><body>
 <div class="box">
   <div class="ic">🔒</div>
   <h1>Bu bo'lim faqat admin uchun</h1>
   <p>AI-ofis (xodimlar, jurnal va buyruqlar) faqat bot egasiga ko'rinadi.
      Mijozlar uchun <b>narxlar</b>, <b>buyurtma</b> va <b>manzil</b> bo'limlari ochiq.</p>
   <a href="/app">📱 Ilovaga o'tish</a>
 </div>
</body></html>"""


def render_html(data, live=False, embed=False):
    """Butun ilovani yasaydi. embed=True — ilova ichida (iframe) ko'rsatish uchun."""
    stations = "".join(_station(a, i) for i, a in enumerate(data.get("agents", [])))

    schedule = "".join(
        '<div class="slot ' + ("done" if s.get("sent") else "wait") + '">'
        '<b>' + s["time"] + '</b><span>' + s["label"] + '</span>'
        '<i>' + ("✅" if s.get("sent") else "⏳") + "</i></div>"
        for s in data.get("schedule", []))

    posts = "".join('<div class="post"><b>' + p.get("time", "") + '</b><span>'
                    + p.get("text", "") + "</span></div>"
                    for p in data.get("channel", {}).get("posts", [])) or \
        '<div class="post empty">Kanal postlari hali yuklanmagan</div>'

    duties = "".join('<div class="duty"><b>' + a["emoji"] + " " + a["name"] + "</b><p>"
                     + a["duty"] + '</p><span class="duty-task">' + a.get("task", "") + "</span></div>"
                     for a in data.get("agents", []))

    live_badge = ('<span class="badge live">🟢 JONLI rejim</span>' if live
                  else '<span class="badge">📄 namunali nusxa</span>')

    info = {
        "price": data.get("price_text", ""),
        "address": data.get("address_text", ""),
        "hours": data.get("hours", ""),
        "contact": data.get("contact", "@abkmebel"),
    }

    html = TEMPLATE
    for token, value in [
        ("__STATIONS__", stations),
        ("__SCHEDULE__", schedule),
        ("__POSTS__", posts),
        ("__DUTIES__", duties),
        ("__LIVE_BADGE__", live_badge),
        ("__COMPANY__", data.get("company", "ABK MEBEL")),
        ("__TIME__", data.get("time", "")),
        ("__DATE__", data.get("date", "")),
        ("__HEADLINE__", data.get("headline", "")),
        ("__WORKING__", str(data.get("agents_working", 0))),
        ("__TOTAL__", str(len(data.get("agents", [])))),
        ("__MEMBERS__", str(data.get("channel", {}).get("members", "—"))),
        ("__ORDERS__", str(data.get("orders_month", 0))),
        ("__PENDING__", str(data.get("pending_orders", 0))),
        ("__NEXT_REPORT__", data.get("next_report", "—")),
        ("__CONTACT__", data.get("contact", "@abkmebel")),
        ("__HOURS__", data.get("hours", "09:00–18:00")),
        ("__LOCKED__", "true" if data.get("office_locked") else "false"),
        ("__INFO__", json.dumps(info, ensure_ascii=False)),
        ("__LOG_HTML__", "".join(
            '<div class="entry"><b>' + e["time"] + '</b><span class="em">' + e.get("emoji", "•")
            + '</span><span>' + e["action"] + "</span></div>" for e in data.get("log", []))
            or '<div class="entry empty">Bugun hali amal bo\'lmagan</div>'),
        ("__LIVE__", "true" if live else "false"),
        ("__SNAPSHOT__", json.dumps(data, ensure_ascii=False)),
        ("__EMBED__", "true" if embed else "false"),
    ]:
        html = html.replace(token, value)
    if embed:
        html = html.replace("</style>", EMBED_CSS + "</style>", 1)
    return html


TEMPLATE = r"""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-OFIS — __COMPANY__</title>
</head>
<body>
<div class="app">
  <header>
    <div class="brand">
      <div class="logo">АБ</div>
      <div>
        <h1>AI-OFIS <span>· __COMPANY__</span></h1>
        <p>Sizning nomingizdan ishlayotgan __TOTAL__ ta AI-xodim — <b>__WORKING__ tasi hozir ishda</b></p>
      </div>
    </div>
    <div class="headright">
      __LIVE_BADGE__
      <div class="clock"><b id="clock">__TIME__</b><span id="date">__DATE__</span></div>
    </div>
  </header>

  <p class="headline">__HEADLINE__</p>

  <div class="stats-strip">
    <div class="stat"><b>__TOTAL__</b><span>AI-xodim</span></div>
    <div class="stat"><b>__WORKING__</b><span>hozir ishda</span></div>
    <div class="stat"><b>__MEMBERS__</b><span>kanal a'zosi</span></div>
    <div class="stat"><b>__PENDING__</b><span>javob kutayotgan</span></div>
    <div class="stat"><b>__NEXT_REPORT__</b><span>keyingi hisobot</span></div>
  </div>

  <p class="hint">👆 Xodim ustiga bosing yoki <b>«💬 Savol berish»</b> tugmasini bosing —
    u bilan suhbatlashasiz va buyruq berasiz (masalan: «post tashla», «tanaffus qil», «hisobot»).</p>

  <section class="office">
    <div class="stations">__STATIONS__</div>
  </section>

  <div class="cols">
    <section class="panel">
      <h2>📋 Bugungi ishlar (jonli jurnal)</h2>
      <div class="log" id="log">__LOG_HTML__</div>
    </section>

    <section class="panel">
      <h2>📢 Kanal holati</h2>
      <div class="slots">__SCHEDULE__</div>
      <div class="posts-head">Kanaldagi oxirgi postlar</div>
      <div class="posts">__POSTS__</div>
      <div class="kanal-stats">
        <div><b>__MEMBERS__</b><span>kanal a'zolari</span></div>
        <div><b>__ORDERS__</b><span>buyurtma (30 kun)</span></div>
        <div><b>__PENDING__</b><span>javob kutayotgan</span></div>
      </div>
    </section>
  </div>

  <section class="panel wide">
    <h2>🎯 Xodimlarning vazifalari</h2>
    <div class="duties">__DUTIES__</div>
    <p class="note">Keyingi hisobot: <b>__NEXT_REPORT__</b> · Aloqa: __CONTACT__ ·
      Ish vaqti: __HOURS__ · Telegram'da: <code>/ofis</code> buyrug'i</p>
  </section>
</div>

<!-- ================= Suhbat oynasi (xodim bilan) ================= -->
<div class="modal" id="modal" hidden>
  <div class="modal-card" id="modalcard">
    <header class="mhead">
      <div class="mavatar" id="mavatar">🤖</div>
      <div class="mtitle"><b id="mname">AI-xodim</b><span id="mrole">vazifasi</span></div>
      <div class="mstatus" id="mstatus">🟢</div>
      <button class="mclose" id="mclose" type="button" title="Yopish">✕</button>
    </header>
    <p class="mduty" id="mduty"></p>
    <div class="mstats" id="mstats"></div>
    <div class="chat" id="chat"></div>
    <div class="chips" id="chips"></div>
    <div class="inputrow">
      <input id="minput" type="text" placeholder="Savolingizni yozing…" autocomplete="off">
      <button id="msend" type="button">Yuborish</button>
    </div>
    <p class="mnote" id="mnote"></p>
  </div>
</div>

<script>
const LIVE = __LIVE__;
const LOCKED = __LOCKED__;
const EMBED = __EMBED__;
const SES = (new URLSearchParams(location.search).get('t')) || '';
if (EMBED) document.body.classList.add('embed');
const DATA = __SNAPSHOT__;
const INFO = __INFO__;
const AGENTS = {};
(DATA.agents || []).forEach(a => AGENTS[a.key] = a);

/* ---------- 1) Soat ---------- */
function tick() {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, '0'), mm = String(d.getMinutes()).padStart(2, '0');
  const el = document.getElementById('clock');
  if (el) el.textContent = hh + ':' + mm;
  document.querySelectorAll('[data-clock] b').forEach(b => b.textContent = hh + ':' + mm);
  document.body.classList.toggle('night', d.getHours() < 7 || d.getHours() >= 20);
}
setInterval(tick, 20000); tick();

/* ---------- 2) Jurnalga yozish ---------- */
function addEntry(emoji, action) {
  const box = document.getElementById('log');
  if (!box) return;
  const d = new Date();
  const t = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  const div = document.createElement('div');
  div.className = 'entry new';
  div.innerHTML = '<b>' + t + '</b><span class="em">' + emoji + '</span><span>' + action + '</span>';
  box.prepend(div);
  while (box.children.length > 40) box.removeChild(box.lastChild);
}

/* ---------- 3) Tanaffuslar: kofe, kuler, ovqat ---------- */
const BREAKS = {
  coffee: {item: '☕', text: ['☕ Kofe tanaffusi', '☕ Kofe ichib olyapti', '☕ Qisqa kofe-pauza'],
           sip: '☕ Kofe kayfiyatni ko\'tardi 🙂', log: '☕ Kofe tanaffusi'},
  water: {item: '💧', text: ['💧 Kulerda muzdek suv ichyapti', '💧 Suv olib, sal dam oldi'],
          sip: '💧 Zambilak-zambilak! Muzdek ekan 😌', log: '💧 Kulerda suv ichdi'},
  food: {item: '🥪', text: ['🍽 Tushlik qilyapti', '🥪 Yengil ovqat tanaffusi', '🍎 Kuch yig\'yapti'],
         sip: '🍽 Ovqat juda mazali!', log: '🍽 Ovqat tanaffusi'},
};
const BREAK_TYPES = ['coffee', 'water', 'food'];

function stationOf(key) { return document.querySelector('[data-agent="' + key + '"]'); }

function setBubble(key, text) {
  const b = document.querySelector('[data-bubble="' + key + '"]');
  if (b) b.textContent = text;
}

function takeBreak(key, name, forceType) {
  const st = stationOf(key);
  if (!st || st.classList.contains('sleep')) return false;
  const type = forceType && BREAKS[forceType] ? forceType
             : BREAK_TYPES[Math.floor(Math.random() * BREAK_TYPES.length)];
  const br = BREAKS[type];
  st.classList.add('on-break', 'standing', type, 'walking');
  st.querySelectorAll('.machine').forEach(m => m.classList.remove('active'));
  const machine = st.querySelector('.machine[data-m="' + type + '"]');
  if (machine) machine.classList.add('active');
  const human = st.querySelector('.human');
  if (human) human.querySelector('.hand-item text').textContent = br.item;
  setBubble(key, br.text[Math.floor(Math.random() * br.text.length)]);

  setTimeout(() => {
    st.classList.add('drinking');
    st.classList.remove('walking');
    setBubble(key, br.sip);
  }, 1100);

  setTimeout(() => {
    st.classList.remove('drinking', 'on-break', 'standing', type);
    st.classList.add('walking');
    setBubble(key, '🙂 Dam oldim, ishga qaytdim');
    if (machine) machine.classList.remove('active');
  }, 9000);

  setTimeout(() => {
    st.classList.remove('walking');
    const task = st.querySelector('.taskchip');
    setBubble(key, task ? task.textContent : 'Ishni davom ettirmoqda');
    paintStation(AGENTS[key] || {});
  }, 10500);

  addEntry(br.item, '<b>' + name + '</b> ' + br.log);
  return true;
}

function scheduleBreaks(key, name) {
  const st = stationOf(key);
  if (!st) return;
  const delay = 18000 + Math.random() * 42000;   // 18–60 sekund
  setTimeout(() => {
    if (!st.classList.contains('sleep') && !st.classList.contains('on-break')) {
      takeBreak(key, name);
      scheduleBreaks(key, name);
    } else {
      scheduleBreaks(key, name);
    }
  }, delay + (st.dataset.index || 0) * 4000);
}

/* ---------- 4) Holatlarni chizish ---------- */
const KEYMAP = {ishlayapti: 'work', band: 'busy', bosh: 'idle', dam: 'sleep'};

function paintStation(a) {
  const st = stationOf(a.key);
  if (!st) return;
  st.classList.remove('work', 'busy', 'idle', 'sleep');
  st.classList.add(KEYMAP[a.status_key] || 'idle');
  st.querySelector('.badge span').textContent = a.status_label || a.role || '';
  const chip = st.querySelector('.taskchip');
  if (chip) chip.textContent = a.task;
  if (a.status_key === 'dam') {
    setBubble(a.key, '💤 Dam olmoqda (to\'xtatilgan)');
  } else if (!st.classList.contains('on-break')) {
    setBubble(a.key, a.task);
  }
  (a.metrics || []).forEach(m => {
    const el = st.querySelector('[data-k="' + a.key + '-' + m.key + '"]');
    if (el) el.textContent = m.value;
  });
}

/* ---------- 5) Boshlash ---------- */
(DATA.agents || []).forEach(a => {
  paintStation(a);
  if (a.status_key !== 'dam') scheduleBreaks(a.key, a.name);
});

setInterval(() => {
  document.querySelectorAll('.station.work .screen .row').forEach((r, i) => {
    r.style.animationDelay = (Math.random() * 0.8).toFixed(2) + 's';
  });
}, 4000);

/* ---------- 6) Jonli rejim ---------- */
async function refresh() {
  try {
    const r = await fetch('/ofis/data?_=' + Date.now(),
      SES ? {headers: {'X-Office-Session': SES}} : undefined);
    if (!r.ok) return;
    const data = await r.json();
    Object.keys(AGENTS).forEach(k => delete AGENTS[k]);
    (data.agents || []).forEach(a => { AGENTS[a.key] = a; paintStation(a); });
    const box = document.getElementById('log');
    if (box && data.log) {
      box.innerHTML = data.log.map(e =>
        '<div class="entry"><b>' + e.time + '</b><span class="em">' + e.emoji +
        '</span><span>' + e.action + '</span></div>').join('') ||
        '<div class="entry empty">Bugun hali amal bo\'lmagan</div>';
    }
    const h = document.querySelector('.headline');
    if (h && data.headline) h.textContent = data.headline;
  } catch (e) { /* oflayn nusxa */ }
}
if (LIVE) { setInterval(refresh, 10000); refresh(); }

/* ---------- 7) Namunali nusxa "tirik" ko'rinishi ---------- */
if (!LIVE && DATA.demo_lines) {
  let i = 0;
  setInterval(() => {
    const line = DATA.demo_lines[i % DATA.demo_lines.length];
    addEntry(line.emoji, line.action);
    i++;
  }, 7000);
}

/* ==========================================================================
   8) XODIM BILAN SUHBAT — savol va buyruqlar
   ========================================================================== */
let CURRENT = null;

function agentColor(key) {
  const st = stationOf(key);
  return st ? getComputedStyle(st).getPropertyValue('--accent').trim() || '#3b82f6' : '#3b82f6';
}

function chatAdd(side, text, emoji) {
  const box = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'cmsg ' + side;
  const body = String(text).replace(/\n/g, '<br>');
  div.innerHTML = (emoji ? '<span class="cav">' + emoji + '</span>' : '') +
                  '<div class="cbub">' + body + '</div>';
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function chipsRender(list, handler) {
  const box = document.getElementById('chips');
  box.innerHTML = '';
  list.forEach(label => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = label;
    b.addEventListener('click', () => handler(label));
    box.appendChild(b);
  });
}

function openChat(key) {
  const a = AGENTS[key];
  if (!a) return;
  CURRENT = key;
  const color = agentColor(key);
  const card = document.getElementById('modalcard');
  card.style.setProperty('--accent', color);
  document.getElementById('mavatar').textContent = a.emoji;
  document.getElementById('mavatar').style.background = color;
  document.getElementById('mname').textContent = a.name;
  document.getElementById('mrole').textContent = a.role || '';
  document.getElementById('mstatus').textContent = a.status_label || '';
  document.getElementById('mduty').innerHTML = '<b>Vazifasi:</b> ' + (a.duty || '—');
  const st = stationOf(key);
  const status = st ? (st.classList.contains('sleep') ? '💤 To\'xtatilgan'
                    : st.classList.contains('on-break') ? '☕ Tanaffusda' : '🟢 Ishda')
                    : '🟢 Ishda';
  document.getElementById('mstats').innerHTML =
    '<span class="pill">' + status + '</span>' +
    (a.metrics || []).map(m => '<span class="pill">' + m.label + ': <b>' + m.value + '</b></span>').join('') +
    (a.last ? '<span class="pill">oxirgi: ' + a.last + '</span>' : '');
  document.getElementById('chat').innerHTML = '';
  chatAdd('bot', 'Assalomu alaykum! Men — ' + a.name + ' (' + (a.role || '') + '). ' +
                 'Savolingizni yozing yoki quyidagi tugmalardan birini tanlang 👇', a.emoji);
  const cmds = ['Nima qilyapsan?', '☕ Tanaffus qil', '📊 Bugungi natijalar',
                '📜 Jurnalni ko\'rsat'];
  if (key === 'postchi') cmds.push('🗂 Postni hozir tashla');
  cmds.push('⏸ To\'xta', '▶️ Ishla');
  const seen = {};
  const chips = (a.asks || []).concat(cmds).filter(x => {
    const k = x.toLowerCase().replace(/[^\wа-яё]+/gi, '');
    if (seen[k]) return false;
    seen[k] = 1;
    return true;
  });
  chipsRender(chips, t => sendTo(key, t));
  const note = document.getElementById('mnote');
  if (LOCKED && !officeKey() && !SES) {
    note.innerHTML = '🔒 Buyruqlar (<i>post tashla, to\'xta</i>) uchun ilova kaliti kerak: ' +
      '<input id="keyin" placeholder="kalit" style="width:110px"> <button id="keysave">Saqlash</button>';
    document.getElementById('keysave').addEventListener('click', () => {
      saveOfficeKey(document.getElementById('keyin').value.trim());
      openChat(key);
    });
  } else {
    note.innerHTML = '💡 Buyruqlar: <i>post tashla</i>, <i>tanaffus qil</i>, <i>to\'xta</i>, ' +
                     '<i>ishla</i>, <i>jurnal</i>, <i>hisobot</i>';
  }
  document.getElementById('modal').hidden = false;
  setTimeout(() => document.getElementById('minput').focus(), 60);
}

function closeChat() {
  document.getElementById('modal').hidden = true;
  CURRENT = null;
}

/* ---- serverga so'rov (jonli rejim) yoki mahalliy javob (namuna) ---- */
function officeKey() {
  try { return localStorage.getItem('officeKey') || ''; } catch (e) { return ''; }
}
function saveOfficeKey(v) {
  try { localStorage.setItem('officeKey', v); } catch (e) { /* ko'rish oynasida taqiqlangan */ }
}

async function askAgent(key, text) {
  if (LIVE) {
    try {
      const headers = {'Content-Type': 'application/json'};
      const k = officeKey();
      if (k) headers['X-Office-Key'] = k;
      if (SES) headers['X-Office-Session'] = SES;
      const r = await fetch('/ofis/ask', {
        method: 'POST', headers: headers,
        body: JSON.stringify({agent: key, text: text})
      });
      if (r.ok) return await r.json();
    } catch (e) { /* quyida mahalliy javob beramiz */ }
  }
  return localReply(key, text);
}

/* ---- namunali nusxa uchun javoblar (serverga ulanmasa ham ishlaydi) ---- */
function has(text, words) {
  return words.some(w => new RegExp('(^|[^\\w\'])' + w, 'i').test(text));
}
function metric(a, key) {
  const m = (a.metrics || []).find(x => x.key === key);
  return m ? m.value : '—';
}
function localReply(key, text) {
  const a = AGENTS[key] || {};
  const t = (text || '').toLowerCase().trim();
  const st = stationOf(key);
  const sleeping = st && st.classList.contains('sleep');
  const reply = (s, action) => ({reply: s, action: action || null, agent: key, name: a.name || ''});

  if (!t) return reply('Marhamat, savolingizni yozing 🙂');
  if (has(t, ['salom', 'assalom', 'xayrli', 'hello', 'hi']))
    return reply('Assalomu alaykum! 👋 Men — ' + a.name + '. ' + (a.task || ''));
  if (has(t, ['rahmat', 'tashakkur']))
    return reply('Sizga rahmat! 🙌 Yana savolingiz bo\'lsa, shu yerda yozing.');
  if (has(t, ['tanaffus', 'dam', 'kofe', 'choy', 'suv', 'ovqat', 'tushlik'])) {
    const type = has(t, ['kofe', 'choy']) ? 'coffee' : has(t, ['ovqat', 'tushlik']) ? 'food'
               : has(t, ['suv']) ? 'water' : null;
    const word = {coffee: '☕ Kofe ichib olaman — kayfiyat ko\'tariladi!',
                  water: '💧 Kulerda muzdek suv ichib olaman 😌',
                  food: '🍽 Yengil tushlik qilib olaman.'}[type || 'coffee'];
    return reply(word, 'break:' + (type || 'random'));
  }
  if (has(t, ['to\'xta', 'toxta', 'to\'xtat', 'dam ol']))
    return reply('⏸ Meni to\'xtatdingiz. Ishga qaytarish uchun «ishla» deb yozing.',
                 LIVE ? 'toggle' : 'demo-toggle');
  if (has(t, ['ishla', 'davom', 'qayt']))
    return reply('🟢 Ishga qaytdim!', LIVE ? 'toggle' : 'demo-toggle');
  if (has(t, ['post', 'tashla', 'yubor'])) {
    if (key !== 'postchi') return reply('Postni faqat 🗂 Reklama agenti tashlaydi.');
    return reply(LIVE ? '🗂 Bo\'ldi, postni kanalga tashlayapman!' : '🗂 Bu namunali nusxa — ' +
                 'jonli rejimda post haqiqatan tashlanadi. Keyingi post: ' +
                 (a.task || 'jadval bo\'yicha'), LIVE ? 'post' : 'demo-post');
  }
  if (has(t, ['nima', 'qilyapsan', 'holat', 'qanday', 'gap']))
    return reply('Men hozir: ' + (a.status_label || '') + ' · ' + (a.task || '') +
                 (a.last ? '\nOxirgi amalim: ' + a.last : ''));
  if (has(t, ['nechta', 'natija', 'hisobot', 'qilding', 'bugun'])) {
    const parts = (a.metrics || []).map(m => m.label + ': ' + m.value);
    return reply('Bugungi natijalarim\n' + parts.join('\n') +
                 (a.last ? '\n\nOxirgi amalim: ' + a.last : ''));
  }
  if (has(t, ['jurnal', 'log']))
    return reply((a.last ? 'Oxirgi amalim: ' + a.last : 'Bugun hali amal bo\'lmagan') +
                 (a.metrics ? '\n' + (a.metrics || []).map(m => m.label + ': ' + m.value).join('\n') : ''));
  if (has(t, ['narx', 'qancha', 'summa', 'pul', 'hisob', 'kromka']))
    return reply(INFO.price || 'Narx: material kvadratiga 2$.');
  if (has(t, ['manzil', 'qayerda', 'xarita', 'joylashuv', 'vaqt', 'soat']))
    return reply((INFO.address || 'Manzil: 9754+W32, Toshkent') + '\nIsh vaqti: ' + (INFO.hours || ''));
  if (has(t, ['xato', 'premium', 'emoji', 'tushuna']) && key === 'suhbat')
    return reply('Men xato yozilgan savollarni tushunaman: «pryikt qanchaga chizasan» deb ' +
                 'yozilsa ham, «loyiha narxi» deb tushunaman 🙂');
  if (sleeping) return reply('Hozir dam olmoqda, ishga tushishi bilan javob beradi ⏸');
  return reply('Savolingizni to\'liq tushunmadim 🤔 Quyidagi savollardan birini sinab ko\'ring.');
}

async function sendTo(key, text) {
  text = (text || '').trim();
  if (!text) return;
  chatAdd('me', text);
  const a = AGENTS[key] || {};
  const res = await askAgent(key, text);
  chatAdd('bot', res.reply || '…', a.emoji);
  const action = res.action || '';
  if (action.indexOf('break:') === 0) {
    let type = action.split(':')[1];
    if (type === 'random') type = null;
    if (!takeBreak(key, a.name, type)) chatAdd('bot', 'Hozir dam olmoqda ⏸');
  } else if (action === 'post' || action === 'demo-post') {
    setBubble(key, '🗂 Kanalga post tashlandi');
    addEntry('🗂', '<b>' + a.name + '</b> postni kanalga tashladi');
    if (action === 'demo-post') chatAdd('bot', '<i>(namunali nusxa: kanalga yuborilmadi)</i>');
  } else if (action === 'toggle') {
    await refresh();
    chatAdd('bot', 'Holatim yangilandi ✔️');
  }
  const box = document.getElementById('chat');
  box.scrollTop = box.scrollHeight;
}

/* ---- ulash ---------------- */
document.querySelectorAll('[data-ask]').forEach(b => {
  b.addEventListener('click', ev => { ev.stopPropagation(); openChat(b.dataset.ask); });
});
document.querySelectorAll('.station').forEach(st => {
  st.querySelector('.scene').addEventListener('click', () => openChat(st.dataset.agent));
});
document.getElementById('mclose').addEventListener('click', closeChat);
document.getElementById('modal').addEventListener('click', ev => {
  if (ev.target.id === 'modal') closeChat();
});
document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape') closeChat();
  if (ev.key === 'Enter' && document.activeElement.id === 'minput') {
    const v = document.getElementById('minput').value;
    document.getElementById('minput').value = '';
    if (CURRENT) sendTo(CURRENT, v);
  }
});
document.getElementById('msend').addEventListener('click', () => {
  const el = document.getElementById('minput');
  const v = el.value; el.value = '';
  if (CURRENT) sendTo(CURRENT, v);
});
</script>
</body>
<style>
  * { box-sizing: border-box }
  body { margin:0; color:#e8eef7; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;
         background:
           radial-gradient(1100px 520px at 12% -8%, #1b2c4b 0%, transparent 60%),
           radial-gradient(900px 460px at 92% 4%, #23203f 0%, transparent 58%),
           #080e1a }
  body.night .window .sky { background:linear-gradient(180deg,#0d1b33,#1b2b4a) !important }
  body.night .scene { filter:brightness(.9) }
  .app { max-width:1180px; margin:0 auto; padding:18px 14px 60px }

  header { display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap;
           background:linear-gradient(160deg,rgba(23,36,60,.95),rgba(14,22,38,.95));
           border:1px solid #23344f; border-radius:18px; padding:14px 16px;
           box-shadow:0 18px 40px rgba(0,0,0,.35) }
  .brand { display:flex; align-items:center; gap:12px }
  .logo { width:48px; height:48px; border-radius:14px; background:linear-gradient(140deg,#f0cf7a,#b3872c);
          color:#1a1206; font-weight:800; display:flex; align-items:center; justify-content:center;
          font-size:17px; box-shadow:0 6px 16px rgba(240,207,122,.25) }
  h1 { font-size:17.5px; margin:0 } h1 span { color:#8fa6c4; font-weight:500 }
  header p { margin:3px 0 0; font-size:12.5px; color:#93aac9 }
  .headright { display:flex; align-items:center; gap:12px }
  .clock { text-align:right }
  .clock b { font-size:22px; display:block; color:#ffd97a; font-variant-numeric:tabular-nums }
  .clock span { font-size:12px; color:#8fa6c4 }
  .badge { font-size:11.5px; padding:5px 10px; border-radius:20px; background:rgba(22,36,60,.9);
           color:#9fb6d4; border:1px solid #23344f }
  .badge.live { color:#7ee0a0; border-color:#2c5f42; background:#122a1f }
  .headline { font-size:13px; color:#9fb6d4; margin:12px 4px 0 }
  .hint { font-size:12.5px; color:#bcd0e8; margin:10px 4px 0; background:rgba(24,38,62,.6);
          border:1px dashed #2c4666; border-radius:12px; padding:8px 11px }

  .stats-strip { display:flex; gap:8px; flex-wrap:wrap; margin:12px 4px 0 }
  .stat { background:rgba(20,33,55,.85); border:1px solid #24395c; border-radius:14px;
          padding:8px 12px; min-width:104px }
  .stat b { display:block; font-size:17px; color:#ffd97a }
  .stat span { font-size:11px; color:#93aac9 }
  .office { margin-top:12px }
  .stations { display:grid; grid-template-columns:1fr; gap:18px }
  @media (min-width:820px) { .stations { grid-template-columns:repeat(2,minmax(0,1fr)) } }

  /* ---------- Ish joyi (sahna) ---------- */
  .station { background:linear-gradient(170deg,rgba(20,32,52,.96),rgba(13,21,36,.96));
             border:1px solid #223350; border-radius:20px; padding:12px 12px 10px;
             position:relative; transition:transform .25s, box-shadow .25s, border-color .25s }
  .station:hover { transform:translateY(-3px); box-shadow:0 18px 38px rgba(0,0,0,.42);
                   border-color:var(--accent) }
  .station.work { border-color:color-mix(in srgb, var(--accent) 55%, #2f6a4a) }
  .station.busy { border-color:#7a5a1e }
  .scene { position:relative; height:300px; border-radius:15px; overflow:hidden; cursor:pointer;
           background:#0e1a2c; transition:filter .4s }
  .wall { position:absolute; inset:0 0 92px 0;
          background:linear-gradient(180deg,#233553,#16243b 75%,#131f33) }
  .wall:after { content:''; position:absolute; inset:0; opacity:.25;
                background-image:linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px),
                                 linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px);
                background-size:34px 34px }
  .floor { position:absolute; left:0; right:0; bottom:0; height:92px;
           background:linear-gradient(180deg,#3d2d1f,#241a12) }
  .floor:after { content:''; position:absolute; inset:0;
                 background:repeating-linear-gradient(90deg,transparent 0 28px,rgba(0,0,0,.22) 28px 30px) }

  .window { position:absolute; left:14px; top:16px; width:84px; height:60px; border-radius:9px;
            overflow:hidden; border:3px solid #0b1424; box-shadow:0 0 0 1px #2a3d5c, inset 0 0 18px rgba(0,0,0,.4) }
  .window .sky { position:absolute; inset:0; background:linear-gradient(180deg,#8ec5ff,#dbeafe) }
  .window .cloud { position:absolute; width:26px; height:9px; border-radius:6px; background:#fff;
                   opacity:.85; animation:drift 22s linear infinite }
  .window .cloud.c1 { top:14px; left:-30px }
  .window .cloud.c2 { top:34px; left:-60px; animation-duration:31s; opacity:.6 }
  .window .frame:before, .window .frame:after { content:''; position:absolute; background:#0b1424 }
  .window .frame:before { left:50%; top:0; bottom:0; width:3px; margin-left:-1.5px }
  .window .frame:after { top:50%; left:0; right:0; height:3px; margin-top:-1.5px }
  @keyframes drift { to { transform:translateX(150px) } }

  .clock-face { position:absolute; right:16px; top:16px; width:44px; height:44px; border-radius:50%;
                background:#f8fafc; border:3px solid #0b1424; display:flex; align-items:center;
                justify-content:center; box-shadow:0 2px 8px rgba(0,0,0,.45) }
  .clock-face b { font-size:10.5px; color:#0f172a; font-variant-numeric:tabular-nums }
  .wallart { position:absolute; right:72px; top:20px; width:38px; height:28px; border-radius:4px;
             background:linear-gradient(150deg,#7fb0e6 0%,#4d7bb5 55%,#2f5a91 100%);
             border:3px solid #c9a145; box-shadow:0 5px 12px rgba(0,0,0,.4) }
  .wallart:after { content:''; position:absolute; inset:0;
             background:linear-gradient(180deg,transparent 62%, rgba(255,255,255,.18) 62%) }
  .plant { position:absolute; right:12px; bottom:76px; width:26px; height:30px }
  .plant b { position:absolute; left:4px; bottom:0; width:18px; height:14px; border-radius:2px 2px 6px 6px;
             background:linear-gradient(180deg,#a8734a,#6d4a2f) }
  .plant i { position:absolute; left:11px; bottom:12px; width:4px; height:12px; background:#2f6a4a }
  .plant i:before, .plant i:after { content:''; position:absolute; width:12px; height:9px;
             background:#3f8f63; border-radius:9px 9px 2px 9px }
  .plant i:before { left:-11px; top:0 } .plant i:after { left:3px; top:-5px; border-radius:9px 9px 9px 2px }

  .corner { position:absolute; left:8px; bottom:55px; display:flex; gap:5px; z-index:8 }
  .machine { width:30px; height:30px; border-radius:9px; background:rgba(20,33,55,.95);
             border:1px solid #25395c; display:flex; align-items:center; justify-content:center;
             transition:.35s; filter:grayscale(.35) brightness(.9) }
  .machine svg { width:19px; height:19px }
  .machine.active { filter:none; border-color:#ffd97a; box-shadow:0 0 0 2px rgba(255,217,122,.25),
                    0 0 16px rgba(255,217,122,.4); transform:translateY(-3px) }

  /* stul */
  .chair { position:absolute; left:27%; bottom:66px; width:86px; height:64px; margin-left:-43px;
           background:linear-gradient(180deg,#1c2740,#101827); border-radius:14px 14px 8px 8px;
           box-shadow:inset 0 0 0 1px #26344d, 0 8px 16px rgba(0,0,0,.4); z-index:3; opacity:.92 }
  .chair:before { content:''; position:absolute; left:50%; bottom:-14px; width:6px; height:16px;
                  margin-left:-3px; background:#1c2536 }
  .chair:after { content:''; position:absolute; left:50%; bottom:-18px; width:34px; height:6px;
                 margin-left:-17px; border-radius:4px; background:#1c2536 }

  /* odam — monitor uning oldini to'smaydi */
  .human-wrap { position:absolute; left:27%; bottom:60px; width:142px; margin-left:-71px;
                transition:transform 1.05s cubic-bezier(.4,.05,.3,1), bottom 1.05s;
                z-index:5; filter:drop-shadow(0 6px 10px rgba(0,0,0,.35)) }
  .human { width:100%; height:auto; overflow:visible }
  .human .legs { opacity:0; transition:opacity .3s }
  .human .zzz, .human .hand-item { opacity:0; transition:opacity .3s }
  .human .shadow { fill:rgba(0,0,0,.35) }
  .station.sleep .human .zzz { opacity:1 }
  .station.sleep .human .head { transform:rotate(9deg); transform-origin:60px 42px }
  .station.standing .human .legs { opacity:1 }
  .station.on-break .human .hand-item { opacity:1 }

  .station.work .human .arm-l, .station.busy .human .arm-l {
    animation:typing-l .55s ease-in-out infinite alternate; transform-origin:35px 70px }
  .station.work .human .arm-r, .station.busy .human .arm-r {
    animation:typing-r .62s ease-in-out infinite alternate; transform-origin:85px 70px }
  @keyframes typing-l { from { transform:rotate(-7deg) translateY(0) } to { transform:rotate(4deg) translateY(2px) } }
  @keyframes typing-r { from { transform:rotate(6deg) translateY(1px) } to { transform:rotate(-5deg) translateY(0) } }
  .station.work .human .head { animation:nod 4.5s ease-in-out infinite }
  @keyframes nod { 0%,100% { transform:translateY(0) } 50% { transform:translateY(-1.5px) } }
  .human .eye { animation:blink 5.5s infinite }
  @keyframes blink { 0%,96%,100% { transform:scaleY(1) } 98% { transform:scaleY(.1) } }

  /* tanaffusga yurish */
  .station.on-break.coffee .human-wrap { transform:translate(-96px,-4px) scale(.9) }
  .station.on-break.water  .human-wrap { transform:translate(-58px,-4px) scale(.9) }
  .station.on-break.food   .human-wrap { transform:translate(-14px,-8px) scale(.94) }
  .station.standing .human-wrap { bottom:60px }
  .station.walking .human .legs { animation:steps .42s ease-in-out infinite alternate }
  @keyframes steps { from { transform:rotate(-5deg) } to { transform:rotate(5deg) } }
  .station.walking .human-wrap { animation:bobwalk .5s ease-in-out infinite alternate }
  @keyframes bobwalk { from { margin-bottom:0 } to { margin-bottom:6px } }
  .station.drinking .human .arm-r { animation:sip 1.1s ease-in-out infinite alternate;
                                    transform-origin:85px 70px }
  @keyframes sip { from { transform:rotate(-4deg) } to { transform:rotate(-42deg) translateY(-6px) } }
  .station.drinking .human .head { animation:siphead 1.1s ease-in-out infinite alternate }
  @keyframes siphead { from { transform:rotate(0) } to { transform:rotate(-5deg) } }

  /* stol va kompyuter — monitor yon tomonda, xodim ko'rinib turadi */
  .desk { position:absolute; left:3%; right:3%; bottom:44px; height:12px; z-index:6 }
  .desk-top { position:absolute; left:0; right:0; top:0; height:11px; border-radius:6px;
              background:linear-gradient(180deg,#d8ab77,#a87c4d); box-shadow:0 3px 8px rgba(0,0,0,.45) }
  .desk-body { position:absolute; left:5%; right:5%; top:10px; height:26px;
               background:linear-gradient(180deg,#8a6239,#66492a); border-radius:0 0 6px 6px; opacity:.92 }
  .monitor { position:absolute; right:10px; bottom:12px; width:88px; background:#0d1728;
             border:3px solid #26344f; border-radius:8px; padding:5px;
             box-shadow:0 8px 18px rgba(0,0,0,.45) }
  .screen { background:#0a1524; border-radius:5px; height:54px; padding:6px;
            display:flex; flex-direction:column; gap:5px; justify-content:center }
  .screen .row { height:4px; border-radius:3px; background:#2c4a74; animation:screenblink 1.2s infinite }
  .screen .row.r2 { width:72% } .screen .row.r3 { width:46% }
  .station.work .screen .row { background:#4f9ad9 }
  .station.busy .screen .row { background:#c39a3d }
  @keyframes screenblink { 0%,100% { opacity:.4 } 50% { opacity:1 } }
  .monitor-stand { position:absolute; right:62px; bottom:8px; width:26px; height:7px;
                   background:#26344f; border-radius:0 0 4px 4px }
  .kbd { position:absolute; left:24%; bottom:14px; width:80px; height:8px; background:#1c2536;
         border-radius:4px; box-shadow:inset 0 0 0 1px #2b3648 }
  .mouse { position:absolute; left:44%; bottom:14px; width:11px; height:16px; background:#1c2536;
           border-radius:5px }
  .cup { position:absolute; left:52%; bottom:13px; font-size:14px }
  .cup .steam { position:absolute; left:6px; top:-10px; width:5px; height:10px; border-radius:3px;
                background:linear-gradient(180deg,rgba(255,255,255,.55),transparent);
                animation:steam 2.4s ease-in-out infinite; opacity:.8 }
  @keyframes steam { 0%,100% { transform:translateY(0); opacity:.25 } 50% { transform:translateY(-5px); opacity:.8 } }

  .badge { position:absolute; left:12px; top:12px; background:rgba(9,16,28,.85); border:1px solid #23344f;
           border-radius:11px; padding:5px 9px; max-width:58%; z-index:8 }
  .badge b { display:block; font-size:12.5px } .badge span { font-size:10.5px; color:#8fa6c4 }

  .bubble { position:absolute; right:10px; top:64px; left:auto; transform:none; z-index:9; max-width:50%;
            max-height:58px; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2;
            -webkit-box-orient:vertical; font-size:11.5px; line-height:1.45;
            background:linear-gradient(150deg,#1e3a60,#152945); color:#e2f0ff; font-size:11px;
            line-height:1.45; padding:6px 10px; border-radius:11px; border:1px solid #2f4d78;
            width:47%; text-align:center; box-shadow:0 8px 18px rgba(0,0,0,.42);
            display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden }
  .bubble:after { content:''; position:absolute; bottom:-5px; left:50%; margin-left:-4px; width:8px;
                  height:8px; background:inherit; transform:rotate(45deg);
                  border-right:1px solid #2f4d78; border-bottom:1px solid #2f4d78 }

  .statusbar { position:absolute; left:10px; right:10px; bottom:9px; display:flex; align-items:center;
               gap:8px; z-index:9 }
  .taskchip { flex:1; font-size:11px; color:#cfe0f3; background:rgba(9,16,28,.82);
              border:1px solid #23344f; border-radius:9px; padding:5px 8px;
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
  .askbtn { border:0; cursor:pointer; font-size:11.5px; font-weight:600; color:#08101d;
            background:linear-gradient(140deg,var(--accent),color-mix(in srgb, var(--accent) 65%, #ffffff));
            padding:6px 11px; border-radius:9px; white-space:nowrap;
            box-shadow:0 6px 14px rgba(0,0,0,.35); transition:transform .15s }
  .askbtn:hover { transform:translateY(-1px) }

  .metrics { display:flex; gap:6px; margin-top:9px }
  .metric { flex:1; background:rgba(14,24,40,.9); border:1px solid #1e2c46; border-radius:11px;
            padding:7px 6px; text-align:center }
  .mnum { display:block; font-size:15.5px; font-weight:700; color:#ffd97a }
  .mlabel { font-size:10px; color:#8fa6c4 }

  /* ---------- Panellar ---------- */
  .cols { display:flex; gap:16px; flex-wrap:wrap; margin-top:16px }
  .panel { flex:1 1 330px; min-width:290px; background:linear-gradient(170deg,rgba(20,32,52,.94),rgba(13,21,36,.94));
           border:1px solid #1e2c46; border-radius:18px; padding:14px 16px }
  .panel.wide { margin-top:16px; flex:1 1 100% }
  .panel h2 { font-size:14.5px; margin:0 0 10px }
  .log { max-height:300px; overflow:auto; display:flex; flex-direction:column; gap:6px }
  .entry { display:flex; gap:8px; align-items:flex-start; font-size:12.5px; color:#cfe0f3;
           background:rgba(14,24,40,.85); border:1px solid #1b2942; border-radius:10px; padding:6px 9px }
  .entry b { color:#7fb2e8; font-variant-numeric:tabular-nums }
  .entry .em { font-size:14px }
  .entry.new { animation:flash 1.6s ease-out }
  @keyframes flash { from { background:#1d3557 } to { background:rgba(14,24,40,.85) } }
  .entry.empty { color:#7d92ad }
  .slots { display:flex; flex-direction:column; gap:5px; margin-bottom:10px }
  .slot { display:flex; align-items:center; gap:8px; font-size:12.5px; background:rgba(14,24,40,.85);
          border:1px solid #1b2942; border-radius:10px; padding:6px 9px }
  .slot b { color:#7fb2e8; width:44px } .slot span { flex:1; color:#cfe0f3 }
  .slot.done { border-color:#2c5f42 }
  .posts-head { font-size:12px; color:#8fa6c4; margin:8px 0 6px }
  .post { font-size:12.5px; color:#cfe0f3; background:rgba(14,24,40,.85); border:1px solid #1b2942;
          border-radius:10px; padding:6px 9px; margin-bottom:5px }
  .post b { color:#7fb2e8; margin-right:6px } .post.empty { color:#7d92ad }
  .kanal-stats { display:flex; gap:8px; margin-top:10px }
  .kanal-stats div { flex:1; background:rgba(14,24,40,.85); border:1px solid #1b2942; border-radius:11px;
                     padding:7px; text-align:center }
  .kanal-stats b { display:block; font-size:16px; color:#ffd97a }
  .kanal-stats span { font-size:10.5px; color:#8fa6c4 }
  .duties { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px }
  .duty { background:rgba(14,24,40,.85); border:1px solid #1b2942; border-radius:13px; padding:10px 12px }
  .duty b { font-size:13.5px } .duty p { margin:6px 0 0; font-size:12.5px; color:#a9c0dc; line-height:1.55 }
  .duty-task { display:block; margin-top:7px; font-size:11.5px; color:#7fb2e8 }
  .note { font-size:12px; color:#8fa6c4; margin:12px 0 0 }

  /* ---------- Suhbat oynasi ---------- */
  .modal { position:fixed; inset:0; background:rgba(4,8,16,.72); backdrop-filter:blur(6px);
           display:flex; align-items:center; justify-content:center; padding:16px; z-index:50 }
  .modal[hidden] { display:none }
  .modal-card { --accent:#3b82f6; width:100%; max-width:520px; max-height:92vh; overflow:auto;
                background:linear-gradient(170deg,#16233a,#0d1526); border:1px solid #26375a;
                border-radius:20px; padding:14px 16px 16px;
                box-shadow:0 30px 70px rgba(0,0,0,.6); animation:pop .28s ease-out }
  @keyframes pop { from { transform:translateY(14px) scale(.98); opacity:0 } to { transform:none; opacity:1 } }
  .mhead { display:flex; align-items:center; gap:11px }
  .mavatar { width:42px; height:42px; border-radius:13px; display:flex; align-items:center;
             justify-content:center; font-size:20px; background:var(--accent);
             box-shadow:0 6px 16px rgba(0,0,0,.35) }
  .mtitle { flex:1 } .mtitle b { display:block; font-size:15px }
  .mtitle span { font-size:11.5px; color:#8fa6c4 }
  .mstatus { font-size:11.5px; color:#bcd0e8; background:rgba(14,24,40,.9); border:1px solid #26375a;
             border-radius:20px; padding:4px 9px }
  .mclose { border:0; background:transparent; color:#8fa6c4; font-size:16px; cursor:pointer; padding:4px 6px }
  .mclose:hover { color:#fff }
  .mduty { font-size:12.5px; color:#a9c0dc; line-height:1.6; margin:10px 0; background:rgba(14,24,40,.7);
           border:1px solid #1e2c46; border-radius:11px; padding:8px 10px }
  .mstats { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px }
  .pill { font-size:11px; color:#cfe0f3; background:rgba(14,24,40,.9); border:1px solid #26375a;
          border-radius:20px; padding:4px 9px }
  .chat { display:flex; flex-direction:column; gap:8px; max-height:270px; overflow:auto;
          padding:10px; background:rgba(8,14,26,.7); border:1px solid #1b2942; border-radius:14px }
  .cmsg { display:flex; gap:8px; align-items:flex-end }
  .cmsg.me { flex-direction:row-reverse }
  .cav { width:26px; height:26px; border-radius:9px; background:var(--accent); display:flex;
         align-items:center; justify-content:center; font-size:14px; flex:0 0 auto }
  .cbub { max-width:78%; font-size:12.8px; line-height:1.55; padding:8px 11px; border-radius:13px;
          background:#1b2942; color:#e4eefb; border:1px solid #27395a }
  .cmsg.me .cbub { background:linear-gradient(140deg,var(--accent),color-mix(in srgb, var(--accent) 60%, #000));
                   color:#fff; border-color:transparent }
  .cmsg.bot .cbub b { color:#ffd97a }
  .chips { display:flex; flex-wrap:wrap; gap:6px; margin:10px 0 }
  .chip { border:1px solid #2b3f63; background:rgba(19,30,50,.9); color:#cfe0f3; font-size:11.5px;
          padding:5px 10px; border-radius:20px; cursor:pointer; transition:.2s }
  .chip:hover { border-color:var(--accent); color:#fff; transform:translateY(-1px) }
  .inputrow { display:flex; gap:8px }
  .inputrow input { flex:1; background:#0c1729; border:1px solid #26375a; color:#e8eef7;
                    border-radius:11px; padding:10px 12px; font-size:13px; font-family:inherit }
  .inputrow input:focus { outline:none; border-color:var(--accent) }
  .inputrow button { border:0; cursor:pointer; font-weight:600; color:#08101d; padding:0 16px;
                     border-radius:11px; font-size:13px;
                     background:linear-gradient(140deg,var(--accent),color-mix(in srgb, var(--accent) 65%, #fff)) }
  .mnote { font-size:11.5px; color:#8fa6c4; margin:9px 0 0 }
  .mnote input { background:#0c1729; border:1px solid #26375a; color:#e8eef7; border-radius:8px;
                 padding:5px 8px; font-size:12px }
  .mnote button { background:var(--accent); border:0; border-radius:8px; padding:5px 10px;
                  font-size:12px; cursor:pointer; color:#08101d; font-weight:600 }

  @media (max-width:440px) {
    .scene { height:262px } .human-wrap { width:112px; margin-left:-56px; left:30% }
    .bubble { max-width:50% } .askbtn { font-size:11px; padding:5px 8px }
  }
</style>
</html>
"""
