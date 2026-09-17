#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_scheduler.py
---------------------
Telegram kanalga kunlik jadval bo'yicha avtomatik post yuboradi.

Jadval (config.json da o'zgartiriladi):
    09:00  — ofis ochildi + yaxshi tilaklar      (har kuni)
    10:00  — Juma tabrigi                       (faqat juma kunlari)
    12:00  — reklama/hizmat posti               (har kuni)
    15:00  — reklama/hizmat posti               (har kuni)
    18:00  — ish vaqti tugadi + samimiy tilaklar (har kuni)

Qo'shimcha kutubxona kerak emas — faqat Python 3.8+.

Ishga tushirish:
    python3 telegram_scheduler.py               # doimiy ishlaydi (server/kompyuter uchun)
    python3 telegram_scheduler.py --due         # hozir "vaqti kelgan" slotlarni yuboradi (GitHub Actions)
    python3 telegram_scheduler.py --time 09:00  # bitta slotni majburan yuborish
    python3 telegram_scheduler.py --test        # sinov posti
    python3 telegram_scheduler.py --dry-run     # yubormasdan ko'rsatadi
    python3 telegram_scheduler.py --status      # bugungi holat: nima yuborilgan, nima kutilmoqda
"""

import json
import os
import sys
import time
import logging
import re
import datetime as dt
from zoneinfo import ZoneInfo
import urllib.request  # faqat AI rejimi uchun

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOG_PATH = os.path.join(BASE_DIR, "sender.log")

API_BASE = os.environ.get("TG_API_BASE", "https://api.telegram.org")

# GitHub Actions uchun: cron kechikishi mumkin, shu sababli slot vaqti o'tgandan keyin
# shu daqiqalar ichida ham yuboriladi.
DUE_GRACE_MINUTES = 70
# Vaqt tezdan boshlangan bo'lsa (bir necha sekund), shuncha oldin ham yuborilsin
EARLY_TOLERANCE_SEC = 120
# Lokal rejimda har necha sekundda tekshiriladi
CHECK_EVERY = 20

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("scheduler")


# --------------------------------------------------------------------------
# Sozlamalar va holat
# --------------------------------------------------------------------------
def load_config():
    if not os.path.exists(CONFIG_PATH):
        log.error("config.json topilmadi! config.example.json dan nusxa olib to'ldiring.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    # GitHub Actions / Render uchun: maxfiy qiymatlar muhit o'zgaruvchisidan ham olinadi
    if os.environ.get("BOT_TOKEN"):
        cfg["bot_token"] = os.environ["BOT_TOKEN"].strip()
    if os.environ.get("CHANNEL"):
        cfg["channel"] = os.environ["CHANNEL"].strip()
    if "PUT_YOUR" in cfg.get("bot_token", "PUT_YOUR") or not cfg.get("bot_token"):
        log.error("config.json ichida bot_token to'ldirilmagan (@BotFather dan olinadi).")
        sys.exit(1)
    if not cfg.get("channel"):
        log.error('config.json ichida "channel" to\'ldirilmagan (masalan "@mening_kanalim").')
        sys.exit(1)
    cfg.setdefault("timezone", "Asia/Tashkent")
    return cfg


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sent": {}, "rotate_index": 0}


def save_state(state):
    cutoff = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    state["sent"] = {k: v for k, v in state["sent"].items() if k[:10] >= cutoff}
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


# Telegram API bilan ishlash tg_api.py modulida — bot_manager.py ham shundan foydalanadi
from tg_api import (  # noqa: E402
    api_json, split_text, send_message, send_message_rich, send_photo_rich,
    build_custom_emoji_entities, TELEGRAM_LIMIT,  # noqa: F401
)

import random
import calendar


# --------------------------------------------------------------------------
# Kontent
# --------------------------------------------------------------------------
def load_content(path):
    """Kontent faylini post bloklariga bo'ladi. Bloklar '---' qatori bilan ajratiladi.

    Blok ichida birinchi qatorlar shunday bo'lishi mumkin:
        #photo: images/rasm.jpg
        Post matni...
    """
    full = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
    if not os.path.exists(full):
        log.warning("Kontent fayli topilmadi: %s", full)
        return []
    with open(full, encoding="utf-8") as f:
        raw = f.read()

    posts = []
    for block in raw.split("\n---"):
        block = block.strip()
        if not block:
            continue
        photo, lines = None, []
        for line in block.splitlines():
            if line.strip().lower().startswith("#photo:"):
                photo = line.split(":", 1)[1].strip()
            else:
                lines.append(line)
        text = "\n".join(lines).strip()
        if text or photo:
            posts.append({"text": text, "photo": photo})
    return posts


def slots_with_same_content(cfg, slot):
    """Bir xil kontent faylidan foydalanadigan slotlar ro'yxati (navbat hisobi uchun)."""
    path = slot.get("content_file", cfg.get("content_file", "content.txt"))
    return [s for s in cfg.get("slots", [])
            if s.get("content_file", cfg.get("content_file", "content.txt")) == path
            and s.get("mode", "rotate") == "rotate"]


def pick_content(cfg, slot, state, day=None):
    """Slot kontent faylidan navbatdagi postni oladi (kunma-kun siljib boradi)."""
    path = slot.get("content_file", cfg.get("content_file", "content.txt"))
    posts = load_content(path)
    if not posts:
        return None
    day = day or dt.date.today()
    group = slots_with_same_content(cfg, slot)
    try:
        pos = group.index(slot)
    except ValueError:
        pos = 0
    idx = (day.toordinal() * max(len(group), 1) + pos) % len(posts)
    state["rotate_index"] = idx
    return posts[idx]


def build_post(cfg, slot, state, day=None):
    mode = slot.get("mode", "rotate")
    if mode == "fixed":
        return {"text": slot.get("text", ""), "photo": slot.get("photo")}
    if mode == "ai":
        return ai_generate(cfg, slot, state)

    item = pick_content(cfg, slot, state, day=day)
    if not item:
        return {"text": slot.get("fallback", "Post matni hali kiritilmagan."), "photo": None}
    if slot.get("prefix"):
        item = {"text": slot["prefix"] + "\n\n" + item["text"], "photo": item.get("photo")}
    return item


def ai_generate(cfg, slot, state):
    """AI (OpenAI-mos API) orqali har kuni yangi post yozadi."""
    ai = cfg.get("ai") or {}
    key = ai.get("api_key", "")
    if not key or "PUT_YOUR" in key:
        log.warning("AI sozlanmagan — kontent faylidan olinadi.")
        return pick_content(cfg, slot, state) or {"text": "", "photo": None}

    prompt = ai.get("prompt", "Kanal uchun qisqa, foydali va qiziqarli post yoz.")
    if slot.get("topic"):
        prompt += f"\nMavzu: {slot['topic']}"
    payload = {
        "model": ai.get("model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": ai.get("system", "Sen o'zbek tilida yozadigan SMM mutaxassisisan.")},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
    }
    url = ai.get("base_url", "https://api.openai.com/v1") + "/chat/completions"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            answer = json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
        return {"text": answer, "photo": None}
    except Exception as e:
        log.error("AI xatosi: %s — kontent faylidan olinadi.", e)
        return pick_content(cfg, slot, state) or {"text": "", "photo": None}



# --------------------------------------------------------------------------
# VARIATOR — postlar bir xil bo'lib qolmasligi uchun
# --------------------------------------------------------------------------
# 3 xil imkoniyat:
#   1) Dinamik tokenlar:  {kun} {sana} {vaqt} {narx} {narx10} {aloqa}
#   2) Nomlangan to'plamlar (config.json -> variator):  {salom} {cta} {tip} {yakun}
#   3) Spintax:  {Xayrli tong|Assalomu alaykum|Xayrli kun}
# Har safar boshqa variant tanlanadi — ketma-ket bir xil takrorlanmaydi.

WEEKDAY_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


def _pick(options, key, state, rnd):
    """Variantlar ichidan tanlaydi, o'tgan safargi bilan bir xil bo'lmasin."""
    options = [o.strip() for o in options if o.strip()]
    if not options:
        return ""
    history = state.setdefault("spin", {})
    last = history.get(key)
    choices = [o for o in options if o != last] or options
    choice = rnd.choice(choices)
    history[key] = choice
    return choice


def dynamic_tokens(cfg, now=None):
    now = now or dt.datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tashkent")))
    price = (cfg.get("bot", {}) or {}).get("price_per_sqm", 2)
    contact = (cfg.get("bot", {}) or {}).get("username", "@abkmebel")
    return {
        "kun": WEEKDAY_UZ[now.weekday()],
        "sana": now.strftime("%d.%m.%Y"),
        "vaqt": now.strftime("%H:%M"),
        "narx": f"{price}$",
        "narx10": f"{price * 10}$",
        "aloqa": contact,
        "oy": calendar.month_name[now.month],
    }


def spin(text, cfg, state, rnd=None, now=None):
    """Matnni 'jonli' qiladi: tokenlar, to'plamlar va spintax almashtiriladi."""
    if not text:
        return text
    rnd = rnd or random.Random()
    pools = (cfg.get("variator", {}) or {}).get("pools", {}) or {}
    tokens = dynamic_tokens(cfg, now)
    tokens.update({k: v for k, v in pools.items() if isinstance(v, str)})

    # 1) Dinamik tokenlar ({kun}, {sana}, {narx}...) va nomlangan to'plamlar ({salom}, {cta}...)
    #    Spintax ichida ham ishlatilishi mumkin: {Yoki shu {aloqa} ga yozing|...}
    for name, options in pools.items():
        if isinstance(options, list) and f"{{{name}}}" in text:
            text = text.replace(f"{{{name}}}", _pick(options, f"pool:{name}", state, rnd))
    for name, value in tokens.items():
        text = text.replace(f"{{{name}}}", str(value))

    # 1b) Ixtiyoriy qatorlar: {?tip} — 70% ehtimol bilan qo'shiladi, aks holda o'chiriladi.
    #     Bu postlarning kombinatsiyasini bir necha barobar ko'paytiradi.
    change = float((cfg.get("variator", {}) or {}).get("optional_chance", 0.7))

    def optional_repl(m):
        name = m.group(1)
        options = pools.get(name)
        if not isinstance(options, list) or rnd.random() > change:
            return ""
        return _pick(options, f"pool:{name}", state, rnd)

    def line_optional_repl(m):
        # qatorda faqat {?token} bo'lsa — tanlanmasa qator butunlay olib tashlanadi
        value = optional_repl(m)
        return (value + "\n") if value else ""

    text = re.sub(r"^[ \t]*\{\?([a-zA-Z_]+)\}[ \t]*\n?", line_optional_repl, text, flags=re.M)
    text = re.sub(r"\{\?([a-zA-Z_]+)\}", optional_repl, text)

    # 2) Spintax: {a|b|c} — ichma-ich variantlar bo'lsa, bir necha marta ishlanadi
    def repl(m):
        options = m.group(1).split("|")
        return _pick(options, f"spin:{abs(hash(m.group(1))) % 0xFFFFFF}", state, rnd)

    for _ in range(5):
        new_text = re.sub(r"\{([^{}]*\|[^{}]*)\}", repl, text)
        if new_text == text:
            break
        text = new_text
    return text


def spin_photo(photo, cfg, state, rnd=None):
    """Rasm yo'li ham to'plamdan bo'lishi mumkin: '#photo: {rasm}'."""
    if not photo or "{" not in photo:
        return photo
    pools = (cfg.get("variator", {}) or {}).get("pools", {}) or {}
    m = re.fullmatch(r"\{([a-zA-Z_]+)\}", photo.strip())
    if m and isinstance(pools.get(m.group(1)), list):
        return _pick(pools[m.group(1)], f"pool:{m.group(1)}", state, rnd or random.Random())
    return photo


def apply_premium(text, cfg):
    """Premium emoji entity'larini yasaydi (yoqilgan bo'lsa)."""
    b = cfg.get("bot", {}) or {}
    if not b.get("premium_emojis_enabled", True):
        return []
    emap = b.get("premium_emojis") or {}
    return build_custom_emoji_entities(text, emap)

# --------------------------------------------------------------------------
# Vaqt va kun tekshiruvi
# --------------------------------------------------------------------------
def slot_allowed_on(slot, day):
    """Slot 'days' sozlamasiga qarab shu kuni yuborilishi kerakmi."""
    days = slot.get("days")
    if not days or days == "*" or (isinstance(days, list) and ("*" in days or not days)):
        return True
    wanted = {str(d).lower()[:3] for d in days}
    return WEEKDAYS[day.weekday()] in wanted


def slot_key(slot, now, position):
    label = slot.get("label") or slot.get("time") or str(position)
    return f"{now.date().isoformat()} {slot.get('time')} {label}"


def slot_datetime(slot, now):
    h, m = [int(x) for x in str(slot.get("time", "")).split(":")]
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


# --------------------------------------------------------------------------
# Yuborish
# --------------------------------------------------------------------------
def deliver(cfg, slot, state, dry_run=False, rnd=None):
    post = build_post(cfg, slot, state, day=dt.datetime.now(
        ZoneInfo(cfg.get("timezone", "Asia/Tashkent"))).date())
    rnd = rnd or random.Random()
    text = spin((post.get("text") or "").strip(), cfg, state, rnd)
    photo = spin_photo(post.get("photo"), cfg, state, rnd)
    title = f"{slot.get('time')} {slot.get('label', '')}".strip()

    if dry_run:
        log.info("[DRY-RUN] %s -> %s\n%s", title, cfg["channel"], text or "(faqat rasm)")
        return True
    if not text and not photo:
        log.warning("%s: post bo'sh, yuborilmadi.", title)
        return False

    entities = apply_premium(text, cfg)
    if photo:
        result = send_photo_rich(cfg["bot_token"], cfg["channel"], photo, text,
                                 entities=entities, base_dir=BASE_DIR)
    else:
        result = send_message_rich(cfg["bot_token"], cfg["channel"], text, entities=entities)

    if result.get("ok"):
        log.info("✅ %s — post yuborildi (%s).", title, cfg["channel"])
        return True
    log.error("❌ %s — yuborilmadi: %s", title, result.get("description"))
    return False


def run_due(cfg, grace_minutes=DUE_GRACE_MINUTES, dry_run=False):
    """Vaqti kelgan (yoki o'tib ketgan) slotlarni yuboradi. GitHub Actions shuni chaqiradi."""
    tz = ZoneInfo(cfg.get("timezone", "Asia/Tashkent"))
    now = dt.datetime.now(tz)
    state = load_state()
    sent = skipped = 0

    log.info("Tekshiruv: %s (%s), slotlar: %d ta",
             now.strftime("%Y-%m-%d %H:%M"), WEEKDAYS[now.weekday()], len(cfg.get("slots", [])))

    for i, slot in enumerate(cfg.get("slots", [])):
        if not slot.get("time"):
            continue
        if not slot_allowed_on(slot, now.date()):
            log.info("• %s %s — bugun emas (faqat: %s)", slot["time"], slot.get("label", ""),
                     ", ".join(slot.get("days", [])))
            continue

        key = slot_key(slot, now, i)
        if state["sent"].get(key):
            log.info("• %s %s — allaqachon yuborilgan.", slot["time"], slot.get("label", ""))
            continue

        delta = (now - slot_datetime(slot, now)).total_seconds()
        if delta < -EARLY_TOLERANCE_SEC:
            log.info("• %s %s — vaqti hali kelmagan (%d daqiqa oldin).",
                     slot["time"], slot.get("label", ""), int(-delta // 60))
            skipped += 1
            continue
        if delta > grace_minutes * 60:
            log.info("• %s %s — o'tkazib yuborilgan (%d daqiqa o'tgan).",
                     slot["time"], slot.get("label", ""), int(delta // 60))
            continue

        if deliver(cfg, slot, state, dry_run=dry_run):
            if not dry_run:
                state["sent"][key] = now.isoformat(timespec="seconds")
                save_state(state)
            sent += 1

    log.info("Natija: %d ta yuborildi, %d ta hali kutilmoqda.", sent, skipped)
    return sent


def preview_posts(cfg, count=5):
    """Keyingi postlar qanday ko'rinishini ko'rsatadi (variator ishlaydi)."""
    state = load_state()
    rnd = random.Random()
    slots = cfg.get("slots", [])
    day = dt.date.today()
    printed = 0
    print(f"\n📮 Keyingi {count} ta post (Toshkent vaqti, variator yoqilgan):\n" + "=" * 70)
    while printed < count:
        for slot in slots:
            days = slot.get("days")
            if days and days != "*" and WEEKDAYS[day.weekday()] not in [str(d).lower()[:3] for d in days]:
                continue
            post = build_post(cfg, slot, state, day=day)
            text = spin((post.get("text") or "").strip(), cfg, state, rnd)
            photo = spin_photo(post.get("photo"), cfg, state, rnd)
            printed += 1
            print(f"\n[{printed}] {day.strftime('%d.%m')} {slot.get('time')} — {slot.get('label','')}"
                  f"{'  🖼 ' + str(photo) if photo else ''}")
            print("-" * 70)
            print(text[:700] + ("…" if len(text) > 700 else ""))
            if printed >= count:
                break
        day += dt.timedelta(days=1)
    print("\n" + "=" * 70)
    save_state(state)


def count_combinations(text, pools):
    """Bitta post necha xil ko'rinishda chiqishi mumkin (kombinatorika)."""
    total = 1
    for m in re.finditer(r"\{([^{}]*\|[^{}]*)\}", text):
        total *= max(len([o for o in m.group(1).split("|") if o.strip()]), 1)
    for name, options in (pools or {}).items():
        if isinstance(options, list) and f"{{{name}}}" in text:
            total *= max(len(options), 1)
        if isinstance(options, list) and f"{{?{name}}}" in text:
            total *= max(len(options) + 1, 1)   # +1: umuman qo'shilmasligi
    return total


def variety_check(cfg, samples=60):
    """Bir xillik tekshiruvi: muhimi — ketma-ket va bir sikl ichida takror bo'lmasin."""
    state = load_state()
    rnd = random.Random(2026)
    slots = [s for s in cfg.get("slots", []) if s.get("mode", "rotate") == "rotate"]
    day = dt.date.today()
    texts = []
    while len(texts) < samples:
        for slot in slots:
            days = slot.get("days")
            if days and days != "*" and WEEKDAYS[day.weekday()] not in [str(d).lower()[:3] for d in days]:
                continue
            post = build_post(cfg, slot, state, day=day)
            texts.append(spin((post.get("text") or "").strip(), cfg, state, rnd))
            if len(texts) >= samples:
                break
        day += dt.timedelta(days=1)

    n = len(texts)
    consecutive = sum(1 for a, b in zip(texts, texts[1:]) if a == b)
    # bir xil postlar orasidagi eng qisqa masofa
    last_seen, min_gap = {}, None
    for i, t in enumerate(texts):
        if t in last_seen:
            gap = i - last_seen[t]
            min_gap = gap if min_gap is None else min(min_gap, gap)
        last_seen[t] = i
    cycle = len([s for s in slots if not s.get("days")])
    window = max(cycle, 1) * 3
    dup_in_window = sum(1 for i in range(n) for j in range(i + 1, min(i + window, n))
                        if texts[i] == texts[j])

    pools = (cfg.get("variator", {}) or {}).get("pools", {})
    files = sorted({s.get("content_file", "content.txt") for s in cfg.get("slots", [])})
    combos = {}
    for f in files:
        posts = load_content(f)
        combos[f] = sum(count_combinations(p["text"], pools) for p in posts)

    print(f"\n🔁 BIR XILLIK TEKSHIRUVI ({n} ta post ketma-ket)\n" + "-" * 52)
    print(f"Ketma-ket aynan bir xil post:          {consecutive} ta  {'✅' if consecutive == 0 else '❌'}")
    print(f"Bir xil postlar orasi (min):           {min_gap if min_gap else '—'} ta post "
          f"{'✅' if not min_gap or min_gap >= cycle else '⚠️'}")
    print(f"Yaqin oraliqda (3 sikl) takror:         {dup_in_window} ta  "
          f"{'✅' if dup_in_window == 0 else '⚠️'}")
    print(f"Birinchi qatorlari xilma-xil:          {len(set(t.split(chr(10))[0] for t in texts))} / {n}")
    print("\n🧬 HAR BIR POSTNING KOMBINATSIYALARI (bitta matndan necha xil ko'rinish chiqadi):")
    for f, c in combos.items():
        print(f"   {f:<22} ~{c:,} xil variant".replace(",", " "))
    total_combos = sum(combos.values())
    print(f"   {'JAMI':<22} ~{total_combos:,} xil variant".replace(",", " "))
    print("\nℹ️  Navbat tizimi: postlar ketma-ket takrorlanmaydi, to'liq sikl esa "
          f"{cycle} ta postdan iborat (~{max(cycle // 2, 1)} kun).")
    if consecutive == 0 and dup_in_window == 0:
        print("✅ Postlar bir xil bo'lib qolmaydi — har safar yangi ko'rinishda chiqadi.")
    else:
        print("⚠️  content fayllariga yana variant qo'shish tavsiya etiladi.")
    print()
    save_state(state)
    return consecutive, dup_in_window


def send_slot_now(cfg, wanted_time, state=None):
    """Bitta slotni vaqtidan qat'i nazar majburan yuboradi (qo'lda sinov uchun)."""
    state = state or load_state()
    now = dt.datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Tashkent")))
    for i, slot in enumerate(cfg.get("slots", [])):
        if str(slot.get("time")) == wanted_time:
            ok = deliver(cfg, slot, state)
            state["sent"][slot_key(slot, now, i)] = now.isoformat(timespec="seconds")
            save_state(state)
            return ok
    print(f"'{wanted_time}' vaqti config.json dagi slotlar orasida topilmadi.")
    return False


def show_status(cfg):
    tz = ZoneInfo(cfg.get("timezone", "Asia/Tashkent"))
    now = dt.datetime.now(tz)
    state = load_state()
    print(f"\n⏰ Hozir: {now.strftime('%Y-%m-%d %H:%M')} ({WEEKDAYS[now.weekday()]}) — {cfg.get('timezone')}")
    print(f"📢 Kanal: {cfg['channel']}\n")
    print(f"{'Vaqt':<7} {'Nomi':<24} {'Kunlar':<12} {'Kontent fayli':<22} Holat")
    print("-" * 95)
    for i, slot in enumerate(cfg.get("slots", [])):
        path = slot.get("content_file", cfg.get("content_file", "content.txt"))
        days = "har kuni" if not slot.get("days") else ",".join(slot["days"])
        key = slot_key(slot, now, i)
        if state["sent"].get(key):
            status = "✅ bugun yuborilgan"
        elif now >= slot_datetime(slot, now):
            status = "⏳ vaqti o'tgan"
        else:
            status = "🕐 kutilmoqda"
        if not slot_allowed_on(slot, now.date()):
            status += " (bugun bu kun emas)"
        print(f"{slot.get('time',''):<7} {slot.get('label',''):<24} {days:<12} {path:<22} {status}")
    print()


# --------------------------------------------------------------------------
# Lokal doimiy rejim
# --------------------------------------------------------------------------
def run_forever(cfg):
    tz = ZoneInfo(cfg.get("timezone", "Asia/Tashkent"))
    log.info("Ishga tushdi. Kanal: %s | Vaqt mintaqasi: %s", cfg["channel"], cfg.get("timezone"))
    for s in cfg.get("slots", []):
        days = "har kuni" if not s.get("days") else ",".join(s["days"])
        log.info("  • %s — %s (%s)", s.get("time"), s.get("label", ""), days)

    while True:
        run_due(cfg, grace_minutes=5)
        time.sleep(CHECK_EVERY)


def main():
    cfg = load_config()
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return
    if "--status" in args:
        show_status(cfg)
        return
    if "--preview" in args:
        n = int(args[args.index("--preview") + 1]) if len(args) > args.index("--preview") + 1 else 5
        preview_posts(cfg, n)
        return
    if "--variety" in args:
        variety_check(cfg)
        return
    if "--due" in args:
        run_due(cfg)
        return
    if "--dry-run" in args:
        run_due(cfg, dry_run=True)
        return
    if "--test" in args:
        slot = cfg["slots"][0]
        post = build_post(cfg, slot, load_state())
        ok = deliver(cfg, {"time": "test", "label": "SINOV"}, load_state())
        print("Sinov posti yuborildi." if ok else "Yuborilmadi — sender.log ni ko'ring.")
        return
    if "--time" in args:
        wanted = args[args.index("--time") + 1]
        ok = send_slot_now(cfg, wanted)
        print("Yuborildi ✅" if ok else "Yuborilmadi — sender.log ni ko'ring.")
        return

    try:
        run_forever(cfg)
    except KeyboardInterrupt:
        log.info("To'xtatildi (Ctrl+C).")


if __name__ == "__main__":
    main()
