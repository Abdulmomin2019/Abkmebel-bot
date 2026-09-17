#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_manager.py — "ABK MEBEL AI-ofis": 3 ta AI-xodim + menejer bot.

🏢 AI-XODIMLAR (har birining o'z vazifasi bor)
  🗂  Reklama agenti (postchi)  — kanalga post tashlaydi, jadvalni yuritadi, kanalni kuzatadi
  💬  Sotuv agenti (menejer)   — mijoz bilan suhbat, narx hisoblash, dalolatnoma bo'yicha anketa, buyurtma
  🏢  Ofis administratori      — manzil va ish vaqti, FAQ, savol-javoblar, hisobotlar, eslatmalar

IMKONIYATLARI
  Mijozlar: menyu, narxlar, namunalar, FastReport, narx kalkulyatori,
            ko'p so'raladigan savollar, 📍 manzil (xarita tugmalari bilan),
            6 qadamli buyurtma anketasi (dalolatnoma asosida), fayl/rasm yuborish
  Siz: /ofis — AI-ofis jonli holati, /agents — xodimlar va vazifalari,
       /agent off menejer — xodimni to'xtatish, /post — kanalga post tashlash,
       /stats /orders /reply /mark /broadcast /report /log
  Kanal: izohlardagi reklama-havolalarni o'chirish, yangi a'zoni kutib olish,
         postlar jadvali va kanaldagi oxirgi postlarni kuzatish
  Ilova: GET /ofis — Telegram ichida ochiladigan AI-ofis ilovasi (jonli yangilanadi)

ISHGA TUSHIRISH
  python3 bot_manager.py --poll            # doimiy (server/kompyuter)
  python3 bot_manager.py --once            # bir marta (cron uchun)
  python3 bot_manager.py --webhook         # webhook + /ofis ilovasi (Render)
  python3 bot_manager.py --report          # hisobotni hozir yuborish
  python3 bot_manager.py --office          # AI-ofis ma'lumotini JSON ko'rinishida chiqarish
  python3 bot_manager.py --status          # sozlamalar va statistika
"""

import datetime as dt
import difflib
import hashlib
import hmac
import json
import logging
import os
import random
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tg_api import (  # noqa: E402
    get_chat_member, get_chat,
    api_json, get_updates, answer_callback_query,
    edit_message_text, delete_message, get_chat_member_count, get_me,
    set_webhook, delete_webhook, get_webhook_info, forward_message, ALL_UPDATES,
    set_menu_button,
    send_message_rich, send_photo_rich, build_custom_emoji_entities, extract_custom_emojis,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
try:      # deploy paketida matn va rasmlar kod ichida keladi
    import assets as _deploy_assets
    _deploy_assets.ensure(BASE_DIR)
except ImportError:
    pass

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
BOT_ID = int(os.environ.get("BOT_ID") or 0)   # get_me() orqali aniqlanadi
USERS_PATH = os.path.join(DATA_DIR, "users.json")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")
BOT_STATE_PATH = os.path.join(DATA_DIR, "bot_state.json")
OFFICE_LOG_PATH = os.path.join(DATA_DIR, "office_log.json")
LOG_PATH = os.path.join(BASE_DIR, "bot.log")

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_UZ = {"mon": "Dushanba", "tue": "Seshanba", "wed": "Chorshanba", "thu": "Payshanba",
              "fri": "Juma", "sat": "Shanba", "sun": "Yakshanba"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("bot")

CONFIG = {}
TOKEN = ""
USERNAME = "@abkmebel"
# https manzil (Render'da avtomatik beriladi; sinovda OFFICE_URL orqali)
PUBLIC_URL = (os.environ.get("OFFICE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
CHANNEL_CACHE = {"at": 0, "data": None}

AGENT_EMOJI = {"postchi": "🗂", "menejer": "💬", "ofis": "🏢", "suhbat": "🗣"}


# --------------------------------------------------------------------------
# Fayllar
# --------------------------------------------------------------------------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_config(require_token=True):
    if not os.path.exists(CONFIG_PATH):
        log.error("config.json topilmadi!")
        sys.exit(1)
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    token = os.environ.get("BOT_TOKEN") or cfg.get("bot_token", "")
    admin = os.environ.get("ADMIN_ID") or (cfg.get("bot", {}) or {}).get("admin_id") or ""
    try:
        admin = int(str(admin).strip()) if str(admin).strip() else None
    except ValueError:
        admin = None
    if require_token and (not token or "PUT_YOUR" in token):
        log.error("bot_token topilmadi (config.json yoki BOT_TOKEN muhit o'zgaruvchisi).")
        sys.exit(1)
    cfg["bot_token"] = token or "TEST"
    cfg["channel"] = os.environ.get("CHANNEL") or cfg.get("channel", "")
    cfg.setdefault("bot", {})["admin_id"] = admin
    return cfg


def init(cfg=None, token=None):
    """Modulning global sozlamalarini o'rnatadi (test va oflayn yasash uchun ham)."""
    global CONFIG, TOKEN, USERNAME
    CONFIG = cfg or load_config()
    TOKEN = token or CONFIG.get("bot_token", "")
    USERNAME = (CONFIG.get("bot", {}) or {}).get("username") or "@abkmebel"
    return CONFIG


def bot_cfg():
    b = CONFIG.setdefault("bot", {})
    b.setdefault("admin_id", None)
    b.setdefault("price_per_sqm", 2)
    b.setdefault("work_hours", {"from": "09:00", "to": "18:00", "days": "*"})
    b.setdefault("daily_report", "18:30")
    b.setdefault("weekly_report", {"day": "fri", "time": "18:35"})
    b.setdefault("portfolio", [])
    b.setdefault("faq", [])
    b.setdefault("keywords", [])
    b.setdefault("address", {})
    b.setdefault("agents", {})
    b.setdefault("order_steps", DEFAULT_ORDER_STEPS)
    b.setdefault("welcome_new_members", False)
    b.setdefault("spam_filter", {"enabled": True,
                                 "patterns": ["http://", "https://", "t.me/", "joinchat"]})
    return b


DEFAULT_ORDER_STEPS = [
    {"key": "name", "q": "1/6 — <b>Ismingiz va familiyangiz?</b>", "required": True},
    {"key": "phone", "q": "2/6 — <b>Telefon raqamingiz?</b> (yoki @username)", "required": True},
    {"key": "furniture",
     "q": "3/6 — <b>Qanday mebel kerak va bo'linishlari?</b>\nMasalan: oshxona, 3 ta yuqori shkaf, "
          "2 ta tortma, idish yuvish mashinasi uchun joy", "required": True},
    {"key": "sizes",
     "q": "4/6 — <b>Gabarit o'lchamlar:</b> umumiy bo'y, eni, chuqurligi (yoki xona o'lchami — "
          "zamer natijasi)", "required": True},
    {"key": "material",
     "q": "5/6 — <b>Material va furnitura:</b> LDSP/MDF turi, rangi, qalinligi, kromka rangi, "
          "mexanizmlar (Blum va h.k.)", "required": False},
    {"key": "deadline", "q": "6/6 — <b>Muddat:</b> qachonga tayyor bo'lishi kerak?", "required": False},
]


def agent_cfg(key):
    """AI-xodim sozlamalari (nomi, vazifasi, yoniq/o'chiq)."""
    defaults = {
        "postchi": {"emoji": "🗂", "name": "Reklama agenti",
                    "role": "kanalga post va jadval",
                    "duty": "Kanalga postlarni jadval bo'yicha tashlaydi, kontent navbatini yuritadi, "
                            "kanaldagi oxirgi postlarni kuzatib boradi."},
        "menejer": {"emoji": "💬", "name": "Sotuv agenti",
                    "role": "mijoz bilan suhbat va buyurtma",
                    "duty": "Mijoz savollariga javob beradi, narxni hisoblab beradi, dalolatnoma "
                            "bo'yicha kerakli ma'lumotlarni so'raydi va buyurtmani qabul qiladi."},
        "ofis": {"emoji": "🏢", "name": "Ofis administratori",
                 "role": "manzil, FAQ va hisobotlar",
                 "duty": "Manzil va ish vaqti ma'lumotini beradi, ko'p so'raladigan savollarga javob "
                         "yozadi, kunlik/haftalik hisobotni tayyorlaydi, mijozlarga eslatma yuboradi."},
        "suhbat": {"emoji": "🗣", "name": "Suhbat agenti",
                   "role": "shaxsiy xabarlar va samimiy muloqot",
                   "duty": "Shaxsiy xabarlarni birinchi bo'lib kutib oladi: xato va imloviy xatolar "
                           "bilan yozilgan savollarni ham tushunadi («proyikt qanchaga chizasan»), "
                           "samimiy va jonli javob beradi, kerak bo'lsa to'g'ri bo'limga yo'naltiradi "
                           "va murakkab savollarni adminga uzatadi."},
    }
    cfg = dict(defaults.get(key, {}))
    cfg.update(bot_cfg().get("agents", {}).get(key, {}))
    cfg.setdefault("enabled", True)
    cfg["key"] = key
    return cfg


def agent_on(key):
    return bool(agent_cfg(key).get("enabled", True))


# --------------------------------------------------------------------------
# Holat, foydalanuvchilar, buyurtmalar, jurnal
# --------------------------------------------------------------------------
def state():
    return load_json(BOT_STATE_PATH, {"offset": 0, "flows": {}, "reports": {}, "days": {}})


def save_state(st):
    save_json(BOT_STATE_PATH, st)


def users():
    return load_json(USERS_PATH, {})


def save_users(u):
    save_json(USERS_PATH, u)


def orders():
    return load_json(ORDERS_PATH, [])


def save_orders(o):
    save_json(ORDERS_PATH, o)


def touch_day(day_key, field, amount=1):
    st = state()
    day = st.setdefault("days", {}).setdefault(day_key, {})
    day[field] = day.get(field, 0) + amount
    save_state(st)


def now_tz():
    return dt.datetime.now(ZoneInfo(CONFIG.get("timezone", "Asia/Tashkent")))


# --- AI-ofis jurnali -------------------------------------------------------
def office_log():
    return load_json(OFFICE_LOG_PATH, {"entries": []}).get("entries", [])


def log_action(agent, action, detail="", chat_id=None, emoji=None):
    """AI-xodim nima ish qilganini jurnalga yozadi (ofisda ko'rinadi)."""
    entries = office_log()
    entries.append({
        "ts": now_tz().isoformat(timespec="seconds"),
        "agent": agent,
        "emoji": emoji or AGENT_EMOJI.get(agent, "•"),
        "action": action,
        "detail": (detail or "")[:300],
        "chat_id": str(chat_id) if chat_id else None,
    })
    save_json(OFFICE_LOG_PATH, {"entries": entries[-800:]})


def today_log(agent=None):
    today = now_tz().date().isoformat()
    items = [e for e in office_log() if e["ts"][:10] == today]
    return [e for e in items if e["agent"] == agent] if agent else items


# --------------------------------------------------------------------------
# Ish vaqti va manzil
# --------------------------------------------------------------------------
def is_work_time(now=None):
    now = now or now_tz()
    wh = bot_cfg()["work_hours"]
    days = wh.get("days", "*")
    if days and days != "*":
        if WEEKDAYS[now.weekday()] not in [str(d).lower()[:3] for d in days]:
            return False
    try:
        h, m = [int(x) for x in wh.get("from", "09:00").split(":")]
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        h, m = [int(x) for x in wh.get("to", "18:00").split(":")]
        end = now.replace(hour=h, minute=m, second=0, microsecond=0)
    except ValueError:
        return True
    return start <= now <= end


def hours_text():
    wh = bot_cfg()["work_hours"]
    a = bot_cfg().get("address", {})
    if a.get("hours_text"):
        return a["hours_text"]
    days = wh.get("days", "*")
    days_uz = "har kuni" if days == "*" else ", ".join(
        WEEKDAY_UZ.get(str(d).lower()[:3], d) for d in days)
    return f"{wh.get('from')} – {wh.get('to')} ({days_uz})"


def after_hours_note():
    return (f"🕘 Hozir ish vaqtidan tashqari ({hours_text()}). "
            f"Xabaringiz adminga yuborildi — ish vaqti boshlanishi bilan javob beramiz.")


def address_text():
    a = bot_cfg().get("address", {})
    lines = ["📍 <b>Bizning manzil</b>", ""]
    if a.get("name"):
        lines.append(f"🏢 {a['name']}")
    if a.get("text"):
        lines.append(f"📍 {a['text']}")
    if a.get("plus_code"):
        lines.append(f"🧭 Plus Code: <code>{a['plus_code']}</code> (Google Maps'ga kiriting)")
    if a.get("landmark"):
        lines.append(f"🚩 Mo'ljal: {a['landmark']}")
    lines.append(f"🕘 Ish vaqti: <b>{hours_text()}</b>")
    if a.get("transport"):
        lines.append(f"🚌 {a['transport']}")
    lines.append("")
    lines.append("🗺 Xaritada ochish uchun quyidagi tugmani bosing yoki shu havoladan foydalaning:")
    if a.get("maps_url"):
        lines.append(a["maps_url"])
    lines.append("")
    lines.append(f"✍️ Kelishdan oldin {USERNAME} ga yozib qo'ysangiz — darhol xizmat ko'rsatamiz.")
    return "\n".join(lines)


def address_keyboard():
    a = bot_cfg().get("address", {})
    rows = []
    if a.get("maps_url"):
        rows.append([{"text": "🗺 Xaritada ochish", "url": a["maps_url"]}])
    if a.get("route_url"):
        rows.append([{"text": "🚕 Marshrut (yo'l ko'rsatish)", "url": a["route_url"]}])
    if a.get("phone"):
        rows.append([{"text": f"📞 {a['phone']}", "url": f"tel:{a['phone'].replace(' ', '')}"}])
    rows.append([{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}])
    return {"inline_keyboard": rows}


# --------------------------------------------------------------------------
# Menyu va matnlar
# --------------------------------------------------------------------------
def menu_keyboard():
    return {"inline_keyboard": [
        [{"text": "📋 Narxlar va xizmatlar", "callback_data": "menu:price"},
         {"text": "🧮 Narx kalkulyatori", "callback_data": "menu:calc"}],
        [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"},
         {"text": "📍 Manzil va ish vaqti", "callback_data": "menu:address"}],
        [{"text": "⚙️ FastReport shablon/script", "callback_data": "menu:fastreport"},
         {"text": "🖼 Namuna loyihalar", "callback_data": "menu:portfolio"}],
        [{"text": "❓ Ko'p so'raladigan savollar", "callback_data": "menu:faq"},
         {"text": "📞 Aloqa", "callback_data": "menu:contact"}],
    ]}


def back_keyboard():
    return {"inline_keyboard": [[{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}]]}


def client_keyboard():
    """Pastdagi doimiy tugmalar (mijoz botga kirishi bilan ko'rinadi)."""
    return {"keyboard": [
        [{"text": "📋 Narxlar"}, {"text": "🧮 Kalkulyator"}],
        [{"text": "✍️ Buyurtma berish"}, {"text": "📍 Manzil"}],
        [{"text": "⚙️ FastReport"}, {"text": "🖼 Namunalar"}],
        [{"text": "❓ Savollar"}, {"text": "👤 Profil"}],
    ], "resize_keyboard": True, "is_persistent": True}


CLIENT_BUTTONS = {
    "📋 narxlar": "menu:price", "🧮 kalkulyator": "menu:calc",
    "✍️ buyurtma berish": "menu:order", "📍 manzil": "menu:address",
    "⚙️ fastreport": "menu:fastreport", "🖼 namunalar": "menu:portfolio",
    "❓ savollar": "menu:faq", "👤 profil": "menu:profile",
    "🏢 ai-ofis": "menu:ofis",
}


def app_button_row():
    """Mini App (ilova) tugmasi — BotFather uslubidagi ilova."""
    if PUBLIC_URL.startswith("https://"):
        return [{"text": "📱 Ilovani ochish", "web_app": {"url": PUBLIC_URL.rstrip("/") + "/app"}}]
    return None


def office_button_row():
    """AI-ofis ilovasini ochish tugmasi (https manzil bo'lsa)."""
    if PUBLIC_URL.startswith("https://"):
        return [{"text": "🏢 AI-ofisni ochish (jonli)", "web_app": {"url": PUBLIC_URL.rstrip("/") + "/ofis"}}]
    if PUBLIC_URL:
        return [{"text": "🏢 AI-ofisni ochish", "url": PUBLIC_URL.rstrip("/") + "/ofis"}]
    return None


def menu_text(name=""):
    salute = f"Assalomu alaykum, {name}!" if name else "Assalomu alaykum!"
    return (f"🏢 <b>ABK MEBEL — BAZIS loyiha va FastReport xizmatlari</b>\n\n"
            f"{salute} 👋\nKerakli bo'limni tanlang:\n\n"
            f"⏰ Ish vaqti: <b>{hours_text()}</b>\n"
            f"📩 Aloqa: {USERNAME}")


def price_text():
    p = bot_cfg()["price_per_sqm"]
    return (f"📋 <b>Narxlar</b>\n\n"
            f"🗂 <b>BAZIS-Mebel loyihasi</b> (3D ko'rinish + detallar + to'liq smeta)\n"
            f"   • material kvadratiga — <b>{p}$</b>\n"
            f"   • 10 m² loyiha ≈ {p*10}$\n"
            f"   • kromka, furnitura va material hisobi narxga kiradi\n\n"
            f"⚙️ <b>FastReport shablon va scriptlar</b>\n"
            f"   • narx ish hajmiga qarab kelishiladi\n"
            f"   • o'rnatish va sozlashda yordam beramiz\n\n"
            f"🧮 Aniq summani kalkulyatorda hisoblab ko'ring 👇")


def fastreport_text():
    return ("⚙️ <b>FastReport shablon va scriptlar</b>\n\n"
            "• Smeta, spetsifikatsiya va hisobotlarni <b>bir tugma bilan</b> chiqaradi\n"
            "• Material, kromka va furnitura hisobini avtomatlashtiradi\n"
            "• Sizning ish uslubingizga moslab yozib beriladi\n"
            "• BAZIS'ga ulash va sozlashda yordam beramiz\n\n"
            "💰 Narx: ish hajmiga qarab kelishiladi.\n"
            f"Namuna va aniq taklif uchun yozing: {USERNAME}")


def contact_text():
    a = bot_cfg().get("address", {})
    lines = ["📞 <b>Aloqa</b>", "", f"• Telegram: {USERNAME}"]
    if a.get("phone"):
        lines.append(f"• Telefon: {a['phone']}")
    lines.append(f"• Ish vaqti: {hours_text()}")
    if a.get("plus_code"):
        lines.append(f"• Manzil: {a.get('text') or a['plus_code']}")
    lines += ["", "✍️ Savolingizni shu chatga yozib qoldiring — adminga darhol yuboriladi."]
    return "\n".join(lines)


def faq_list_text():
    faq = bot_cfg()["faq"]
    if not faq:
        return "Savollar ro'yxati hali to'ldirilmagan."
    lines = ["❓ <b>Ko'p so'raladigan savollar</b>\n"]
    lines += [f"{i}. {item['q']}" for i, item in enumerate(faq, 1)]
    lines.append("\nJavobni ko'rish uchun savolni bosing 👇")
    return "\n".join(lines)


def faq_keyboard():
    rows = [[{"text": f"{i}. {item['q'][:40]}", "callback_data": f"faq:{i-1}"}]
            for i, item in enumerate(bot_cfg()["faq"])]
    rows.append([{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}])
    return {"inline_keyboard": rows}


def calc_result_text(area):
    p = bot_cfg()["price_per_sqm"]
    return (f"🧮 <b>Hisob-kitob</b>\n\n"
            f"📐 Material maydoni: <b>{area:g} m²</b>\n"
            f"💰 Narx: {p}$ × {area:g} m² = <b>{area*p:g}$</b>\n\n"
            f"Bu taxminiy narx — aniq summa o'lchamlar aniqlangach aytiladi.\n"
            f"Loyihani boshlash uchun «✍️ Buyurtma berish» tugmasini bosing.")


def order_step_text(step):
    total = len(bot_cfg()["order_steps"])
    hint = "\n\n<i>O'tkazib yuborish uchun /skip · Bekor qilish uchun /bekor</i>" if not step["required"] \
        else "\n\n<i>Bekor qilish uchun /bekor</i>"
    return f"✍️ <b>Buyurtma anketasi</b> ({total} qadam)\n\n{step['q']}{hint}"


def dalolatnoma_text(order):
    """Dalolatnoma (shartnoma ilovasi) loyihasi — order ma'lumotlaridan to'ldiriladi."""
    return (
        f"📄 <b>DALOLATNOMA LOYIHASI — buyurtma #{order['id']}</b>\n"
        f"<i>(«Loyihani tasdiqlash va qabul qilish dalolatnomasi» asosida)</i>\n\n"
        f"Sana: {order['created'][:10]} | Buyurtma №: {order['id']}\n\n"
        f"<b>1. TOMONLAR</b>\n"
        f"Loyihachi: «ABK FURNITURE STUDIO» (ABK MEBEL)\n"
        f"Buyurtmachi: {order.get('name','')}\n"
        f"Telefon: {order.get('phone','')}\n\n"
        f"<b>2. BUYURTMA ASOSI VA TALABLAR</b>\n"
        f"• Mebel turi va bo'linishlari: {order.get('furniture','—')}\n"
        f"• Gabarit va aniq o'lchamlar: {order.get('sizes','—')}\n"
        f"• Material va furnituralar: {order.get('material','—')}\n"
        f"• Muddat: {order.get('deadline','—')}\n\n"
        f"<b>3. IZOHLAR</b>\n"
        f"Chizma BAZIS-Mebel dasturida tayyorlanadi. Buyurtmachi chizma va o'lchamlarni\n"
        f"tekshirib tasdiqlagach, ishlab chiqarishga o'tiladi (prisyadka sxemasi bilan).\n"
        f"Fayllar/eskiz/loyiha rasmi mijozdan qabul qilinadi.\n\n"
        f"Buyurtmachi imzosi: ____________     Loyihachi imzosi: ____________\n"
        f"<i>Yevgeniy / ABK FURNITURE STUDIO</i>")



# --------------------------------------------------------------------------
# SUHBAT AGENTI: xato yozilgan, samimiy (adabiy bo'lmagan) savollarni tushunish
# --------------------------------------------------------------------------
def normalize(text, return_fixes=False):
    """Matnni solishtirish uchun tozalaydi va xato so'zlarni to'g'rilaydi.

    return_fixes=True bo'lsa: (natija, [(xato, to'g'ri), ...]) qaytaradi.
    """
    fixes = []
    if not text:
        return ("", fixes) if return_fixes else ""
    t = text.lower().replace("ё", "е").replace("’", "'").replace("`", "'")
    t = re.sub(r"[^\w\s'\u0400-\u04FF]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()

    repl = (bot_cfg().get("fuzzy") or {}).get("replacements", {}) or {}
    for w in ("tanaffus", "kofe", "suv", "ovqat", "tushlik", "post", "tashla", "yubor",
              "to'xta", "toxta", "ishla", "davom", "hisobot", "jurnal", "salom", "rahmat"):
        repl.setdefault(w, w)
    KNOWN_WORDS = set(repl.keys()) | set(repl.values())
    words = []
    for w in t.split():
        if w in repl:
            words.append(repl[w])
            if w != repl[w]:
                fixes.append((w, repl[w]))
            continue
        # takrorlangan harflarni qisqartirish — faqat xavfsiz holatlarda:
        #   "qanchaaa" -> "qancha" (3+ takror), "salooom" -> "salom",
        #   lekin "tanaffus", "katta" kabi to'g'ri so'zlar buzilmaydi.
        squashed = re.sub(r"(.)\1+", r"\1", w)
        long_run = re.search(r"(.)\1{2,}", w) is not None
        if squashed != w and (long_run or squashed in KNOWN_WORDS or w not in KNOWN_WORDS):
            fixes.append((w, squashed))
        if squashed in repl:
            words.append(repl[squashed])
            if squashed != repl[squashed]:
                fixes.append((squashed, repl[squashed]))
            continue
        # yaqin so'zni topish (imlo xatolari): "fastreportt", "kromkaa"
        if len(w) >= 4:
            close = difflib.get_close_matches(w, list(repl.keys()) + [k for k in repl.values()], n=1, cutoff=0.86)
            if close:
                cand = close[0]
                fixed = repl.get(cand, cand)
                if fixed != w:
                    fixes.append((w, fixed))
                words.append(fixed)
                continue
        words.append(squashed if len(squashed) >= 4 else w)
    result = " ".join(words)
    return (result, fixes) if return_fixes else result


def text_matches(keyword, text, norm):
    """Kalit so'z matnda bormi: to'g'ridan-to'g'ri, normalizatsiya yoki yaqinlik orqali."""
    kw = keyword.lower()
    # Qisqa so'zlar ("hi", "uz") faqat alohida so'z sifatida hisobga olinadi —
    # aks holda "c-hi-zasan" ichidan "hi" topilib qolar edi.
    if len(kw) <= 3:
        return re.search(r"(?<![\w'])" + re.escape(kw) + r"(?![\w'])", text.lower()) is not None
    if kw in text.lower():
        return True
    kw_norm = normalize(kw)
    if kw_norm and kw_norm in norm:
        return True
    if len(kw_norm) >= 4 and norm:
        for w in norm.split():
            if len(w) >= 4 and difflib.SequenceMatcher(None, kw_norm, w).ratio() >= 0.85:
                return True
    return False


def has_word(norm, words):
    """So'z boshi bo'yicha mos kelishni tekshiradi.

    Muhim: "chizasan" ichidan "hi" yoki "hisobi" ichidan "hi" topilmasligi kerak,
    shu sababli qisqa so'zlar (<=3 harf) faqat butun so'z sifatida sanaladi.
    """
    for w in words:
        w = w.lower()
        pat = r"(?<![\w'])" + re.escape(w)
        if len(w) <= 3:
            pat += r"(?![\w'])"
        if re.search(pat, norm):
            return True
    return False


def is_greeting(norm):
    return has_word(norm, ("salom", "assalom", "xayrli", "hayrli", "hello", "hi", "privet"))


def is_thanks(norm):
    return has_word(norm, ("rahmat", "tashakkur", "spasibo", "thank"))


def is_bye(norm):
    return has_word(norm, ("xayr", "ko'rishguncha", "xayrlashuv", "bye", "pokа"))


def looks_like_question(text, norm):
    if "?" in text:
        return True
    q_words = ("qancha", "qanday", "qachon", "qanaqa", "necha", "bormi", "kerak", "mumkin",
               "mumkinmi", "narx", "chiz", "loyiha", "bazis", "buyurtma", "olaman", "kerakmi",
               "ishlaysizmi", "qayerda", "manzil")
    return has_word(norm, q_words)


def suhbat_pick(pool_name, name=""):
    pool = (bot_cfg().get("suhbat") or {}).get(pool_name) or []
    if not pool:
        return ""
    text = random.choice(pool)
    return text.replace("{ism}", (name or "").strip() or "do'stim").replace("{narx}", f"{bot_cfg()['price_per_sqm']}$") \
               .replace("{narx10}", f"{bot_cfg()['price_per_sqm'] * 10}$")


def suhbat_reply(text, norm, name=""):
    """Suhbat agenti javobini tanlaydi. Qaytaradi: (javob, klaviatura, izoh, turi)"""
    if is_greeting(norm) and len(norm.split()) <= 4:
        return suhbat_pick("greetings", name), menu_keyboard(), "suhbat", "salom"
    if is_thanks(norm):
        return suhbat_pick("thanks", name), back_keyboard(), "suhbat", "rahmat"
    if is_bye(norm):
        return suhbat_pick("bye", name), None, "suhbat", "xayr"
    # Narx/loyiha haqida so'ralayotgan bo'lsa (xato yozilgan bo'lsa ham)
    price_words = ("narx", "chiz", "loyiha", "bazis", "qancha", "summa", "hisob", "pul", "kromka")
    if has_word(norm, price_words):
        return suhbat_pick("price_hint", name), {"inline_keyboard": [
            [{"text": "🧮 Narx kalkulyatori", "callback_data": "menu:calc"},
             {"text": "📋 Narxlar", "callback_data": "menu:price"}],
            [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"}]]}, "suhbat", "narx"
    if has_word(norm, ("yaxshi", "zo'r", "rahmat", "ishlaysanmi", "charchamadingizmi",
                       "qalaysiz", "nima", "qandaysiz")):
        return suhbat_pick("smalltalk", name), back_keyboard(), "suhbat", "suhbat"
    if looks_like_question(text, norm):
        return suhbat_pick("unclear", name), {"inline_keyboard": [
            [{"text": "📋 Narxlar", "callback_data": "menu:price"},
             {"text": "📍 Manzil", "callback_data": "menu:address"}],
            [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"},
             {"text": "❓ Savollar", "callback_data": "menu:faq"}]]}, "suhbat", "savol"
    return suhbat_pick("unclear", name), menu_keyboard(), "suhbat", "tushunarsiz"


# --------------------------------------------------------------------------
# PREMIUM EMOJI (bot egasida Premium bo'lsa ishlaydi)
# --------------------------------------------------------------------------
def reply(chat_id, text, reply_markup=None, premium=True, reply_to=None):
    """Bot javobini premium emojilar bilan yuboradi (o'rganilgan bo'lsa)."""
    entities = None
    if premium and bot_cfg().get("premium_emojis_enabled", True):
        emap = {k: v for k, v in (bot_cfg().get("premium_emojis") or {}).items()
                if not k.startswith("_")}
        entities = build_custom_emoji_entities(text, emap) or None
    return send_message_rich(TOKEN, chat_id, text, entities=entities, reply_markup=reply_markup,
                             reply_to=reply_to)


def reply_photo(chat_id, photo, caption="", reply_markup=None):
    emap = {k: v for k, v in (bot_cfg().get("premium_emojis") or {}).items() if not k.startswith("_")}
    entities = build_custom_emoji_entities(caption, emap) or None
    return send_photo_rich(TOKEN, chat_id, photo, caption, entities=entities,
                           reply_markup=reply_markup, base_dir=BASE_DIR)


def learn_premium_emoji(msg, chat_id):
    """Admin premium emoji yuborsa — bot uni o'rganib, sozlamaga yozadi."""
    found = extract_custom_emojis(msg)
    if not found:
        return False
    b = bot_cfg()
    store = b.setdefault("premium_emojis", {})
    added = {k: v for k, v in found.items() if store.get(k) != v}
    store.update(found)
    save_json(CONFIG_PATH, CONFIG)

    lines = ["✅ <b>Premium emoji o'rganildi!</b>", ""]
    for emo, eid in found.items():
        lines.append(f"{emo} → <code>{eid}</code>")
    lines += ["", f"Jami o'rganilgan premium emoji: <b>{len([k for k in store if not k.startswith('_')])}</b> ta.",
              "", "Endi bot shu emojilarni javoblarida ishlatadi. "
                  "Kanaldagi postlarga qo'shish uchun <code>config.json</code> → "
                  "<code>bot.premium_emojis</code> ichidan ID ni oling." if added else
                  "Bu emojilar allaqachon ma'lum edi."]
    reply(chat_id, "\n".join(lines), premium=False)
    log_action("ofis", "premium emoji o'rganildi", f"{len(found)} ta: {' '.join(found.keys())}")
    return True

# --------------------------------------------------------------------------
# Admin, foydalanuvchilar
# --------------------------------------------------------------------------
def register_user(user, is_bot=False):
    if is_bot or not user:
        return
    uid = str(user["id"])
    u = users()
    today = now_tz().date().isoformat()
    if uid not in u:
        u[uid] = {"first_name": user.get("first_name", ""), "username": user.get("username", ""),
                  "joined": today, "last_seen": today}
        touch_day(today, "new_users")
        log.info("Yangi foydalanuvchi: %s (id=%s)", u[uid]["first_name"], uid)
    else:
        u[uid]["last_seen"] = today
    save_users(u)


def admin_id():
    return bot_cfg().get("admin_id")


def notify_admin(text):
    aid = admin_id()
    if not aid:
        log.warning("ADMIN_ID sozlanmagan — xabar: %s", text[:200])
        return False
    return reply(aid, text).get("ok", False)


# --------------------------------------------------------------------------
# Kanalni kuzatish (ochiq kanal sahifasidan)
# --------------------------------------------------------------------------
def channel_recent_posts(limit=6, cache_seconds=60):
    """Kanaldagi oxirgi postlarni o'qiydi (ochiq kanal sahifasidan). Xato bo'lsa []."""
    name = str(CONFIG.get("channel", "")).lstrip("@").strip()
    if not name or os.environ.get("TG_API_BASE"):
        return []          # sinovda va oflayn rejimda tashqi so'rov qilmaymiz
    if time.time() - CHANNEL_CACHE["at"] < cache_seconds and CHANNEL_CACHE["data"] is not None:
        return CHANNEL_CACHE["data"]
    posts = []
    try:
        req = urllib.request.Request(f"https://t.me/s/{name}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", "ignore")
        times = re.findall(r'<time datetime="([^"]+)"', html)
        texts = re.findall(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.S)
        for i, iso in enumerate(times[-limit:]):
            try:
                when = dt.datetime.fromisoformat(iso).astimezone(ZoneInfo(CONFIG.get("timezone", "Asia/Tashkent")))
            except Exception:
                continue
            text = ""
            if len(texts) >= len(times) - limit + 0:
                idx = len(texts) - (len(times) - times.index(iso)) if iso in times else -1
                try:
                    text = re.sub(r"<[^>]+>", " ", texts[idx]).strip()
                except Exception:
                    text = ""
            if not text and i < len(texts):
                text = re.sub(r"<[^>]+>", " ", texts[i if len(times) == len(texts) else -1]).strip()
            posts.append({"time": when.strftime("%d.%m %H:%M"), "text": (text[:110] or "(rasm/post)")})
    except Exception as e:
        log.info("Kanal postlarini olish imkoni bo'lmadi: %s", e)
        posts = []
    CHANNEL_CACHE.update({"at": time.time(), "data": posts})
    return posts


# --------------------------------------------------------------------------
# AI-OFIS: xodimlar holati va ma'lumotlar
# --------------------------------------------------------------------------
def _sent_today_times():
    """Bugun qaysi slotlar yuborilgani (scheduler state.json dan, bo'lsa)."""
    st = load_json(os.path.join(BASE_DIR, "state.json"), {"sent": {}})
    today = now_tz().date().isoformat()
    return {k.split(" ", 1)[1].split(" ")[0] for k in st.get("sent", {}) if k.startswith(today)}


def _next_slot(now=None):
    now = now or now_tz()
    sent = _sent_today_times()
    today_key = WEEKDAYS[now.weekday()]
    for s in CONFIG.get("slots", []):
        days = s.get("days")
        if days and days != "*" and today_key not in [str(d).lower()[:3] for d in days]:
            continue
        if str(s.get("time")) in sent:
            continue
        try:
            h, m = [int(x) for x in str(s["time"]).split(":")]
        except Exception:
            continue
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target >= now:
            return s, target
    return None, None


def build_office_data(with_channel=True):
    """AI-ofis uchun to'liq ma'lumot (bot ham, HTML ilova ham shundan foydalanadi)."""
    now = now_tz()
    bot_cfg()
    today = now.date().isoformat()
    log_entries = today_log()
    all_orders = orders()
    merged_orders = [o for o in all_orders if o["created"][:10] >= (now.date() - dt.timedelta(days=30)).isoformat()]
    pending = [o for o in all_orders if o.get("status") == "yangi"]

    def count(agent, actions):
        return len([e for e in log_entries if e["agent"] == agent and e["action"] in actions])

    def clients_today():
        ids = {e.get("chat_id") for e in log_entries
               if e["agent"] == "menejer" and e.get("chat_id") and e["action"] in ("xabar", "savol")}
        return len(ids)

    def last_entry(agent):
        items = [e for e in log_entries if e["agent"] == agent]
        return items[-1] if items else None

    # --- 🗂 Reklama agenti ---
    posts_today = len(_sent_today_times())
    chan_posts = channel_recent_posts() if with_channel else []
    chan_today = len([p for p in chan_posts if p["time"].startswith(now.strftime("%d.%m"))])
    next_slot, next_time = _next_slot(now)
    if next_slot:
        mins = int((next_time - now).total_seconds() // 60)
        post_task = f"Keyingi post: {next_slot['time']} «{next_slot.get('label','')}» ({mins} daqiqadan so'ng)"
        post_status = "ishlayapti" if mins <= 90 else "bosh"
    else:
        post_task = "Bugungi postlar yakunlandi — ertaga 09:00 da davom etadi"
        post_status = "bosh"
    if not agent_on("postchi"):
        post_status, post_task = "dam", "To'xtatilgan (/agent on postchi bilan yoqiladi)"
    le = last_entry("postchi")
    agents = [{
        "key": "postchi", "emoji": "🗂", "name": agent_cfg("postchi")["name"],
        "role": agent_cfg("postchi")["role"], "duty": agent_cfg("postchi")["duty"],
        "status_key": post_status,
        "status_label": {"ishlayapti": "🟢 post tashlamoqda", "bosh": "💤 navbatda",
                         "dam": "⏸ to'xtatilgan"}.get(post_status, "💤"),
        "task": post_task,
        "metrics": [
            {"key": "posts", "label": "post (bugun)", "value": posts_today or chan_today},
            {"key": "chan", "label": "kanalda (bugun)", "value": chan_today},
            {"key": "next", "label": "keyingi", "value": next_slot["time"] if next_slot else "—"},
        ],
        "last": (f"{le['ts'][11:16]} — {le['action']}" if le else None),
    }]

    # --- 💬 Sotuv agenti ---
    calcs = count("menejer", {"hisob"})
    orders_today = count("menejer", {"buyurtma"})
    clients = clients_today()
    flows = state().get("flows", {})
    if not agent_on("menejer"):
        sal_status, sal_task = "dam", "To'xtatilgan (/agent on menejer)"
    elif flows:
        sal_status = "band"
        sal_task = f"Mijoz bilan anketada: {len(flows)} ta suhbat faol"
    else:
        sal_status, sal_task = "ishlayapti", "Yangi mijozlarni kutmoqda — savollarga javob beradi"
    le = last_entry("menejer")
    agents.append({
        "key": "menejer", "emoji": "💬", "name": agent_cfg("menejer")["name"],
        "role": agent_cfg("menejer")["role"], "duty": agent_cfg("menejer")["duty"],
        "status_key": sal_status,
        "status_label": {"band": "🟡 mijoz bilan band", "ishlayapti": "🟢 ishga tayyor",
                         "dam": "⏸ to'xtatilgan"}.get(sal_status, "🟢"),
        "task": sal_task,
        "metrics": [
            {"key": "clients", "label": "mijoz (bugun)", "value": clients},
            {"key": "calc", "label": "hisob-kitob", "value": calcs},
            {"key": "orders", "label": "buyurtma", "value": orders_today},
        ],
        "last": (f"{le['ts'][11:16]} — {le['action']}" if le else None),
    })

    # --- 🏢 Ofis administratori ---
    answers = count("ofis", {"javob", "manzil", "faq"})
    reports = count("ofis", {"hisobot"})
    if not agent_on("ofis"):
        adm_status, adm_task = "dam", "To'xtatilgan (/agent on ofis)"
    elif not is_work_time(now):
        adm_status = "dam"
        adm_task = f"Ish vaqtidan tashqari ({hours_text()}) — savollarni yig'ib turadi"
    else:
        adm_status, adm_task = "ishlayapti", "Manzil, savol-javob va hisobotlar bilan shug'ullanmoqda"
    le = last_entry("ofis")
    agents.append({
        "key": "ofis", "emoji": "🏢", "name": agent_cfg("ofis")["name"],
        "role": agent_cfg("ofis")["role"], "duty": agent_cfg("ofis")["duty"],
        "status_key": adm_status,
        "status_label": {"ishlayapti": "🟢 ishlamoqda", "dam": "💤 dam olmoqda"}.get(adm_status, "🟢"),
        "task": adm_task,
        "metrics": [
            {"key": "answers", "label": "javob (bugun)", "value": answers},
            {"key": "reports", "label": "hisobot", "value": reports},
            {"key": "pending", "label": "javob kutayotgan", "value": len(pending)},
        ],
        "last": (f"{le['ts'][11:16]} — {le['action']}" if le else None),
    })

    # --- 🗣 Suhbat agenti (shaxsiy xabarlar) ---
    said_hi = count("suhbat", {"salomlashdi", "samimiy suhbat qurdi", "minnatdorchilikni qabul qildi",
                               "xayrlashdi"})
    understood = count("suhbat", {"xato yozilgan savolni tushundi"})
    escalated = count("suhbat", {"savolni tushunmadi — aniqlashtirdi", "tushunmadi — menyu taklif qildi"})
    unique_clients = len({e.get("chat_id") for e in log_entries
                          if e["agent"] == "suhbat" and e.get("chat_id")})
    if not agent_on("suhbat"):
        suh_status, suh_task = "dam", "To'xtatilgan (/agent on suhbat)"
    elif not is_work_time(now):
        suh_status = "dam"
        suh_task = "Ish vaqtidan tashqari — xabarlarni yig'ib turadi"
    elif escalated:
        suh_status = "band"
        suh_task = f"{escalated} ta savolni aniqlashtirmoqda, tushunarsiz xabarlar bilan ishlayapti"
    else:
        suh_status = "ishlayapti"
        suh_task = "Shaxsiy xabarlarni kutmoqda — xato yozilgan savollarni ham tushunadi"
    le = last_entry("suhbat")
    agents.append({
        "key": "suhbat", "emoji": "🗣", "name": agent_cfg("suhbat")["name"],
        "role": agent_cfg("suhbat")["role"], "duty": agent_cfg("suhbat")["duty"],
        "status_key": suh_status,
        "status_label": {"ishlayapti": "🟢 muloqotga tayyor", "band": "🟡 savolni aniqlashtirmoqda",
                         "dam": "💤 dam olmoqda"}.get(suh_status, "🟢"),
        "task": suh_task,
        "metrics": [
            {"key": "clients", "label": "mijoz (bugun)", "value": unique_clients},
            {"key": "understood", "label": "tushunilgan savol", "value": understood},
            {"key": "escalated", "label": "adminga uzatilgan", "value": escalated},
        ],
        "last": (f"{le['ts'][11:16]} — {le['action']}" if le else None),
    })

    for _a in agents:
        _a["asks"] = APP_ASKS.get(_a["key"], APP_ASKS["ofis"])

    working = len([a for a in agents if a["status_key"] in ("ishlayapti", "band")])
    headline = (f"{now.strftime('%H:%M')} holatiga ko'ra {working} ta AI-xodim ishlamoqda. "
                f"Bugun {posts_today or chan_today} ta post, {clients} ta mijoz, "
                f"{orders_today} ta buyurtma qayd etildi.")

    schedule = []
    sent_set = _sent_today_times()
    today_key = WEEKDAYS[now.weekday()]
    for s in CONFIG.get("slots", []):
        days = s.get("days")
        if days and days != "*" and today_key not in [str(d).lower()[:3] for d in days]:
            schedule.append({"time": s["time"], "label": f"{s.get('label','')} (bu kun emas)", "sent": False})
            continue
        schedule.append({"time": s["time"], "label": s.get("label", ""),
                         "sent": str(s["time"]) in sent_set})

    members = "—"
    if with_channel and CONFIG.get("channel") and not os.environ.get("TG_API_BASE"):
        r = get_chat_member_count(TOKEN, CONFIG["channel"])
        if r.get("ok"):
            members = r["result"]

    b = bot_cfg()
    office_key = os.environ.get("OFFICE_KEY") or (b.get("office_key") or "")
    return {
        "company": "ABK MEBEL",
        "office_locked": bool(office_key),
        "price_text": price_text(),
        "address_text": address_text(),
        "time": now.strftime("%H:%M"),
        "date": f"{WEEKDAY_UZ[WEEKDAYS[now.weekday()]]}, {now.strftime('%d.%m.%Y')}",
        "hours": hours_text(),
        "contact": USERNAME,
        "headline": headline,
        "agents": agents,
        "agents_working": working,
        "log": [{"time": e["ts"][11:16], "emoji": e.get("emoji", "•"), "action": e["action"]}
                for e in log_entries[-25:]][::-1],
        "schedule": schedule,
        "channel": {"posts": chan_posts, "members": members,
                    "hint": "(t.me sahifasidan)" if chan_posts else ""},
        "pending_orders": len(pending),
        "orders_month": len(merged_orders),
        "next_report": f"{b.get('daily_report','18:30')} da kunlik hisobot",
        "demo_lines": [
            {"emoji": "🗂", "action": "Kanalga jadval bo'yicha post tashlandi"},
            {"emoji": "💬", "action": "Mijoz hisob-kitob so'radi — 14.2 m² → 28.4$"},
            {"emoji": "🏢", "action": "Manzil va ish vaqti yuborildi"},
            {"emoji": "💬", "action": "Buyurtma anketasi 3/6 qadamda"},
            {"emoji": "🗂", "action": "Kanaldagi postlar tekshirildi"},
            {"emoji": "🏢", "action": "Javob kutayotgan buyurtmalar eslatildi"},
        ],
    }


def office_text(data):
    """/ofis buyrug'i uchun matn ko'rinishi."""
    lines = [f"🏢 <b>AI-OFIS — jonli holat</b>",
             f"🕒 {data['time']} · {data['date']}",
             f"👥 Ishda: <b>{data['agents_working']} ta AI-xodim</b>",
             ""]
    for a in data["agents"]:
        lines.append(f"{a['emoji']} <b>{a['name']}</b> — {a['status_label']}")
        lines.append(f"   {a['task']}")
        metrics = " · ".join(f"{m['label']}: <b>{m['value']}</b>" for m in a["metrics"])
        lines.append(f"   {metrics}")
        if a.get("last"):
            lines.append(f"   <i>oxirgi amal: {a['last']}</i>")
        lines.append("")
    sched = " · ".join(f"{s['time']}{'✅' if s['sent'] else '⏳'}" for s in data["schedule"])
    lines.append(f"🗓 Postlar jadvali: {sched}")
    if data["channel"]["posts"]:
        lines.append("\n📢 Kanaldagi oxirgi postlar:")
        for p in data["channel"]["posts"][:3]:
            lines.append(f"   • {p['time']} — {p['text'][:60]}")
    lines.append(f"\n📥 Javob kutayotgan buyurtmalar: <b>{data['pending_orders']}</b>")
    lines.append(f"⏰ {data['next_report']}")
    lines.append("\n<i>AI-ofisni ilova ko'rinishida ochish uchun quyidagi tugmani bosing 👇</i>")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# ILOVA ORQALI XODIM BILAN SUHBAT (savol-javob va buyruqlar)
# --------------------------------------------------------------------------
APP_ASKS = {
    "postchi": ["Nima qilyapsan?", "Keyingi post qachon?", "Bugun nechta post tashlading?",
                "Postni hozir tashla"],
    "menejer": ["Nima qilyapsan?", "Bugun nechta mijoz yozdi?", "Narx qancha?",
                "Ish vaqti qanday?"],
    "ofis": ["Nima qilyapsan?", "Manzil qayerda?", "Bugungi hisobot",
             "Jurnalni ko'rsat"],
    "suhbat": ["Nima qilyapsan?", "Xato yozilgan savolni tushunasanmi?",
               "Bugun nechta mijoz yozdi?", "Premium emoji nima beradi?"],
}


def _agent_state(a):
    return f"{a['status_label']} · {a['task']}"


def _metric(a, key):
    for m in a.get("metrics", []):
        if m["key"] == key:
            return m["value"]
    return "—"


def app_ask(agent_key, text, allow_commands=True):
    """Ilovada xodimga berilgan savol yoki buyruqqa javob qaytaradi.

    Qaytaradi: {"agent", "name", "emoji", "reply", "action", "asks"}
    action — ilovada qo'shimcha harakat: break:coffee | break:water | break:food |
             post | toggle | None
    """
    text = (text or "").strip()
    norm = normalize(text)
    data = build_office_data(with_channel=False)
    a = next((x for x in data["agents"] if x["key"] == agent_key), None)
    if a is None:
        a = data["agents"][0] if data["agents"] else None
        agent_key = a["key"] if a else "ofis"
    name, emoji = (a["name"], a["emoji"]) if a else ("AI-xodim", "🤖")
    out = {"agent": agent_key, "name": name, "emoji": emoji, "action": None,
           "asks": APP_ASKS.get(agent_key, APP_ASKS["ofis"])}

    def done(reply, action=None):
        out["reply"] = reply
        out["action"] = action
        return out

    if not text:
        return done(f"Marhamat, savolingizni yozing — men {name}man. {a['task'] if a else ''}")

    # 1) Salomlashish / minnatdorchilik
    if is_greeting(norm) and len(norm.split()) <= 4:
        return done(f"Assalomu alaykum! 👋 Men — {name}. {_agent_state(a)}")
    if is_thanks(norm):
        return done("Sizga rahmat! 🙌 Yana savolingiz bo'lsa, shu yerda yozing.")

    # 2) Tanaffus (ko'rinishda aks etadi)
    if has_word(norm, ("tanaffus", "dam", "kofe", "choy", "suv", "ovqat", "tushlik")):
        if has_word(norm, ("kofe", "choy")):
            kind = "coffee"
        elif has_word(norm, ("ovqat", "tushlik")):
            kind = "food"
        elif has_word(norm, ("suv",)):
            kind = "water"
        else:
            kind = random.choice(("coffee", "water", "food"))   # faqat "tanaffus" deyilsa
        words = {"coffee": "☕ Ha, bir piyola kofe ichib olaman — kayfiyat ko'tariladi!",
                 "water": "💧 Kulerda muzdek suv ichib olaman, zambilak-zambilak 😌",
                 "food": "🍽 Yengil tushlik qilib olaman, keyin yana ishga tushaman."}
        log_action(agent_key, "tanaffusga chiqdi", "ilovadan buyruq berildi", emoji="☕")
        return done(words[kind], f"break:{kind}")

    # 3) Xodimning holati
    if has_word(norm, ("nima", "qilyapsan", "ishlayapsan", "qanday", "holat", "gap")):
        last = f"\n<i>Oxirgi amalim: {a['last']}</i>" if a.get("last") else ""
        return done(f"Men hozir: {_agent_state(a)}{last}")

    # 4) Metrikalar / natijalar
    if has_word(norm, ("nechta", "natija", "hisobot", "qilding", "bugun")):
        parts = [f"{m['label'].capitalize()}: <b>{m['value']}</b>" for m in a.get("metrics", [])]
        last = f"\n\n<i>Oxirgi amalim: {a['last']}</i>" if a.get("last") else ""
        if has_word(norm, ("jurnal",)):
            entries = today_log(agent_key)[-6:][::-1]
            body = "\n".join(f"{e['ts'][11:16]} {e.get('emoji','•')} {e['action']}" for e in entries) \
                or "Bugun hali amal bo'lmagan."
            return done(f"<b>Jurnalim (bugun):</b>\n{body}")
        return done(f"<b>Bugungi natijalarim</b>\n" + "\n".join(parts) + last)

    # 5) Jurnal (alohida so'ralsa)
    if has_word(norm, ("jurnal", "log")):
        entries = today_log(agent_key)[-6:][::-1]
        body = "\n".join(f"{e['ts'][11:16]} {e.get('emoji','•')} {e['action']}" for e in entries) \
            or "Bugun hali amal bo'lmagan."
        return done(f"<b>Jurnalim (bugun):</b>\n{body}")

    # 6) Narx
    if has_word(norm, ("narx", "qancha", "summa", "pul", "hisob", "kromka")):
        return done(price_text())

    # 7) Manzil va ish vaqti
    if has_word(norm, ("manzil", "qayerda", "xarita", "joylashuv", "vaqt", "soat")):
        return done(f"📍 <b>Manzilimiz:</b>\n{address_text()}\n\n🕘 Ish vaqti: {hours_text()}")

    # 8) Buyruqlar (faqat kalit bo'lmasa yoki kalit to'g'ri bo'lsa)
    want_command = has_word(norm, ("tashla", "yubor", "qil", "post", "to'xta", "toxta",
                                   "yoq", "yoqqin", "ishla", "davom"))
    if want_command and not allow_commands:
        return done("🔒 Bu buyruqni bajarish uchun ilova kaliti kerak "
                    "(config.json → <code>bot.office_key</code>).")

    if has_word(norm, ("post", "tashla", "yubor")):
        if agent_key != "postchi":
            return done("Postni faqat 🗂 Reklama agenti tashlaydi — savolni unga bering.")
        ok, info = manual_post("")
        log_action("postchi", "qo'lda post tashladi" if ok else "post tashlashga urindi",
                   "ilovadan buyruq berildi")
        return done(info, "post" if ok else None)

    if has_word(norm, ("to'xta", "toxta", "to'xtat", "dam ol")):
        CONFIG.setdefault("bot", {}).setdefault("agents", {}).setdefault(agent_key, {})["enabled"] = False
        save_json(CONFIG_PATH, CONFIG)
        log_action("ofis", "xodim to'xtatildi", name)
        return done(f"⏸ Bo'ldi — men to'xtadim. Ishga qaytarish uchun «ishla» deb yozing.",
                    "toggle")

    if has_word(norm, ("ishla", "davom", "yoq", "qayt")):
        CONFIG.setdefault("bot", {}).setdefault("agents", {}).setdefault(agent_key, {})["enabled"] = True
        save_json(CONFIG_PATH, CONFIG)
        log_action("ofis", "xodim yoqildi", name)
        return done("🟢 Ishga qaytdim! Savollaringizni kutaveraman.", "toggle")

    # 9) Suhbat agentiga maxsus savollar
    if agent_key == "suhbat" and has_word(norm, ("xato", "premium", "emoji", "tushuna", "yozsa")):
        emap = [k for k in (bot_cfg().get("premium_emojis") or {}) if not k.startswith("_")]
        return done("Men xato yozilgan savollarni tushunaman: «pryikt qanchaga chizasan» deb "
                    "yozilsa ham, men «loyiha narxi» deb tushunib javob beraman 🙂\n"
                    f"🎨 Premium emojilar: <b>{len(emap)}</b> ta o'rganilgan.")

    # 10) Tushunilmadi
    return done("Savolingizni to'liq tushunmadim 🤔 Quyidagi savollardan birini tanlab ko'ring "
                "yoki boshqacha yozib ko'ring.")


# --------------------------------------------------------------------------
# Hisobotlar
# --------------------------------------------------------------------------
def agents_report_block():
    d = build_office_data(with_channel=False)
    lines = ["", "<b>🤖 AI-XODIMLAR HISOBOTI</b>"]
    for a in d["agents"]:
        metrics = " · ".join(f"{m['label']}: {m['value']}" for m in a["metrics"])
        lines.append(f"{a['emoji']} {a['name']}: {metrics}")
        if a.get("last"):
            lines.append(f"    oxirgi amal: {a['last']}")
    lines.append(f"👥 Ishda: {d['agents_working']} ta · 📥 Javob kutayotgan: {d['pending_orders']}")
    return "\n".join(lines)


def build_daily_report(day=None):
    now = now_tz()
    day = day or now.date().isoformat()
    d = state().get("days", {}).get(day, {})
    day_orders = [o for o in orders() if o["created"][:10] == day]
    text = [f"📊 <b>Kunlik hisobot</b> — {day} ({WEEKDAY_UZ[WEEKDAYS[now.weekday()]]})",
            "",
            f"👥 Botga yangi mijozlar: <b>{d.get('new_users', 0)}</b>",
            f"➕ Kanalga qo'shilganlar: <b>{d.get('member_joins', 0)}</b>",
            f"✍️ Buyurtmalar: <b>{len(day_orders)}</b>",
            f"💬 Murojaatlar: <b>{d.get('messages', 0)}</b>",
            f"🚫 O'chirilgan reklama: <b>{d.get('spam_deleted', 0)}</b>"]
    if day_orders:
        text.append("\n<b>Bugungi buyurtmalar:</b>")
        for o in day_orders:
            text.append(f"#{o['id']} — {o['name']}, {o['phone']} ({o.get('furniture', '')[:40]})")
    text.append(agents_report_block())
    return "\n".join(text)


def build_weekly_report():
    now = now_tz()
    st = state()
    days = [(now.date() - dt.timedelta(days=i)).isoformat() for i in range(7)]
    new_users = sum(st.get("days", {}).get(d, {}).get("new_users", 0) for d in days)
    joins = sum(st.get("days", {}).get(d, {}).get("member_joins", 0) for d in days)
    msgs = sum(st.get("days", {}).get(d, {}).get("messages", 0) for d in days)
    week_orders = [o for o in orders() if o["created"][:10] >= days[-1]]
    text = [f"📈 <b>Haftalik hisobot</b> ({days[-1]} — {days[0]})", "",
            f"👥 Yangi mijozlar: <b>{new_users}</b>",
            f"➕ Kanalga qo'shilganlar: <b>{joins}</b>",
            f"✍️ Buyurtmalar: <b>{len(week_orders)}</b>",
            f"💬 Murojaatlar: <b>{msgs}</b>",
            agents_report_block(),
            "",
            "Izoh: yaxshi ishlayotgan postlarni saqlab, ishlamaganlarini almashtiring 😉"]
    return "\n".join(text)


def send_report(kind="daily"):
    text = build_daily_report() if kind == "daily" else build_weekly_report()
    ok = notify_admin(text)
    log_action("ofis", "hisobot yuborildi", kind)
    log.info("%s hisobot: %s", kind, ok)
    return ok


def check_reports():
    if not agent_on("ofis"):
        return
    b = bot_cfg()
    now = now_tz()
    st = state()
    today = now.date().isoformat()
    changed = False
    daily_at = str(b.get("daily_report", "")).strip()
    if daily_at and st.get("reports", {}).get("daily") != today:
        try:
            h, m = [int(x) for x in daily_at.split(":")]
            if now.hour * 60 + now.minute >= h * 60 + m:
                send_report("daily")
                st.setdefault("reports", {})["daily"] = today
                changed = True
        except ValueError:
            pass
    wr = b.get("weekly_report") or {}
    key = f"weekly-{today}"
    if wr.get("time") and st.get("reports", {}).get("weekly") != key:
        if WEEKDAYS[now.weekday()] == str(wr.get("day", "fri")).lower()[:3]:
            try:
                h, m = [int(x) for x in str(wr["time"]).split(":")]
                if now.hour * 60 + now.minute >= h * 60 + m:
                    send_report("weekly")
                    st.setdefault("reports", {})["weekly"] = key
                    changed = True
            except ValueError:
                pass
    if changed:
        save_state(st)


# --------------------------------------------------------------------------
# Kontent yordamchilari
# --------------------------------------------------------------------------
def keyword_answer(text, norm=None):
    """Kalit so'z bo'yicha javob. Xato yozilgan so'zlarni ham tushunadi (fuzzy).

    Qaytaradi: (javob, klaviatura, agent, turi)
    """
    low = text.lower()
    norm = norm if norm is not None else normalize(text)

    # Eng aniq mos kelgan qoida tanlanadi: "kromka hisobi" so'zi "hisob" dan ustun turadi
    best_score, best_rule = -1, None
    for rule in bot_cfg()["keywords"]:
        for kw in rule.get("keywords", []):
            if text_matches(kw, low, norm) and len(kw) > best_score:
                best_score, best_rule = len(kw), rule
    if best_rule is not None:
            rule = best_rule
            agent = rule.get("agent", "menejer")
            special = rule.get("special")
            if special == "address":
                return address_text(), address_keyboard(), agent, "address"
            if special == "greeting":
                return suhbat_pick("greetings", ""), menu_keyboard(), agent, "salom"
            if special == "thanks":
                return suhbat_pick("thanks", ""), back_keyboard(), agent, "rahmat"
            if special == "price":
                return suhbat_pick("price_hint", ""), {"inline_keyboard": [
                    [{"text": "🧮 Narx kalkulyatori", "callback_data": "menu:calc"},
                     {"text": "📋 Narxlar", "callback_data": "menu:price"}],
                    [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"}]]}, agent, "narx"
            answer = rule.get("answer", "")
            kb = menu_keyboard() if rule.get("menu") else back_keyboard()
            return answer, kb, agent, "javob"
    return None, None, None, None


def is_number(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.replace(" ", ""))
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return value if 0.5 <= value <= 100000 else None


# --------------------------------------------------------------------------
# Suhbat oqimlari
# --------------------------------------------------------------------------
def get_flow(chat_id):
    flows = state().get("flows", {})
    return flows.get(str(chat_id))


def set_flow(chat_id, obj):
    st = state()
    st.setdefault("flows", {})[str(chat_id)] = obj
    save_state(st)


def pop_flow(chat_id):
    st = state()
    st.get("flows", {}).pop(str(chat_id), None)
    save_state(st)


def start_calc(chat_id):
    if not agent_on("menejer"):
        reply(chat_id, "Sotuv bo'limi hozircha to'xtatilgan. "
                                     f"Savolingizni yozing — admin javob beradi: {USERNAME}")
        return False
    set_flow(chat_id, {"step": "calc_area"})
    reply(chat_id,
                 f"🧮 <b>Narx kalkulyatori</b>\n\nMaterial maydonini kiriting (m²).\n"
                 f"Masalan: <b>12.5</b>\n\nNarx: {bot_cfg()['price_per_sqm']}$ × maydon."
                 f"\n\n(Bekor qilish uchun /bekor)", reply_markup=back_keyboard())
    return True


def start_order(chat_id):
    if not agent_on("menejer"):
        reply(chat_id, "Buyurtma qabul bo'limi hozircha to'xtatilgan. "
                                     f"To'g'ridan-to'g'ri yozing: {USERNAME}")
        return False
    steps = bot_cfg()["order_steps"]
    set_flow(chat_id, {"step": steps[0]["key"], "data": {}, "idx": 0})
    reply(chat_id, order_step_text(steps[0]))
    log_action("menejer", "anketa boshlandi", "mijoz buyurtma anketasini boshladi", chat_id)
    return True


def _next_step(idx):
    steps = bot_cfg()["order_steps"]
    return steps[idx + 1] if idx + 1 < len(steps) else None


def finish_order(chat_id, user, data):
    all_orders = orders()
    num = len(all_orders) + 1
    now = now_tz()
    order = {
        "id": num, "user_id": chat_id, "username": user.get("username", ""),
        "name": data.get("name", ""), "phone": data.get("phone", ""),
        "furniture": data.get("furniture", ""), "sizes": data.get("sizes", ""),
        "material": data.get("material", ""), "deadline": data.get("deadline", ""),
        "created": now.isoformat(timespec="seconds"), "status": "yangi",
    }
    all_orders.append(order)
    save_orders(all_orders)
    touch_day(now.date().isoformat(), "orders")
    log_action("menejer", "buyurtma qabul qilindi",
               f"#{num} — {order['name']}, {order['furniture'][:40]}", chat_id)

    notify_admin(
        f"🆕 <b>YANGI BUYURTMA #{num}</b>\n\n"
        f"👤 {order['name']}\n📞 {order['phone']}\n"
        f"🪑 Mebel: {order['furniture']}\n📐 O'lchamlar: {order['sizes']}\n"
        f"🪵 Material/furnitura: {order['material'] or '—'}\n⏱ Muddat: {order['deadline'] or '—'}\n\n"
        f"🆔 <code>{chat_id}</code>"
        f"{' · @' + order['username'] if order['username'] else ''}\n"
        f"🕒 {order['created'][:16]}\n\n"
        f"Javob: <code>/reply {chat_id} Matn</code> · Holat: <code>/mark {num} bajarildi</code>\n\n"
        + dalolatnoma_text(order))

    reply(chat_id,
                 f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
                 f"Buyurtma raqami: <b>#{num}</b>\n"
                 f"👤 {order['name']}\n📞 {order['phone']}\n🪑 {order['furniture']}\n"
                 f"📐 {order['sizes']}\n\n"
                 f"Dalolatnoma loyihasi tayyorlandi — {USERNAME} siz bilan bog'lanib, "
                 f"chizma va o'lchamlarni tasdiqlaydi. Rahmat! 🤝",
                 reply_markup=back_keyboard())


# --------------------------------------------------------------------------
# Mijoz bilan muloqot
# --------------------------------------------------------------------------
def flow_pending(chat_id):
    """Mijozda tugallanmagan anketa/kalkulyator bormi."""
    return bool(get_flow(chat_id))


def menu_text_v2(name=""):
    """Menyu matni — mijoz nima qilishini darhol tushunadi."""
    salute = f"Assalomu alaykum, <b>{name}</b>!" if name else "Assalomu alaykum!"
    return (f"🏢 <b>ABK MEBEL</b> — BAZIS-Mebel loyihalari va FastReport xizmatlari\n\n"
            f"{salute} 👋\n"
            f"Men sizga quyidagilarda yordam beraman:\n\n"
            f"📋 <b>Narxlar</b> — material m² uchun {bot_cfg()['price_per_sqm']}$\n"
            f"🧮 <b>Kalkulyator</b> — xona o'lchamidan summani hisoblaydi\n"
            f"✍️ <b>Buyurtma</b> — 6 qadamda anketani to'ldirasiz\n"
            f"📍 <b>Manzil</b> — xarita va marshrut bilan\n"
            f"⚙️ <b>FastReport</b> — shablon va skriptlar\n\n"
            f"Quyidagi tugmalardan birini bosing yoki savolingizni yozing 👇\n\n"
            f"🕘 Ish vaqti: <b>{hours_text()}</b>\n"
            f"📩 Aloqa: {USERNAME}")


def send_main_menu(chat_id, name="", edit_message=None):
    if edit_message:
        return edit_message_text(TOKEN, chat_id, edit_message, menu_text_v2(name), menu_keyboard())
    return reply(chat_id, menu_text_v2(name), reply_markup=menu_keyboard())


def handle_private_message(msg):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    register_user(user, is_bot=user.get("is_bot", False))
    if user.get("is_bot"):
        return
    text = (msg.get("text") or msg.get("caption") or "").strip()
    touch_day(now_tz().date().isoformat(), "messages")

    # 0a) Admin premium emoji yuborsa — bot o'rganib oladi
    if admin_id() is not None and user.get("id") == admin_id() and extract_custom_emojis(msg):
        learn_premium_emoji(msg, chat_id)
        return

    # 0) Fayl/rasm (o'lchov, eskiz, loyiha rasmi) — adminga uzatiladi
    if (msg.get("photo") or msg.get("document")) and not text.startswith("/"):
        try:
            forward_message(TOKEN, admin_id(), chat_id, msg["message_id"])
        except Exception as e:
            log.warning("Faylni uzatib bo'lmadi: %s", e)
        notify_admin(f"📎 Mijoz fayl yubordi\n👤 {user.get('first_name','')}\n"
                     f"🆔 <code>{chat_id}</code>\n💬 {text[:200] or '(izohsiz)'}\n\n"
                     f"Javob: <code>/reply {chat_id} Matn</code>")
        log_action("menejer", "fayl qabul qilindi", f"eskiz/rasm: {text[:40]}", chat_id)
        reply(chat_id, "📎 Faylingiz adminga yuborildi. Tez orada javob beramiz!",
                     reply_markup=back_keyboard())
        return

    # 0b) Pastdagi doimiy tugmalar bosilganda
    btn = CLIENT_BUTTONS.get(text.lower())
    if btn and not flow_pending(chat_id):
        handle_callback({"id": "0", "from": user, "data": btn,
                         "message": {"chat": {"id": chat_id}, "message_id": 0}})
        return

    # 0c) Profil
    if text.lower() == "👤 profil":
        u = users().get(str(chat_id), {})
        reply(chat_id, f"👤 <b>Sizning profilingiz</b>\n\n"
                       f"Ism: <b>{user.get('first_name','')}</b>\n"
                       f"Username: @{user.get('username','—')}\n"
                       f"ID: <code>{chat_id}</code>\n"
                       f"Ro'yxatdan o'tgan: {u.get('joined','—')}", reply_markup=back_keyboard())
        return

    # 1) Tugallanmagan suhbat
    flow = get_flow(chat_id)
    if flow and text and not text.startswith("/"):
        if flow["step"] == "calc_area":
            area = is_number(text)
            if area is None:
                reply(chat_id, "Iltimos, faqat raqam yuboring — masalan: <b>12.5</b>",
                             reply_markup=back_keyboard())
                return
            pop_flow(chat_id)
            log_action("menejer", "narx hisoblandi", f"{area:g} m² → {area*bot_cfg()['price_per_sqm']:g}$",
                       chat_id, emoji="🧮")
            reply(chat_id, calc_result_text(area), reply_markup={"inline_keyboard": [
                [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"},
                 {"text": "📋 Narxlar", "callback_data": "menu:price"}],
                [{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}]]})
            return

        if flow.get("order") is not False and "idx" in flow:
            steps = bot_cfg()["order_steps"]
            idx = flow.get("idx", 0)
            step = steps[idx]
            if text.lower() in ("skip", "/skip") and not step["required"]:
                pass
            else:
                flow["data"][step["key"]] = text
            log_action("menejer", f"anketa {idx+1}/{len(steps)}",
                       f"{step['key']}: {text[:60]}", chat_id)
            nxt = _next_step(idx)
            if nxt is None:
                finish_order(chat_id, user, flow["data"])
                pop_flow(chat_id)
                return
            flow["idx"] = idx + 1
            flow["step"] = nxt["key"]
            set_flow(chat_id, flow)
            reply(chat_id, order_step_text(nxt))
            return

    # 2) Komandalar
    if text.startswith("/"):
        cmd = text.split()[0].lower().split("@")[0]
        arg = text[len(cmd):].strip()
        if handle_command(chat_id, cmd, arg, user):
            return

    # 3) Kalit so'z bo'yicha javob (xato yozilgan so'zlar ham tushuniladi)
    norm, fixes = normalize(text, return_fixes=True) if text else ("", [])
    answer, kb, agent, kind = keyword_answer(text, norm) if text else (None, None, None, None)
    if answer and agent_on(agent):
        reply(chat_id, answer, reply_markup=kb)
        fix_note = ("xato tuzatildi: " + ", ".join(f"{a}→{b}" for a, b in fixes[:3])) if fixes else ""
        if kind == "address":
            log_action("ofis", "manzil ma'lumoti yuborildi", f"mijoz {chat_id}", chat_id, emoji="📍")
        elif fixes:
            log_action(agent, "xato yozilgan savolni tushundi",
                       f"«{text[:40]}» — {fix_note}", chat_id)
        elif kind in ("narx", "salom", "rahmat"):
            log_action(agent, "javob berdi (qisqa yo'l)", f"«{text[:40]}»", chat_id)
        else:
            log_action(agent, "javob berdi", f"kalit so'z: «{text[:40]}»", chat_id)
        if kind == "narx":
            log_action("menejer", "narx yuborildi", f"«{text[:40]}»", chat_id, emoji="💰")
        return

    # 4) SUHBAT AGENTI — samimiy va xato yozilgan xabarlarni ham tushunadi
    if text and agent_on("suhbat"):
        answer, kb, agent, kind = suhbat_reply(text, norm, user.get("first_name", ""))
        if kind == "narx" and fixes:
            kind = "xato"
        reply(chat_id, answer, reply_markup=kb)
        log_action("suhbat", {
            "salom": "salomlashdi", "rahmat": "minnatdorchilikni qabul qildi",
            "xayr": "xayrlashdi", "narx": "narx haqidagi savolga javob berdi",
            "xato": "xato yozilgan savolni tushundi",
            "suhbat": "samimiy suhbat qurdi", "savol": "savolni tushunmadi — aniqlashtirdi",
            "tushunarsiz": "tushunmadi — menyu taklif qildi",
        }.get(kind, "javob berdi"), f"«{text[:50]}»", chat_id)
        if kind in ("savol", "narx", "xato", "tushunarsiz"):
            notify_admin(f"✉️ <b>Mijoz xabari</b> (Suhbat agenti javob berdi)\n\n"
                         f"👤 {user.get('first_name','')}"
                         f"{' (@' + user['username'] + ')' if user.get('username') else ''}\n"
                         f"🆔 <code>{chat_id}</code>\n🕒 {now_tz().strftime('%H:%M')}\n"
                         f"💬 Mijoz: {text[:800]}\n\n"
                         f"Javob: <code>/reply {chat_id} Matn</code>")
        return

    # 5) Boshqa hollar — xabar adminga yuboriladi
    if text:
        notify_admin(f"✉️ <b>Yangi xabar (mijoz)</b>\n\n"
                     f"👤 {user.get('first_name','')}"
                     f"{' (@' + user['username'] + ')' if user.get('username') else ''}\n"
                     f"🆔 <code>{chat_id}</code>\n🕒 {now_tz().strftime('%H:%M')}\n\n{text[:1500]}\n\n"
                     f"Javob: <code>/reply {chat_id} Matn</code>")
        log_action("menejer", "savol adminga yuborildi", f"«{text[:50]}»", chat_id)
        note = "" if is_work_time() else f"\n\n{after_hours_note()}"
        reply(chat_id,
              f"✅ Xabaringiz qabul qilindi va adminga yuborildi.\n"
              f"Ish vaqtida ({hours_text()}) javob beramiz.{note}",
              reply_markup=back_keyboard())
        return

    send_main_menu(chat_id, user.get("first_name", ""))


def handle_command(chat_id, cmd, arg, user):
    aid = admin_id()
    is_admin = aid is not None and user.get("id") == aid

    if cmd in ("/start", "/menu", "/help"):
        if arg in ("calc", "kalkulyator"):
            return start_calc(chat_id)
        if arg in ("order", "buyurtma"):
            return start_order(chat_id)
        reply(chat_id, f"🏢 <b>ABK MEBEL yordamchisi</b>", reply_markup=client_keyboard())
        send_main_menu(chat_id, user.get("first_name", ""))
        if aid is None:
            reply(chat_id,
                         f"ℹ️ Sizning Telegram ID: <code>{user.get('id')}</code>\n\n"
                         f"Bot egasi bo'lsangiz, shu raqamni ADMIN_ID sifatida kiriting — "
                         f"shunda buyurtmalar, hisobotlar va AI-ofis sizga ko'rinadi.")
        return True

    if cmd in ("/bekor", "/cancel"):
        pop_flow(chat_id)
        reply(chat_id, "Bekor qilindi. Kerakli bo'limni tanlang 👇",
                     reply_markup=menu_keyboard())
        return True

    if cmd == "/skip":
        flow = get_flow(chat_id)
        steps = bot_cfg()["order_steps"]
        if flow and "idx" in flow:
            idx = flow.get("idx", 0)
            if not steps[idx]["required"]:
                nxt = _next_step(idx)
                if nxt is None:
                    finish_order(chat_id, user, flow["data"])
                    pop_flow(chat_id)
                else:
                    flow["idx"] = idx + 1
                    flow["step"] = nxt["key"]
                    set_flow(chat_id, flow)
                    reply(chat_id, order_step_text(nxt))
            else:
                reply(chat_id, "Bu savolni o'tkazib yuborib bo'lmaydi 🙂")
        return True

    if cmd in ("/premium", "/emoji"):
        b = bot_cfg()
        emap = {k: v for k, v in (b.get("premium_emojis") or {}).items() if not k.startswith("_")}
        if not emap:
            reply(chat_id, "🎨 <b>Premium emoji hali o'rganilmagan</b>\n\n"
                           "Qanday o'rganiladi:\n"
                           "1️⃣ Shu botga <b>premium emoji</b> yuboring (bir yoki bir nechta)\n"
                           "2️⃣ Bot ularni avtomatik o'rganadi va tasdiqlaydi\n"
                           "3️⃣ Shundan keyin bot javoblarida shu emojilarni ishlatadi\n\n"
                           "ℹ️ Telegram qoidasi (Bot API 9.4): premium emoji bot egasida Telegram "
                           "Premium bo'lsa ishlaydi. Kanallarda hozircha qo'llanmaydi — "
                           "u yerda oddiy emoji chiqadi.", premium=False)
        else:
            lines = [f"🎨 <b>O'rganilgan premium emojilar: {len(emap)} ta</b>", ""]
            lines += [f"{emo} → <code>{eid}</code>" for emo, eid in emap.items()]
            lines += ["", "Bot shu emojilarni javoblarida ishlatadi.",
                      "Yana qo'shish uchun shu chatga yangi premium emoji yuboring."]
            reply(chat_id, "\n".join(lines), premium=False)
        return True

    if cmd in ("/id", "/whoami"):
        reply(chat_id, f"🆔 Sizning Telegram ID: <code>{user.get('id')}</code>")
        return True

    if cmd == "/kalkulyator":
        return start_calc(chat_id)
    if cmd == "/buyurtma":
        return start_order(chat_id)
    if cmd in ("/ofis", "/office"):
        send_office(chat_id, is_admin)
        return True

    # ----- Faqat admin -----
    if cmd == "/agents":
        if not is_admin:
            return False
        lines = ["🤖 <b>AI-XODIMLAR</b> (har birining o'z vazifasi)\n"]
        for key in ("postchi", "menejer", "ofis", "suhbat"):
            a = agent_cfg(key)
            holat = "🟢 yoniq" if a.get("enabled", True) else "⏸ to'xtatilgan"
            lines.append(f"{a['emoji']} <b>{a['name']}</b> — {holat}\n    {a['duty']}")
        lines += ["", "To'xtatish: <code>/agent off menejer</code>",
                  "Yoqish: <code>/agent on menejer</code>",
                  "Kuzatish: /ofis"]
        reply(chat_id, "\n".join(lines))
        return True

    if cmd == "/agent":
        if not is_admin:
            return False
        parts = arg.split()
        if len(parts) < 2 or parts[0] not in ("on", "off") or parts[1] not in (
                "postchi", "menejer", "ofis", "suhbat"):
            reply(chat_id, "Foydalanish: <code>/agent off menejer</code> "
                                         "(postchi | menejer | ofis | suhbat)")
            return True
        mode, key = parts[0], parts[1]
        CONFIG.setdefault("bot", {}).setdefault("agents", {}).setdefault(key, {})["enabled"] = (mode == "on")
        save_json(CONFIG_PATH, CONFIG)
        a = agent_cfg(key)
        verb = "yoqildi" if mode == "on" else "to'xtatildi"
        holat = "🟢 yoniq" if mode == "on" else "⏸ to'xtatilgan"
        log_action("ofis", "xodim " + verb, a["name"])
        reply(chat_id, a["emoji"] + " " + a["name"] + ": " + holat)
        return True

    if cmd == "/ofis" or cmd == "/office":
        send_office(chat_id, is_admin)
        return True

    if cmd in ("/ilova", "/app", "/app_ilova"):
        row = app_button_row()
        if row:
            reply(chat_id, "📱 <b>ABK MEBEL ilovasi</b>\n\n"
                           "Ilovada: AI-ofis (xodimlar), narxlar, buyurtma, manzil, bot bo'limlari.",
                  reply_markup={"inline_keyboard": [row]})
        else:
            reply(chat_id, "📱 <b>Ilova</b>\n\nIlova serverda (https manzil) ishga tushgach "
                           "ochiladi. Hozircha brauzerda ochish uchun: bot yuborgan "
                           "<b>ai-ofis.html</b> faylini ko'ring.", premium=False)
        return True

    if cmd in ("/guruh", "/group"):
        if not is_admin:
            return False
        ch = CONFIG.get("channel") or ""
        lines = ["👥 <b>Kanal guruhi (izohlar guruhi)</b>", ""]
        if not ch:
            lines.append("Kanal sozlanmagan (config.json → channel).")
        else:
            r = get_chat(TOKEN, ch)
            if not r.get("ok"):
                lines.append("Kanalga ulanib bo'lmadi: " + str(r.get("description"))[:80])
            else:
                linked = r["result"].get("linked_chat_id")
                lines.append(f"📢 Kanal: <b>{r['result'].get('title','')}</b> (@{r['result'].get('username','')})")
                if not linked:
                    lines.append("\n🔗 Bu kanalga hali <b>guruh bog'lanmagan</b>.\n"
                                 "Kanal → Sozlamalar → «Discussion» (Muhokama) → guruhni ulang.")
                else:
                    g = get_chat(TOKEN, linked)
                    mt = get_chat_member(TOKEN, linked, BOT_ID) if BOT_ID else {"ok": False}
                    status = (mt.get("result") or {}).get("status") if mt.get("ok") else "a'zo emas"
                    cnt = get_chat_member_count(TOKEN, linked)
                    gname = g["result"].get("title", "guruh") if g.get("ok") else "guruh"
                    gun = ("@" + g["result"]["username"]) if g.get("ok") and g["result"].get("username") else ""
                    lines += [f"🔗 Guruh: <b>{gname}</b> {gun}",
                              f"🆔 guruh ID: <code>{linked}</code>",
                              f"👥 a'zolar: <b>{cnt.get('result','—') if cnt.get('ok') else '—'}</b>",
                              f"🤖 botning holati: <b>{status}</b>", ""]
                    if status in ("left", "kicked") or not mt.get("ok"):
                        lines += ["❗️ Bot guruhga <b>qo'shilmagan</b>. Qo'shish:",
                                  "1️⃣ Guruhni oching → nomini bosing → <b>Add members</b> → "
                                  "@abkmebel_javob_bot",
                                  "2️⃣ Guruhni bosing → <b>Administrators</b> → Add Admin → bot → "
                                  "✅ Delete messages, ✅ Pin messages → Save"]
                    else:
                        lines.append("✅ Bot guruhda — izohlardagi savollarga javob beradi.")
                    lines += ["", "⚙️ <b>Qanday javob beradi:</b>",
                              "• Botga <b>@abkmebel_javob_bot</b> deb murojaat qilinsa — javob beradi",
                              "• Botning xabariga <b>javob (reply)</b> qilinsa — javob beradi",
                              "• Boshqa oddiy savollarga ham javob berishi uchun:",
                              "   — @BotFather → /setprivacy → botni tanlang → <b>Disable</b>",
                              "   — yoki botni guruhga <b>admin</b> qiling (admin hamma xabarni ko'radi)",
                              "   — so'ng config.json → <code>bot.group.answer_questions</code> = true"]
        reply(chat_id, "\n".join(lines), premium=False)
        return True

    if cmd == "/log":
        if not is_admin:
            return False
        entries = today_log()[-20:][::-1]
        if not entries:
            reply(chat_id, "Bugun hali AI-xodimlar amal bajarmadi.")
            return True
        lines = ["🗒 <b>AI-ofis jurnali (bugun)</b>\n"]
        for e in entries:
            lines.append(f"{e['ts'][11:16]} {e.get('emoji','•')} {e['action']}"
                         + (f" — <i>{e['detail'][:60]}</i>" if e.get("detail") else ""))
        reply(chat_id, "\n".join(lines))
        return True

    if cmd == "/post":
        if not is_admin:
            return False
        ok, info = manual_post(arg)
        reply(chat_id, info)
        return True

    if cmd == "/stats":
        if not is_admin:
            return False
        st = state()
        today = now_tz().date().isoformat()
        d = st.get("days", {}).get(today, {})
        all_orders = orders()
        reply(chat_id,
                     f"📊 <b>Statistika</b>\n\n"
                     f"👥 Bot foydalanuvchilari: <b>{len(users())}</b>\n"
                     f"🆕 Bugun qo'shilganlar: <b>{d.get('new_users', 0)}</b>\n"
                     f"✍️ Jami buyurtmalar: <b>{len(all_orders)}</b> "
                     f"(yangi: {len([o for o in all_orders if o.get('status') == 'yangi'])})\n"
                     f"💬 Bugungi murojaatlar: <b>{d.get('messages', 0)}</b>\n"
                     f"🚫 O'chirilgan reklama: <b>{d.get('spam_deleted', 0)}</b>")
        return True

    if cmd == "/orders":
        if not is_admin:
            return False
        all_orders = orders()
        if not all_orders:
            reply(chat_id, "Hozircha buyurtmalar yo'q.")
            return True
        lines = ["📋 <b>Oxirgi buyurtmalar</b>\n"]
        for o in all_orders[-10:][::-1]:
            lines.append(f"<b>#{o['id']}</b> [{o.get('status','yangi')}] {o['created'][:16]}\n"
                         f"👤 {o['name']} · {o['phone']}\n🪑 {o.get('furniture','')[:60]}\n"
                         f"🆔 <code>{o['user_id']}</code>"
                         f"{' · @' + o['username'] if o.get('username') else ''}\n")
        reply(chat_id, "\n".join(lines))
        return True

    if cmd == "/dalolatnoma":
        if not is_admin:
            return False
        all_orders = orders()
        if not all_orders:
            reply(chat_id, "Buyurtmalar yo'q.")
            return True
        oid = arg.strip()
        target = next((o for o in all_orders if str(o["id"]) == oid), all_orders[-1])
        reply(chat_id, dalolatnoma_text(target))
        return True

    if cmd == "/report":
        if not is_admin:
            return False
        send_report("weekly" if "hafta" in arg or "weekly" in arg else "daily")
        reply(chat_id, "Hisobot yuborildi ✅")
        return True

    if cmd == "/broadcast":
        if not is_admin:
            return False
        if not arg:
            reply(chat_id, "Foydalanish: <code>/broadcast E'lon matni</code>")
            return True
        sent = failed = 0
        for uid in users():
            r = reply(uid, f"📣 <b>E'lon</b>\n\n{arg}")
            sent += 1 if r.get("ok") else 0
            failed += 0 if r.get("ok") else 1
            time.sleep(0.05)
        log_action("ofis", "e'lon yuborildi", f"{sent} ta mijozga")
        reply(chat_id, f"📣 Yuborildi: <b>{sent}</b>, yetmadi: {failed}")
        return True

    if cmd == "/reply":
        if not is_admin:
            return False
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            reply(chat_id, "Foydalanish: <code>/reply 123456789 Javob matni</code>")
            return True
        target, body = parts[0].strip(), parts[1]
        r = reply(target, f"💬 <b>Admin javobi:</b>\n\n{body}")
        log_action("ofis", "admin javob yozdi", f"mijoz {target}", target)
        reply(chat_id, "Yuborildi ✅" if r.get("ok") else
                     f"Yuborilmadi ❌ {r.get('description')}")
        return True

    if cmd == "/mark":
        if not is_admin:
            return False
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            reply(chat_id, "Foydalanish: <code>/mark 3 bajarildi</code>")
            return True
        oid, status = parts[0], parts[1]
        all_orders = orders()
        for o in all_orders:
            if str(o["id"]) == oid:
                o["status"] = status
                save_orders(all_orders)
                log_action("ofis", "buyurtma holati o'zgartirildi", f"#{oid} → {status}")
                reply(chat_id, f"#{oid} holati: <b>{status}</b>")
                return True
        reply(chat_id, f"#{oid} topilmadi.")
        return True

    return False


def send_office(chat_id, is_admin):
    """AI-ofis holatini yuboradi (ilova tugmasi bilan)."""
    if not is_admin:
        # Mijozga ichki ma'lumot ko'rsatilmaydi
        reply(chat_id, menu_text())
        return
    data = build_office_data()
    text = office_text(data)
    kb = {"inline_keyboard": []}
    kb["inline_keyboard"].append(app_button_row() or [])
    row = office_button_row()
    if row:
        kb["inline_keyboard"].append(row)
    else:
        text += ("\n\n⚠️ <b>Ilova tugmasi hozircha yo'q</b> — u faqat serverda (https manzil) "
                 "ishlaydi. Render'ga joylangach tugma avtomatik paydo bo'ladi.\n"
                 "Hozir ilovani ko'rish uchun: bot yuborgan <b>ofis-holati.pdf</b> yoki "
                 "<b>ai-ofis.html</b> faylini oching.")
    kb["inline_keyboard"].append([{"text": "🗒 Jurnal", "callback_data": "adm:log"},
                                  {"text": "🤖 Xodimlar", "callback_data": "adm:agents"}])
    kb["inline_keyboard"].append([{"text": "📋 Buyurtmalar", "callback_data": "adm:orders"}])
    reply(chat_id, text, reply_markup=kb)


def manual_post(arg=""):
    """🗂 Reklama agenti: kanalga postni qo'lda tashlash."""
    if not agent_on("postchi"):
        return False, "Reklama agenti to'xtatilgan (/agent on postchi)"
    try:
        import telegram_scheduler as ts
    except Exception as e:
        return False, f"Scheduler moduli topilmadi: {e}"

    wanted = arg.strip()
    slots = CONFIG.get("slots", [])
    slot = None
    if wanted:
        slot = next((s for s in slots if str(s.get("time")) == wanted), None)
        if slot is None:
            return False, f"«{wanted}» vaqti topilmadi. Mavjud: " + ", ".join(str(s["time"]) for s in slots)
    else:
        _, nxt = _next_slot(now_tz())
        slot = nxt or (slots[0] if slots else None)
    if slot is None:
        return False, "Slotlar sozlanmagan."

    ok = ts.deliver(CONFIG, slot, ts.load_state())
    if ok:
        log_action("postchi", "qo'lda post tashlandi",
                   f"{slot.get('time')} «{slot.get('label','')}» → {CONFIG.get('channel')}")
        return True, f"✅ Post tashlandi: {slot.get('time')} «{slot.get('label','')}»"
    return False, "❌ Post yuborilmadi — bot.log ni ko'ring."


# --------------------------------------------------------------------------
# Tugmalar
# --------------------------------------------------------------------------
def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    data = cb.get("data", "")
    user = cb.get("from", {})
    register_user(user)
    name = user.get("first_name", "")
    answer_callback_query(TOKEN, cb["id"])

    if data == "menu:main":
        send_main_menu(chat_id, name, edit_message=message_id)
    elif data == "menu:price":
        reply(chat_id, price_text(), reply_markup={"inline_keyboard": [
            [{"text": "🧮 Kalkulyatorda hisoblash", "callback_data": "menu:calc"}],
            [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"}],
            [{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}]]})
    elif data == "menu:fastreport":
        reply(chat_id, fastreport_text(), reply_markup=back_keyboard())
    elif data == "menu:contact":
        reply(chat_id, contact_text(), reply_markup=address_keyboard())
    elif data == "menu:address":
        reply(chat_id, address_text(), reply_markup=address_keyboard())
        log_action("ofis", "manzil ma'lumoti yuborildi", f"mijoz {chat_id}", chat_id, emoji="📍")
    elif data == "menu:portfolio":
        send_portfolio(chat_id)
    elif data == "menu:faq":
        reply(chat_id, faq_list_text(), reply_markup=faq_keyboard())
    elif data.startswith("faq:"):
        idx = int(data.split(":")[1])
        faq = bot_cfg()["faq"]
        if 0 <= idx < len(faq):
            item = faq[idx]
            reply(chat_id, f"❓ <b>{item['q']}</b>\n\n{item['a']}",
                         reply_markup={"inline_keyboard": [
                             [{"text": "❓ Boshqa savollar", "callback_data": "menu:faq"}],
                             [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"}]]})
            log_action("ofis", "FAQ javobi berildi", item["q"][:60], chat_id)
    elif data == "menu:profile":
        u = users().get(str(chat_id), {})
        reply(chat_id, f"👤 <b>Sizning profilingiz</b>\n\n"
                       f"Ism: <b>{name or '—'}</b>\n"
                       f"Username: @{user.get('username','—')}\n"
                       f"ID: <code>{chat_id}</code>\n"
                       f"Ro'yxatdan o'tgan: {u.get('joined','—')}",
              reply_markup=back_keyboard())
    elif data == "menu:ofis":
        send_office(chat_id, True)
    elif data == "menu:calc":
        start_calc(chat_id)
    elif data == "menu:order":
        start_order(chat_id)
    # --- admin tugmalari ---
    elif data.startswith("adm:"):
        if user.get("id") != admin_id():
            return
        if data == "adm:log":
            handle_command(chat_id, "/log", "", user)
        elif data == "adm:agents":
            handle_command(chat_id, "/agents", "", user)
        elif data == "adm:orders":
            handle_command(chat_id, "/orders", "", user)


def send_portfolio(chat_id):
    items = bot_cfg().get("portfolio") or []
    if not items:
        reply(chat_id, "Namuna loyihalar hali yuklanmagan.", reply_markup=back_keyboard())
        return
    reply(chat_id, "🖼 <b>Namuna loyihalar</b>\n\nQuyida ishlarimizdan namunalar 👇")
    for item in items[:5]:
        if isinstance(item, dict):
            reply_photo(chat_id, item.get("photo", ""), item.get("caption", ""))
        else:
            reply_photo(chat_id, item, "")
    log_action("menejer", "namuna loyihalar yuborildi", f"{len(items)} ta rasm", chat_id)
    reply(chat_id,
                 f"Shu kabi loyihani sizga ham tayyorlab beramiz 😊\n"
                 f"📐 Narx: material kvadratiga {bot_cfg()['price_per_sqm']}$",
                 reply_markup={"inline_keyboard": [
                     [{"text": "✍️ Buyurtma berish", "callback_data": "menu:order"}],
                     [{"text": "⬅️ Asosiy menyu", "callback_data": "menu:main"}]]})


# --------------------------------------------------------------------------
# Kanal
# --------------------------------------------------------------------------
def handle_channel_message(msg):
    sf = bot_cfg().get("spam_filter") or {}
    if not sf.get("enabled") or not agent_on("ofis"):
        return
    text = (msg.get("text") or msg.get("caption") or "")
    if not text:
        return
    low = text.lower()
    if str(msg.get("from", {}).get("id", "")) in [str(x) for x in sf.get("exempt_users", [])]:
        return
    own = [str(CONFIG.get("channel", "")).lower(), USERNAME.lower()]
    if any(o and o in low for o in own):
        return
    if any(p.lower() in low for p in sf.get("patterns", [])):
        r = delete_message(TOKEN, msg["chat"]["id"], msg["message_id"])
        if r.get("ok"):
            touch_day(now_tz().date().isoformat(), "spam_deleted")
            log_action("ofis", "reklama o'chirildi", f"havola: {text[:50]}", msg["chat"]["id"])
        else:
            log.warning("O'chirib bo'lmadi: %s", r.get("description"))


def bot_mentioned(msg, bot_username=None):
    """Xabar botga qaratilganmi: @mention, javob (reply) yoki /komanda."""
    text = (msg.get("text") or msg.get("caption") or "")
    me = (bot_username if bot_username is not None else USERNAME or "").lstrip("@").lower()
    if me and ("@" + me) in text.lower():
        return True
    rp = msg.get("reply_to_message") or {}
    if (rp.get("from") or {}).get("id") == BOT_ID:
        return True
    if text.strip().startswith("/"):
        return True
    return False


def strip_mention(text, bot_username=None):
    me = (bot_username if bot_username is not None else USERNAME or "").lstrip("@")
    if not me:
        return text
    return re.sub(r"@" + re.escape(me) + r"\b", "", text, flags=re.I).strip()


def handle_group_message(msg):
    """Guruhdagi (kanal izohlari) xabarlar: reklamani o'chiradi va savolga javob beradi.

    Sozlamalar: config.json → bot.group
        enabled          — guruhda ishlash (standart: true)
        answer_questions — botga qaratilmagan savollarga ham javob berish (standart: false)
        notify_admin     — har bir guruh savolini adminga ham yuborish (standart: true)
    """
    g = bot_cfg().get("group") or {}
    if g.get("enabled", True) is False:
        return

    # 1) Reklama-havolalarni o'chirish (avvalgi vazifa)
    handle_channel_message(msg)

    # 2) Botga qaratilgan yoki savolga o'xshash xabar bo'lsa — javob beramiz
    chat_id = msg["chat"]["id"]
    user = msg.get("from") or {}
    if user.get("is_bot"):
        return
    if user.get("id") == BOT_ID:
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return

    mentioned = bot_mentioned(msg)
    clean = strip_mention(text) if mentioned else text
    norm = normalize(clean)
    is_question = looks_like_question(clean, norm)
    if not mentioned and not (g.get("answer_questions") and is_question):
        return

    answer, kb, agent, kind = keyword_answer(clean, norm)
    if not answer or not agent_on(agent):
        if agent_on("suhbat"):
            answer, kb = suhbat_reply(clean, norm, user.get("first_name", ""))[:2]
            agent, kind = "suhbat", "suhbat"
        else:
            return
    if not answer:
        return

    r = reply(chat_id, answer, reply_markup=kb, reply_to=msg.get("message_id"))
    if r.get("ok"):
        who = user.get("first_name") or user.get("username") or "mijoz"
        log_action(agent, "guruhda savolga javob berdi", f"{who}: «{clean[:50]}»", chat_id)
        if g.get("notify_admin", True):
            notify_admin(f"💬 <b>Guruhdagi savol</b> ({msg['chat'].get('title','guruh')})\n"
                         f"👤 {who}\n"
                         f"❓ {clean[:200]}\n\n"
                         f"<i>{agent_cfg(agent)['name']} javob berdi.</i>")
    else:
        log.warning("Guruhga javob yuborilmadi: %s", r.get("description"))


def handle_chat_member(upd):
    cm = upd.get("chat_member", {})
    new_status = (cm.get("new_chat_member") or {}).get("status")
    old_status = (cm.get("old_chat_member") or {}).get("status")
    if new_status not in ("member", "restricted") or old_status in ("member", "administrator", "creator"):
        return
    user = cm.get("new_chat_member", {}).get("user", {})
    touch_day(now_tz().date().isoformat(), "member_joins")
    log_action("postchi", "kanalga yangi a'zo qo'shildi", user.get("first_name", ""))
    if not bot_cfg().get("welcome_new_members"):
        return
    a = bot_cfg().get("address", {})
    text = (f"👋 Assalomu alaykum, {user.get('first_name','')}!\n\n"
            f"Kanalimizga qo'shilganingiz uchun rahmat.\n"
            f"🏢 ABK MEBEL — BAZIS loyiha (m² uchun {bot_cfg()['price_per_sqm']}$) va "
            f"FastReport shablonlari.\n")
    if a.get("plus_code"):
        text += f"📍 Manzil: {a.get('text') or a['plus_code']}\n🕘 {hours_text()}\n"
    text += "\nSavollaringiz bo'lsa shu botga yozing — javob beraman 😊"
    r = reply(user["id"], text, reply_markup=menu_keyboard())
    if not r.get("ok"):
        log.info("Kutib olish xabari yuborilmadi (a'zo botga yozmagan).")


# --------------------------------------------------------------------------
# Update'lar
# --------------------------------------------------------------------------
def handle_update(upd):
    try:
        if "message" in upd:
            msg = upd["message"]
            ctype = msg["chat"]["type"]
            if ctype == "private":
                handle_private_message(msg)
            elif ctype in ("group", "supergroup"):
                handle_group_message(msg)
            else:
                handle_channel_message(msg)
        elif "callback_query" in upd:
            handle_callback(upd["callback_query"])
        elif "chat_member" in upd:
            handle_chat_member(upd)
    except Exception as e:
        log.exception("Update xatosi: %s", e)


def process_updates(updates):
    if not updates:
        return 0
    count = 0
    max_offset = state().get("offset", 0)
    for upd in updates:
        try:
            handle_update(upd)
            max_offset = max(max_offset, upd.get("update_id", 0) + 1)
            count += 1
        except Exception as e:
            log.exception("Xato: %s", e)
    fresh = state()
    fresh["offset"] = max_offset
    save_state(fresh)
    check_reports()
    return count


ALLOWED = ALL_UPDATES


def run_once(timeout=0):
    r = get_updates(TOKEN, offset=state().get("offset", 0), timeout=timeout, allowed_updates=ALLOWED)
    if not r.get("ok"):
        log.error("getUpdates xatosi: %s", r.get("description"))
        return 0
    updates = r.get("result", [])
    n = process_updates(updates) if updates else 0
    if not updates:
        check_reports()
    log.info("Qayta ishlandi: %d ta update", n)
    return n


def run_once_window():
    """GitHub Actions rejimi: LISTEN_SECONDS davomida tinglaydi, keyin chiqadi.

    Bu usul botni Render'siz, faqat GitHub hisobi bilan 24/7 ishlatish imkonini beradi:
    har 5 daqiqada yangi ishga tushish 4-5 daqiqa tinglaydi — mijoz yozsa javob darhol ketadi.
    Webhook o'rnatilgan bo'lsa ishlamaydi (o'shanda Render ishlatilmoqda).
    """
    try:
        seconds = int(os.environ.get("LISTEN_SECONDS") or 0)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        return run_once(timeout=1)
    me = get_me(TOKEN)
    if me.get("ok"):
        globals()["BOT_ID"] = int(me["result"]["id"])
        log.info("GitHub rejimi: @%s — %d soniya tinglaymiz", me["result"].get("username"), seconds)
    else:
        log.error("Token tekshirilmadi: %s", me.get("description"))
        return 0
    deadline = time.time() + seconds
    total = 0
    while time.time() < deadline:
        try:
            r = get_updates(TOKEN, offset=state().get("offset", 0), timeout=25,
                            allowed_updates=ALLOWED)
        except Exception as e:
            log.error("Polling xatosi: %s", e)
            time.sleep(3)
            continue
        if not r.get("ok"):
            log.error("getUpdates xatosi: %s (webhook o'rnatilgan bo'lishi mumkin)",
                      r.get("description"))
            break
        updates = r.get("result", [])
        if updates:
            total += process_updates(updates)
        else:
            check_reports()
        try:
            import telegram_scheduler as ts
            ts.run_due(ts.load_config())
        except Exception as e:
            log.error("Post jadvali xatosi: %s", e)
    log.info("Tinglash tugadi: %d ta update qayta ishlandi.", total)
    return total


def set_bot_id():
    """Botning ID sini aniqlaydi (guruhda o'z xabarini tanib olishi uchun)."""
    global BOT_ID
    if BOT_ID:
        return BOT_ID
    me = get_me(TOKEN)
    if me.get("ok"):
        BOT_ID = int(me["result"]["id"])
        log.info("Bot ID: %s (@%s)", BOT_ID, me["result"].get("username"))
    return BOT_ID


def run_poll():
    me = get_me(TOKEN)
    if me.get("ok"):
        log.info("Bot ishga tushdi: @%s", me["result"].get("username"))
        globals()["BOT_ID"] = int(me["result"]["id"])
    else:
        log.error("Token tekshirilmadi: %s", me.get("description"))
    delete_webhook(TOKEN)
    log.info("AI-ofis ishga tushdi. Xodimlar: 🗂 reklama, 💬 sotuv, 🏢 ofis. To'xtatish: Ctrl+C")
    while True:
        try:
            r = get_updates(TOKEN, offset=state().get("offset", 0), timeout=25, allowed_updates=ALLOWED)
            if r.get("ok"):
                updates = r.get("result", [])
                if updates:
                    process_updates(updates)
                else:
                    check_reports()
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            log.info("To'xtatildi (Ctrl+C).")
            return
        except Exception as e:
            log.error("Polling xatosi: %s", e)
            time.sleep(5)


def reports_loop():
    while True:
        try:
            check_reports()
        except Exception as e:
            log.error("Hisobot xatosi: %s", e)
        time.sleep(60)


def posts_loop():
    """Webhook (Render) rejimida jadval bo'yicha kanalga post tashlab turadi.

    O'chirish: SCHEDULE_POSTS=0.  GitHub Actions ishlatilsa ham o'chirish mumkin
    (ikki joyda post ketmasligi uchun).
    """
    if os.environ.get("SCHEDULE_POSTS", "1").lower() in ("0", "false", "no", "off"):
        log.info("Post jadvali o'chirilgan (SCHEDULE_POSTS=0).")
        return
    try:
        import telegram_scheduler as ts
    except Exception as e:
        log.error("Post jadvali yuklanmadi: %s", e)
        return
    log.info("Post jadvali yoqildi — kanal: %s", (CONFIG or {}).get("channel", "?"))
    while True:
        try:
            cfg = ts.load_config()
            ts.run_due(cfg)
        except Exception as e:
            log.error("Post jadvali xatosi: %s", e)
        time.sleep(60)


# --------------------------------------------------------------------------
# Webhook + AI-ofis ilovasi
# --------------------------------------------------------------------------
class WebhookHandler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _query(self):
        q = {}
        try:
            from urllib.parse import parse_qs
            if "?" in self.path:
                q = {k: v[0] for k, v in parse_qs(self.path.split("?", 1)[1]).items()}
        except Exception:
            pass
        return q

    def office_allowed(self):
        """Ofis bo'limi FAQAT adminga (yoki to'g'ri ilova kaliti bilan) ochiladi."""
        q = self._query()
        tok = q.get("t") or self.headers.get("X-Office-Session") or ""
        uid = check_office_session(tok)
        if uid is not None and is_admin_user_id(uid):
            return True
        key = os.environ.get("OFFICE_KEY") or (bot_cfg().get("office_key") or "")
        supplied = self.headers.get("X-Office-Key") or q.get("k") or ""
        return bool(key) and supplied == key

    def do_GET(self):
        path = self.path.split("?")[0]
        q = self._query()
        if path.startswith("/ofis/data"):
            if not self.office_allowed():
                return self._send(403, json.dumps({"ok": False, "office_locked": True,
                                                   "reason": "faqat admin"},
                                                  ensure_ascii=False),
                                  "application/json; charset=utf-8")
            return self._send(200, json.dumps(build_office_data(), ensure_ascii=False),
                              "application/json; charset=utf-8")
        if path in ("/app", "/app/") or path.startswith("/app?"):
            import app_web
            allowed = self.office_allowed()
            tok = q.get("t") or ""
            if allowed and not tok:
                aid = admin_id()
                tok = make_office_session(aid) if aid else ""
            return self._send(200, app_web.render_app(build_office_data(), live=True,
                                                      admin=allowed, session=tok),
                              "text/html; charset=utf-8")
        if path.startswith("/app/panel"):
            import app_web
            if not self.office_allowed():
                return self._send(403, "🔒 faqat admin", "text/plain; charset=utf-8")
            return self._send(200, app_web._panel_section(build_office_data()),
                              "text/html; charset=utf-8")
        if path.startswith("/ofis"):
            import office_web
            if not self.office_allowed():
                return self._send(403, office_web.lock_html(), "text/html; charset=utf-8")
            return self._send(200, office_web.render_html(build_office_data(), live=True,
                                                          embed=bool(q.get("embed"))),
                              "text/html; charset=utf-8")
        return self._send(200, "🏢 ABK MEBEL AI-ofis ishlayapti. Ilova: /app")

    def do_POST(self):
        if self.path.split("?")[0].startswith("/app/me"):
            return self.app_me()
        if self.path.split("?")[0].startswith("/ofis/ask"):
            if not self.office_allowed():
                return self._send(403, json.dumps(
                    {"ok": False, "locked": True, "agent": "", "name": "AI-xodim", "emoji": "🔒",
                     "reply": "🔒 Ofis bo'limi faqat admin uchun. Mijozlar narx, manzil va "
                              "buyurtma bo'limlaridan foydalanadi.", "action": None},
                    ensure_ascii=False), "application/json; charset=utf-8")
            return self.office_ask()
        if not self.path.startswith("/webhook"):
            return self._send(404, "not found")
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if secret and self.headers.get("X-Telegram-Bot-Api-Secret-Token") != secret:
            return self._send(403, "forbidden")
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        self._send(200, '{"ok":true}', "application/json")
        try:
            threading.Thread(target=process_updates, args=([json.loads(raw.decode())],),
                             daemon=True).start()
        except Exception as e:
            log.error("Webhook xatosi: %s", e)

    def app_me(self):
        """Ilovadan kelgan initData ni tekshiradi: admin yoki oddiy mijoz?"""
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            payload = {}
        user = init_data_user(payload.get("initData") or payload.get("init_data") or "")
        if user and is_admin_user_id(user.get("id")):
            log.info("Ilova: ADMIN kirdi (%s, id=%s)", user.get("first_name"), user.get("id"))
            return self._send(200, json.dumps(
                {"ok": True, "admin": True, "name": user.get("first_name", ""),
                 "token": make_office_session(user.get("id"))}, ensure_ascii=False),
                "application/json; charset=utf-8")
        if user:
            log.info("Ilova: mijoz kirdi (%s, id=%s)", user.get("first_name"), user.get("id"))
        return self._send(200, json.dumps({"ok": True, "admin": False}, ensure_ascii=False),
                          "application/json; charset=utf-8")

    def office_ask(self):
        """Ilovadagi suhbat oynasidan kelgan savol/buyruq."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            payload = {}
        key = os.environ.get("OFFICE_KEY") or (bot_cfg().get("office_key") or "")
        supplied = self.headers.get("X-Office-Key") or ""
        allow = (not key) or (supplied == key)
        try:
            res = app_ask(payload.get("agent", ""), payload.get("text", ""), allow_commands=allow)
            if res.get("action"):
                log_action(res["agent"], "ilovadan buyruq bajarildi",
                           f"«{payload.get('text', '')[:60]}»", emoji="📱")
        except Exception as e:
            log.error("office_ask xatosi: %s", e)
            res = {"agent": payload.get("agent", ""), "name": "AI-xodim", "emoji": "🤖",
                   "reply": f"Kechirasiz, xatolik bo'ldi: {e}", "action": None}
        res["locked"] = not allow
        return self._send(200, json.dumps({"ok": True, **res}, ensure_ascii=False),
                          "application/json; charset=utf-8")

    def log_message(self, *args):
        pass


# --------------------------------------------------------------------------
# Ilovaga faqat ADMIN kira olishi (Telegram initData ni HMAC bilan tekshirish)
# --------------------------------------------------------------------------
def _sig(key: bytes, msg: str) -> str:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def init_data_user(init_data, max_age=86400):
    """Telegram Mini App «initData» ni tekshiradi. To'g'ri bo'lsa — foydalanuvchi."""
    if not init_data:
        return None
    try:
        from urllib.parse import parse_qsl
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None
    check_hash = pairs.pop("hash", "")
    if not check_hash:
        return None
    data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", TOKEN.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(_sig(secret, data_check), check_hash):
        log.warning("initData imzosi mos kelmadi")
        return None
    try:
        auth_date = int(pairs.get("auth_date") or 0)
        if max_age and auth_date and (time.time() - auth_date) > max_age:
            return None
        return json.loads(pairs.get("user") or "null")
    except Exception:
        return None


def make_office_session(user_id, ttl=86400):
    """Ofis bo'limi uchun qisqa muddatli kalit (imzo bilan)."""
    exp = int(time.time()) + int(ttl)
    return f"{user_id}.{exp}.{_sig(TOKEN.encode('utf-8'), f'{user_id}.{exp}')}"


def check_office_session(token):
    """Kalitni tekshiradi -> user_id yoki None."""
    if not token or token.count(".") != 2:
        return None
    uid, exp, sign = token.split(".")
    try:
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    if hmac.compare_digest(_sig(TOKEN.encode("utf-8"), f"{uid}.{exp}"), sign):
        try:
            return int(uid)
        except ValueError:
            return None
    return None


def is_admin_user_id(uid):
    aid = admin_id()
    return aid is not None and str(uid) == str(aid)


def run_webhook(port=None):
    global PUBLIC_URL
    port = int(port or os.environ.get("PORT", 8080))
    base = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL") or ""
    PUBLIC_URL = base.rstrip("/") if base else ""
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if base:
        url = PUBLIC_URL + "/webhook"
        r = set_webhook(TOKEN, url, secret_token=secret or None, allowed_updates=ALLOWED)
        log.info("Webhook: %s -> ok=%s", url, r.get("ok"))
        if PUBLIC_URL.startswith("https://"):
            log.info("AI-ofis ilovasi: %s/app  (eski: /ofis)", PUBLIC_URL)
    else:
        log.warning("WEBHOOK_URL topilmadi — webhook'ni qo'lda o'rnatasiz: "
                    "python3 bot_manager.py --set-webhook https://MANZIL/webhook")
    set_bot_id()
    if PUBLIC_URL.startswith("https://"):
        r = set_menu_button(TOKEN, PUBLIC_URL.rstrip("/") + "/app", "🏢 AI-Ofis")
        log.info("Menyu tugmasi (AI-Ofis ilovasi): ok=%s -> %s/app", r.get("ok"), PUBLIC_URL)
    threading.Thread(target=reports_loop, daemon=True).start()
    threading.Thread(target=posts_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), WebhookHandler)
    log.info("Server %d portda ishga tushdi (webhook + /ofis ilovasi).", port)
    server.serve_forever()


# --------------------------------------------------------------------------
# Holat
# --------------------------------------------------------------------------
def show_status():
    me = get_me(TOKEN)
    b = bot_cfg()
    st = state()
    today = now_tz().date().isoformat()
    d = st.get("days", {}).get(today, {})
    wh = get_webhook_info(TOKEN)
    print(f"\n🤖 Bot: @{me.get('result', {}).get('username', '?')} "
          f"({'✅' if me.get('ok') else '❌ ' + str(me.get('description'))})")
    print(f"📢 Kanal: {CONFIG.get('channel')}")
    print(f"👤 Admin ID: {b.get('admin_id') or '❌ sozlanmagan'}")
    print(f"💰 Narx: m² uchun {b.get('price_per_sqm')}$ | ⏰ Ish vaqti: {hours_text()}")
    print(f"📍 Manzil: {bot_cfg().get('address', {}).get('text') or '—'} "
          f"(Plus Code: {bot_cfg().get('address', {}).get('plus_code') or '—'})")
    print("\n🤖 AI-XODIMLAR:")
    for key in ("postchi", "menejer", "ofis", "suhbat"):
        a = agent_cfg(key)
        print(f"   {a['emoji']} {a['name']}: {'🟢 yoniq' if a.get('enabled', True) else '⏸ to`xtatilgan'}"
              f" — {a['role']}")
    print(f"\n👥 Foydalanuvchilar: {len(users())} | ✍️ Buyurtmalar: {len(orders())}")
    print(f"📊 Bugun: mijoz {d.get('new_users', 0)}, buyurtma {d.get('orders', 0)}, "
          f"murojaat {d.get('messages', 0)}")
    data = build_office_data(with_channel=False)
    print(f"\n🏢 AI-OFIS: {data['agents_working']} ta xodim ishda | "
          f"javob kutayotgan buyurtma: {data['pending_orders']}")
    for a in data["agents"]:
        print(f"   {a['emoji']} {a['name']}: {a['status_label']} — {a['task']}")
    print(f"\n🔗 Webhook: {wh.get('result', {}).get('url') or '— (long polling)'}")
    print(f"🎛 FAQ: {len(b['faq'])} · kalit so'z: {len(b['keywords'])} · "
          f"anketa qadamlari: {len(b['order_steps'])} · namuna rasm: {len(b['portfolio'])}\n")


def main():
    init()
    args = sys.argv[1:]
    if not args or "--poll" in args:
        run_poll()
    elif "--once" in args:
        run_once_window()
    elif "--webhook" in args:
        run_webhook()
    elif "--set-webhook" in args:
        r = set_webhook(TOKEN, args[args.index("--set-webhook") + 1],
                        secret_token=os.environ.get("WEBHOOK_SECRET") or None, allowed_updates=ALLOWED)
        print("Webhook o'rnatildi ✅" if r.get("ok") else f"Xatolik ❌ {r.get('description')}")
    elif "--delete-webhook" in args:
        r = delete_webhook(TOKEN)
        print("Webhook o'chirildi ✅" if r.get("ok") else f"Xatolik ❌ {r.get('description')}")
    elif "--report" in args:
        send_report("weekly" if "--weekly" in args else "daily")
        print("Hisobot yuborildi ✅")
    elif "--office" in args:
        print(json.dumps(build_office_data(), ensure_ascii=False, indent=2))
    elif "--status" in args:
        show_status()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
