import os
import re
import asyncio
import logging
from uuid import uuid4

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram.types import ReplyKeyboardRemove
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

STICKER_ID = "CAACAgEAAxkBAAK6kGlLoJrwgP6Y-FBjv1N0ZHJ_aohvAAI6AgACLeX5Ddv34qRmNpJZNgQ"
START_IMAGE = "https://image.ashlynn.workers.dev/zixawvbuvrlejcxetoneaqhrikbgxugi"

INLINE_META = {}
STREAM_MAP = {}
USER_BUSY = set()

URL_RE = re.compile(r"https?://\S+")
PORT = int(os.environ.get("PORT", "8080"))

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

@app.on_message()
async def handler(client, message):
    await message.reply_text(
        "\u200b",
        reply_markup=ReplyKeyboardRemove()
    )

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

        INLINE_META[url] = {
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

    info = STREAM_MAP.pop(data)
    user_id = cb.from_user.id

    if user_id in USER_BUSY:
        return await cb.answer("Already processing", show_alert=True)

    USER_BUSY.add(user_id)

    try:
        await cb.answer()
        try:
            await cb.message.delete()
        except Exception:
            pass

        title = info.get("title") or "Video"
        duration = info.get("duration") or "N/A"
        poster = info.get("poster")
        page = info["page"]
        stream_url = info["videoUrl"]

        msg = await app.send_message(cb.message.chat.id, "Processing...")

        extractor = StreamingURLExtractor(page)
        final_url = extractor.resolve_stream_url(stream_url)

        await upload_hls_to_telegram(
            app,
            cb.message,
            final_url,
            title=title,
            duration=duration,
            poster=poster,
        )

        await msg.delete()

    finally:
        USER_BUSY.discard(user_id)

# ==========================================================================================================
# START
# ==========================================================================================================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(_, message):
    caption = f"""
<b>Hello {message.from_user.first_name}</b>

━━━━━━━━━━━━━━━━━━━━━

<code>⚠ Tʜᴇ Bᴏᴛ Cᴏɴᴛᴀɪɴs 18+ Cᴏɴᴛᴇɴᴛ. Kɪɴᴅʟʏ Aᴄᴄᴇss ɪᴛ Aᴛ Yᴏᴜʀ Oᴡɴ Rɪsᴋ. Cʜɪʟᴅʀᴇɴ Pʟᴇᴀsᴇ Sᴛᴀʏ Aᴡᴀʏ. Wᴇ ᴅᴏɴ'ᴛ ɪɴᴛᴇɴᴅ ᴛᴏ sᴘʀᴇᴀᴅ Pᴏʀɴᴏɢʀᴀᴘʜʏ. Tʜɪs ɪs ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴀɴᴅ ᴘᴜʀᴘᴏsᴇ-ʙᴀsᴇᴅ.</code>

━━━━━━━━━━━━━━━━━━━━━
<b>👨🏻‍💻 Developed By @THE_DS_OFFICIAL</b>

"""
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Search 🔎", switch_inline_query_current_chat=" ")
        ]]
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

    if m.from_user.id in USER_BUSY:
        await m.reply("Wait for current task to finish")
        return

    extractor = StreamingURLExtractor(m.text)
    streams = extractor.extract_streaming_urls()

    if not streams:
        await m.reply("No streams found")
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
        STREAM_MAP[sid] = {
            "page": m.text,
            "videoUrl": s["videoUrl"],
            "title": s.get("title") or "Video",
            "duration": s.get("duration") or "N/A",
            "poster": s.get("poster"),
        }

        row.append(InlineKeyboardButton(f"◂ {h}p ▸", callback_data=sid))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await m.reply(
        "🎬 Select Quality 🎬",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==========================================================================================================
# RUN
# ==========================================================================================================

if __name__ == "__main__":
    app.start()
    idle()
    app.stop()
