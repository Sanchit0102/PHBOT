import os
import re
import html
import yt_dlp
import asyncio
import logging
import aiohttp
import requests
import tempfile
import threading
from PIL import Image
from uuid import uuid4
from search import search
from bs4 import BeautifulSoup
from pyrogram.enums import ParseMode
from pyrogram import Client, filters, idle
from extractor import StreamingURLExtractor
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent
)

# ==========================================================================================================
# CONFIG (ENV)
# ==========================================================================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", 1562935405))
DELETE_TIME = int(os.environ.get("DELETE_TIME", "300"))
PORT = int(os.environ.get("PORT", 8080))

STICKER_ID = "CAACAgEAAxkBAAK6kGlLoJrwgP6Y-FBjv1N0ZHJ_aohvAAI6AgACLeX5Ddv34qRmNpJZNgQ"
START_IMAGE = "https://image.ashlynn.workers.dev/zixawvbuvrlejcxetoneaqhrikbgxugi"

INLINE_META = {}
STREAM_MAP = {}
USER_BUSY = set()
# URL_RE = re.compile(r"https://(?:www\.|de\.)?pornhub\.org/view_video\.php\?viewkey=[a-zA-Z0-9]+")

# ==========================================================================================================
# LOGGING & APP
# ==========================================================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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

app = Client(
    "ds_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ==========================================================================================================
# ==========================================================================================================

def get_viewkey(url: str):
    m = re.search(r"viewkey=([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None

def cap(title, duration, quality_url, bot_username, filesize, quality):
    title = html.escape(title or "Video")
    duration = duration or "N/A"
    quality_url = html.escape(quality_url)

    return (
        f"📄 <b>𝖥𝗂𝗅𝖾 𝖭𝖺𝗆𝖾:</b> <code>{title}</code>\n\n"
        f"🔗 <b>𝖶𝖺𝗍𝖼𝗁 𝖮𝗇𝗅𝗂𝗇𝖾:</b> <a href=\"{quality_url}\">Click Here</a>\n"
        f"⏰ <b>𝖣𝗎𝗋𝖺𝗍𝗂𝗈𝗇:</b> {duration}\n"
        f"📦 <b>𝖥𝗂𝗅𝖾 𝖲𝗂𝗓𝖾:</b> {filesize}\n"
        f"🎞 <b>𝖰𝗎𝖺𝗅𝗂𝗍𝗒:</b> {quality}\n\n"
        f"⚡ <b>𝖴𝗉𝗅𝗈𝖺𝖽 𝖡𝗒:</b> <a href=\"https://t.me/{html.escape(bot_username)}\">𝖣𝖲𝖠𝖽𝗎𝗅𝗍𝖡𝗈𝗍 🔞</a>"
    )
    
def human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
    
async def download_poster(url: str):
    if not url:
        return None

    tmp = os.path.join(tempfile.gettempdir(), f"thumb_{uuid4().hex}.jpg")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as r:
                if r.status == 200:
                    with open(tmp, "wb") as f:
                        f.write(await r.read())
                    return tmp
    except Exception:
        return None
    return None

# ==========================================================================================================

async def upload_hls_to_telegram(app: Client, message, url, title=None, duration=None, poster=None, quality=None):
    temp = tempfile.gettempdir()
    base = os.path.join(temp, f"dl_{uuid4().hex}")

    ydl_opts = {
        "format": "best",
        "outtmpl": base + ".%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "concurrent_fragment_downloads": 8,
        "http_chunk_size": 10 * 1024 * 1024,
        "no_warnings": True,
        "downloader": "ffmpeg",
        "hls_use_mpegts": True,
        "live_from_start": True,
    }
    
    def run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    await asyncio.to_thread(run)

    files = [f for f in os.listdir(temp) if f.startswith(os.path.basename(base))]
    video = os.path.join(temp, files[0])
    me = await app.get_me()
    thumb_path = await download_poster(poster)
    if thumb_path:
        try:
            img = Image.open(thumb_path)
            img.thumbnail((320, 320))
            img.save(thumb_path, "JPEG", quality=85)
        except Exception:
            thumb_path = None

    duration_str = duration 
    duration_sec = None
    user_id = message.from_user.id

    if duration and ":" in duration:
        m, s = duration.split(":")
        duration_sec = int(m) * 60 + int(s)

    send_kwargs = {
        "chat_id": user_id,
        "video": video,
        "caption": "Loading...",
        "supports_streaming": True,
        "parse_mode": ParseMode.HTML,
    }

    if duration_sec is not None:
        send_kwargs["duration"] = duration_sec

    if thumb_path:
        send_kwargs["thumb"] = thumb_path

    sent = await app.send_video(**send_kwargs)

    video_obj = sent.video or sent.document
    filesize = human_size(video_obj.file_size)

    await sent.edit_caption(
        cap(
            title=title,
            duration=duration_str,
            quality_url=url,
            bot_username=me.username or "THE_DS_OFFICIAL_BOT",
            filesize=filesize,
            quality=quality,
        ),
        parse_mode=ParseMode.HTML
    )
    
    delmsg = await app.send_message(
    chat_id=message.chat.id,
    text=f"❗️❗️❗️ <b>IMPORTANT</b> ❗️❗️❗️\n\nᴛʜɪꜱ ꜰɪʟᴇ / ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b>{DELETE_TIME // 60} Mɪɴᴜᴛᴇꜱ</b> ⏰ (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\nᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ᴛᴏ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛʜᴇʀᴇ.",
    parse_mode=ParseMode.HTML
    )
    
    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)
    
    USER_BUSY.discard(user_id)

    await asyncio.sleep(DELETE_TIME)
    
    await sent.delete()
    await delmsg.edit_text("<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!</b>")
    
    try:
        os.remove(video)
    except Exception:
        pass

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
