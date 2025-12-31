import os
import re
import asyncio
import logging
from uuid import uuid4

import requests
from bs4 import BeautifulSoup

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent
)

from extractor import StreamingURLExtractor
from search import search
from dl_ul_to_tg import upload_hls_to_telegram

# ==========================================================================================================
# CONFIG (ENV)
# ==========================================================================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", 1562935405))

STICKER_ID = "CAACAgEAAxkBAAK6kGlLoJrwgP6Y-FBjv1N0ZHJ_aohvAAI6AgACLeX5Ddv34qRmNpJZNgQ"
START_IMAGE = "https://image.ashlynn.workers.dev/zixawvbuvrlejcxetoneaqhrikbgxugi"

INLINE_META = {}
STREAM_MAP = {}
USER_BUSY = set()

# 0URL_RE = re.compile(r"https?://\S+")
URL_RE = re.compile(r"https://(?:www\.|de\.)?pornhub\.org/view_video\.php\?viewkey=[a-zA-Z0-9]+")
PORT = int(os.environ.get("PORT", 8080))

def get_viewkey(url: str):
    m = re.search(r"viewkey=([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None
    
# ======================================================================================
# Dummy HTTP server (ONLY for Render Web Service)
# ======================================================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def start_health_server():
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

threading.Thread(target=start_health_server, daemon=True).start()

# ==========================================================================================================
# LOGGING
# ==========================================================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ==========================================================================================================
# APP
# ==========================================================================================================

app = Client(
    "ds_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ==========================================================================================================
# INLINE SEARCH
# ==========================================================================================================

@app.on_inline_query()
async def inline_query_handler(_, q):
    if not q.query:
        return

    results = []

    for r in search(q.query):
        url = r["url"]
        title = r.get("title") or "Video"
        duration = r.get("duration") or "N/A"
        poster = r.get("poster")

        vk = get_viewkey(url)
        if vk:
            INLINE_META[vk] = {
                "title": title,
                "duration": duration,
                "poster": poster,
            }

        results.append(
            InlineQueryResultArticle(
                id=uuid4().hex,
                title=title,
                description=f"Duration: {duration}",
                thumb_url=poster,
                input_message_content=InputTextMessageContent(url),
            )
        )

    await q.answer(results, cache_time=1)

# ==========================================================================================================
# CALLBACK
# ==========================================================================================================

@app.on_callback_query()
async def callback_handler(_, cb):
    data = cb.data
    if data not in STREAM_MAP:
        return

    info = STREAM_MAP[data]   
    user_id = cb.from_user.id

    if user_id in USER_BUSY:
        return await cb.answer("Already processing", show_alert=True)

    USER_BUSY.add(user_id)
    processing_msg = None
    sticker_msg = None
    chat_id = cb.message.chat.id

    try:
        await cb.answer()

        try:
            await cb.message.delete()
        except Exception:
            pass
            
        page = info["page"]
        title = info["title"]
        duration = info["duration"]
        poster = info["poster"]
        quality = f"{info['height']}p"
        stream_url = info["videoUrl"]
        
        processing_msg = await app.send_message(
            chat_id,
            "Processing your request..."
        )

        sticker_msg = await app.send_sticker(
            chat_id,
            STICKER_ID
        )

        extractor = StreamingURLExtractor(page)
        final_url = extractor.resolve_stream_url(stream_url)

        await upload_hls_to_telegram(
            app,
            cb.message,   
            final_url,
            title=title.strip() if title else "N/A",
            duration=duration,
            poster=poster,
            quality=quality,
        )

    finally:
        try:
            if processing_msg:
                await processing_msg.delete()
        except Exception:
            pass

        try:
            if sticker_msg:
                await sticker_msg.delete()
        except Exception:
            pass
        USER_BUSY.discard(user_id)
        STREAM_MAP.pop(data, None)  
# ==========================================================================================================
# START
# ==========================================================================================================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(_, message):
    caption = f"""
<b>Hᴇʟʟᴏ, {message.from_user.first_name}</b>

━━━━━━━━━━━━━━━━━━━━━

<code>⚠ Tʜᴇ Bᴏᴛ Cᴏɴᴛᴀɪɴs 18+ Cᴏɴᴛᴇɴᴛ. Kɪɴᴅʟʏ Aᴄᴄᴇss ɪᴛ Aᴛ Yᴏᴜʀ Oᴡɴ Rɪsᴋ. Cʜɪʟᴅʀᴇɴ Pʟᴇᴀsᴇ Sᴛᴀʏ Aᴡᴀʏ. Wᴇ ᴅᴏɴ'ᴛ ɪɴᴛᴇɴᴅ ᴛᴏ sᴘʀᴇᴀᴅ Pᴏʀɴᴏɢʀᴀᴘʜʏ. Tʜɪs ɪs ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴀɴᴅ ᴘᴜʀᴘᴏsᴇ-ʙᴀsᴇᴅ.</code>

━━━━━━━━━━━━━━━━━━━━━
<b>👨🏻‍💻 Dᴇᴠᴇʟᴏᴘᴇᴅ Bʏ @THE_DS_OFFICIAL</b>
"""

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Search 🔎", switch_inline_query_current_chat=" ")]]
    )

    await message.reply_photo(
        photo=START_IMAGE,
        caption=caption,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# ==========================================================================================================
# URL HANDLER
# ==========================================================================================================

@app.on_message(filters.private & filters.text & ~filters.regex(r'^/'))
async def url_handler(_, m):
    if not m.text.startswith("http"):
        return

    vk = get_viewkey(m.text)
    if vk and vk not in INLINE_META:
        r = requests.get(m.text, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        dur = soup.find("meta", property="video:duration")
        duration = None
        if dur and dur.get("content"):
            sec = int(dur["content"])
            duration = f"{sec//60}:{sec%60:02d}"

        INLINE_META[vk] = {
            "title": (soup.find("meta", property="og:title") or {}).get("content"),
            "poster": (soup.find("meta", property="og:image") or {}).get("content"),
            "duration": duration,
        }
    
    if m.from_user.id in USER_BUSY:
        await m.reply("<b>Wait for current task to finish</b>")
        return

    extractor = StreamingURLExtractor(m.text)
    streams = extractor.extract_streaming_urls()

    if not streams:
        await m.reply("No data found")
        return

    buttons = []
    row = []

    for s in streams:
        h = s.get("height")
        if not h or not s.get("videoUrl"):
            continue
        if int(h) < 144 or int(h) > 1080:
            continue

        sid = uuid4().hex[:12]
        meta = INLINE_META.get(vk, {})

        STREAM_MAP[sid] = {
            "page": m.text,
            "videoUrl": s["videoUrl"],
            "title": meta.get("title") if meta else "Video",
            "duration": meta.get("duration") if meta else "N/A",
            "poster": meta.get("poster") if meta else None,
            "height": h,
        }

        row.append(InlineKeyboardButton(f"◂ {h}p ▸", callback_data=sid))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await m.reply(
        "◆━━━━━━━━━━━━◆\n"
        "🎬 <b>𝖲𝖾𝗅𝖾𝖼𝗍 𝖰𝗎𝖺𝗅𝗂𝗍𝗒</b> 🎬\n"
        "◆━━━━━━━━━━━━◆",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==========================================================================================================
# RUN
# ==========================================================================================================

if __name__ == "__main__":
    app.start()

    app.send_message(
        chat_id=OWNER_ID,
        text="𝐁𝐎𝐓 𝐑𝐄𝐒𝐓𝐀𝐑𝐓𝐄𝐃 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘 ✅"
    )

    idle()
    app.stop()
