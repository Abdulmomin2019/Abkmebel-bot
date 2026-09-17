#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tg_api.py — Telegram Bot API bilan ishlash uchun umumiy modul.
Faqat standart kutubxonalar ishlatiladi (pip install kerak emas).

Bu modulni telegram_scheduler.py (post tashlovchi) va bot_manager.py (menejer bot)
birgalikda ishlatadi.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request

log = logging.getLogger("tgapi")

DEFAULT_BASE = "https://api.telegram.org"
TELEGRAM_LIMIT = 4000  # Telegram chegarasi 4096 belgi


def api_base():
    # Sinov paytida TG_API_BASE orqali boshqa manzilga yo'naltirish mumkin
    return os.environ.get("TG_API_BASE", DEFAULT_BASE)


# --------------------------------------------------------------------------
# Asosiy so'rov
# --------------------------------------------------------------------------
def _request(token, method, data=None, headers=None, timeout=60):
    url = f"{api_base()}/bot{token}/{method}"
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        log.error("Telegram API xatosi (%s): %s", method, detail)
        try:
            return json.loads(detail)
        except Exception:
            return {"ok": False, "description": detail}
    except Exception as e:
        log.error("Tarmoq xatosi (%s): %s", method, e)
        return {"ok": False, "description": str(e)}


def api_json(token, method, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    return _request(token, method, data, {"Content-Type": "application/json"}, timeout=timeout)


def _multipart(fields, file_field, filename, content, ctype):
    boundary = "----TSBoundary" + str(int(time.time() * 1000))
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                 f"{v}\r\n").encode("utf-8")
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
             f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n").encode("utf-8")
    body += content + b"\r\n" + f"--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


# --------------------------------------------------------------------------
# Xabar yuborish
# --------------------------------------------------------------------------
def split_text(text, limit=TELEGRAM_LIMIT):
    """Uzun matnni Telegram chegarasiga mos bo'laklarga bo'ladi."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for para in text.split("\n"):
        candidate = (current + "\n" + para) if current else para
        if len(candidate) > limit:
            if current:
                parts.append(current)
            while len(para) > limit:
                parts.append(para[:limit])
                para = para[limit:]
            current = para
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def send_message(token, chat_id, text, disable_preview=True, reply_markup=None):
    """Matn yuboradi. HTML belgilari xato bersa — oddiy matn sifatida qayta urinadi."""
    last = None
    for chunk in split_text(text):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_preview,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = api_json(token, "sendMessage", payload)
        if not result.get("ok"):
            desc = str(result.get("description", "")).lower()
            if "parse" in desc or "entity" in desc:
                log.warning("HTML belgilarida xato — oddiy matn sifatida qayta yuborilmoqda.")
                payload.pop("parse_mode")
                result = api_json(token, "sendMessage", payload)
        last = result
        if not result.get("ok"):
            break
    return last or {"ok": False, "description": "Bo'sh matn"}


def send_photo(token, chat_id, photo, caption="", reply_markup=None, base_dir="."):
    """Rasm yuboradi. photo — lokal fayl yo'li yoki internet havola."""
    if str(photo).startswith("http://") or str(photo).startswith("https://"):
        payload = {"chat_id": chat_id, "photo": photo, "caption": caption[:1024], "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return api_json(token, "sendPhoto", payload)

    full = photo if os.path.isabs(photo) else os.path.join(base_dir, photo)
    if not os.path.exists(full):
        log.warning("Rasm topilmadi: %s — faqat matn yuboriladi.", full)
        return send_message(token, chat_id, caption, reply_markup=reply_markup)

    with open(full, "rb") as f:
        content = f.read()
    ctype = "image/png" if full.lower().endswith(".png") else "image/jpeg"
    fields = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "HTML"}
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup)
    body, ct = _multipart(fields, "photo", os.path.basename(full), content, ctype)
    return _request(token, "sendPhoto", body, {"Content-Type": ct})


def send_document(token, chat_id, doc, caption="", reply_markup=None, base_dir="."):
    """Fayl (PDF, hujjat) yuboradi."""
    full = doc if os.path.isabs(doc) else os.path.join(base_dir, doc)
    if not os.path.exists(full):
        return {"ok": False, "description": "fayl topilmadi: %s" % doc}
    with open(full, "rb") as f:
        content = f.read()
    ext = os.path.splitext(full)[1].lower()
    ctype = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             ".zip": "application/zip"}.get(ext, "application/octet-stream")
    fields = {"chat_id": str(chat_id)}
    if caption:
        fields["caption"] = caption
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    body, ct = _multipart(fields, "document", os.path.basename(full), content, ctype)
    return _request(token, "sendDocument", body, {"Content-Type": ct}, timeout=180)


def send_location(token, chat_id, latitude, longitude, reply_markup=None):
    """Joylashuvni (lokatsiya) xarita belgisi sifatida yuboradi."""
    payload = {"chat_id": chat_id, "latitude": float(latitude), "longitude": float(longitude)}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return api_json(token, "sendLocation", payload)


def send_chat_action(token, chat_id, action="typing"):
    return api_json(token, "sendChatAction", {"chat_id": chat_id, "action": action})


# --------------------------------------------------------------------------
# Boshqa metodlar
# --------------------------------------------------------------------------
def get_updates(token, offset=None, timeout=25, allowed_updates=None, limit=100):
    payload = {"timeout": timeout, "limit": limit}
    if offset is not None:
        payload["offset"] = offset
    if allowed_updates:
        payload["allowed_updates"] = allowed_updates
    return api_json(token, "getUpdates", payload, timeout=timeout + 20)


def answer_callback_query(token, callback_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text[:200]
    if show_alert:
        payload["show_alert"] = True
    return api_json(token, "answerCallbackQuery", payload)


def edit_message_text(token, chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return api_json(token, "editMessageText", payload)


def delete_message(token, chat_id, message_id):
    return api_json(token, "deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def forward_message(token, chat_id, from_chat_id, message_id):
    return api_json(token, "forwardMessage", {
        "chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id,
    })


def get_chat(token, chat_id):
    return api_json(token, "getChat", {"chat_id": chat_id})


def get_chat_member(token, chat_id, user_id):
    return api_json(token, "getChatMember", {"chat_id": chat_id, "user_id": user_id})


def get_chat_member_count(token, chat_id):
    return api_json(token, "getChatMemberCount", {"chat_id": chat_id})


def get_me(token):
    return api_json(token, "getMe", {})


def set_menu_button(token, url=None, text="🏢 AI-Ofis", chat_id=None):
    """Botning chap pastdagi menyu tugmasini Web App ga bog'laydi."""
    if url:
        payload = {"menu_button": {"type": "web_app", "text": text,
                                   "web_app": {"url": url}}}
    else:
        payload = {"menu_button": {"type": "default"}}
    if chat_id:
        payload["chat_id"] = chat_id
    return api_json(token, "setChatMenuButton", payload)


def set_webhook(token, url, secret_token=None, allowed_updates=None):
    payload = {"url": url, "drop_pending_updates": True}
    if secret_token:
        payload["secret_token"] = secret_token
    if allowed_updates:
        payload["allowed_updates"] = allowed_updates
    return api_json(token, "setWebhook", payload)


def delete_webhook(token):
    return api_json(token, "deleteWebhook", {"drop_pending_updates": False})


def get_webhook_info(token):
    return api_json(token, "getWebhookInfo", {})


ALL_UPDATES = ["message", "callback_query", "chat_member", "my_chat_member", "edited_message"]


# --------------------------------------------------------------------------
# PREMIUM (custom) EMOJI
# --------------------------------------------------------------------------
# Telegram qoidasi (Bot API 9.4, 2026-yil 9-fevral):
#   «Custom emoji entities can only be used by bots that purchased additional
#    usernames on Fragment or in the messages directly sent by the bot to
#    private, group and supergroup chats if the owner of the bot has a
#    Telegram Premium subscription.»
# Ya'ni: bot egasida Premium bo'lsa — bot SHAXSIY va GURUH chatlarida premium
# emojilarni yubora oladi. Kanallar ro'yxatda yo'q — u yerda Telegram oddiy
# emojiga qaytaradi, shuning uchun kod avtomatik "fallback" qiladi.

def utf16_offset(text, index):
    """Python indeksini Telegram kutayotgan UTF-16 offsetga o'giradi."""
    return len(text[:index].encode("utf-16-le")) // 2 - index  # faqat surrogate juftliklar uchun


def _offset_map(text):
    """Har bir belgi indeksi uchun UTF-16 offsetini hisoblaydi."""
    offsets, cur = [], 0
    for ch in text:
        offsets.append(cur)
        cur += len(ch.encode("utf-16-le")) // 2
    offsets.append(cur)
    return offsets


def build_custom_emoji_entities(text, emoji_map):
    """Matndagi premium emojilarga mos `custom_emoji` entity'larini yasaydi.

    emoji_map: {"⚡": "5368324170671202286", "🔥": "..."} — bot_manager ularni
    admin yuborgan xabarlardan o'rganib oladi.
    """
    if not emoji_map:
        return []
    offsets = _offset_map(text)
    entities = []
    for i, ch in enumerate(text):
        emoji_id = emoji_map.get(ch)
        if not emoji_id:
            continue
        entities.append({
            "type": "custom_emoji",
            "offset": offsets[i],
            "length": len(ch.encode("utf-16-le")) // 2,
            "custom_emoji_id": str(emoji_id),
        })
    return entities


def extract_custom_emojis(message):
    """Kelgan xabardan premium emojilarni ajratib oladi: {"⚡": "5368..."}.

    Admin botga premium emoji yuborsa — bot uni o'rganib, keyin o'zi hammaga
    shunday emoji bilan yozadi.
    """
    text = message.get("text") or message.get("caption") or ""
    ents = message.get("entities") or message.get("caption_entities") or []
    found = {}
    for e in ents:
        if e.get("type") != "custom_emoji":
            continue
        start = e.get("offset", 0)
        length = e.get("length", 0)
        # UTF-16 offset -> Python indeks
        prefix = text.encode("utf-16-le")[:start * 2].decode("utf-16-le", "ignore")
        segment = text.encode("utf-16-le")[start * 2:(start + length) * 2].decode("utf-16-le", "ignore")
        if segment:
            found[segment] = e.get("custom_emoji_id")
    return found


def _is_emoji_error(result):
    desc = str(result.get("description", "")).lower()
    return ("custom_emoji" in desc.replace(" ", "_") or "custom emoji" in desc
            or "emoji" in desc and "not" in desc)


def send_message_rich(token, chat_id, text, entities=None, reply_markup=None,
                      disable_preview=True, reply_to=None):
    """Matn + entity (premium emoji, spoiler va h.k.) yuboradi.
    Premium emoji rad etilsa — oddiy emojilar bilan qayta yuboradi."""
    def payload_with(ents, plain=False):
        p = {"chat_id": chat_id, "text": text, "disable_web_page_preview": disable_preview}
        if ents and not plain:
            p["entities"] = ents
        else:
            p["parse_mode"] = "HTML"
        if reply_markup:
            p["reply_markup"] = reply_markup
        if reply_to:
            p["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        return p

    result = api_json(token, "sendMessage", payload_with(entities))
    if not result.get("ok") and entities and _is_emoji_error(result):
        log.info("Premium emoji qabul qilinmadi — oddiy ko'rinishda yuborilmoqda.")
        result = api_json(token, "sendMessage", payload_with(None, plain=False))
    return result


def send_photo_rich(token, chat_id, photo, caption="", entities=None, reply_markup=None,
                    base_dir=".", reply_to=None):
    """Rasm + premium emojili izoh. Premium rad etilsa — oddiy izoh bilan yuboriladi."""
    if str(photo).startswith("http://") or str(photo).startswith("https://"):
        payload = {"chat_id": chat_id, "photo": photo, "caption": caption[:1024]}
        if entities:
            payload["caption_entities"] = entities
        else:
            payload["parse_mode"] = "HTML"
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return api_json(token, "sendPhoto", payload)

    full = photo if os.path.isabs(photo) else os.path.join(base_dir, photo)
    if not os.path.exists(full):
        return send_message_rich(token, chat_id, caption, entities, reply_markup)
    with open(full, "rb") as f:
        content = f.read()
    ctype = "image/png" if full.lower().endswith(".png") else "image/jpeg"
    fields = {"chat_id": chat_id, "caption": caption[:1024]}
    if entities:
        fields["caption_entities"] = json.dumps(entities)
    else:
        fields["parse_mode"] = "HTML"
    if reply_markup:
        fields["reply_markup"] = json.dumps(reply_markup)
    body, ct = _multipart(fields, "photo", os.path.basename(full), content, ctype)
    return _request(token, "sendPhoto", body, {"Content-Type": ct})
