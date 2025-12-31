import os
import re
import html
import time 
import yt_dlp
import asyncio
import logging
import aiohttp
import datetime
import requests
import tempfile
import threading
from PIL import Image
from uuid import uuid4
from search import search
from db import db, adds_user, LOG_CHANNEL_ID
from bs4 import BeautifulSoup
from pyrogram.enums import ParseMode
from pyrogram import Client, filters, idle, utils as pyroutils
from extractor import StreamingURLExtractor
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, UserIsBot
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent
)

# ==========================================================================================================
# CONFIG (ENV)
# ==========================================================================================================
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", 1562935405))

STICKER_ID = "CAACAgEAAxkBAAK6kGlLoJrwgP6Y-FBjv1N0ZHJ_aohvAAI6AgACLeX5Ddv34qRmNpJZNgQ"
START_IMAGE = "https://image.ashlynn.workers.dev/zixawvbuvrlejcxetoneaqhrikbgxugi"
DELETE_TIME = int(os.environ.get("DELETE_TIME", "300"))
PORT = int(os.environ.get("PORT", 8080))

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
# HELPERS
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
# def run():
        # with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ydl.download([url])
async def upload_hls_to_telegram(app: Client, message, user, user_id: int, url, title=None, duration=None, poster=None, quality=None):
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
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    video = await asyncio.to_thread(run)

    if not video or not os.path.exists(video):
        raise RuntimeError("Download failed: video file not created")
    
    files = [f for f in os.listdir(temp) if f.startswith(os.path.basename(base))]
    video = os.path.join(temp, files[0])
    me = await app.get_me()
    bot_username = me.username

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
    file_code = uuid4().hex[:10]
   
    getfile_btn = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🔁 Get File Again 🔁", url=f"https://t.me/{bot_username}?start=DS_{file_code}")
        ]]
        )

    share_btn = InlineKeyboardMarkup(
        [[  
            InlineKeyboardButton("🔗 Share Video 🔗", url=f"https://t.me/share/url?url=https://t.me/{bot_username}?start=DS_{file_code}")
        ]]
        )
    
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
        reply_markup=share_btn,
        parse_mode=ParseMode.HTML
    )
    
    delmsg = await app.send_message(
    chat_id=user_id,
    text=f"❗️❗️❗️ <b>IMPORTANT</b> ❗️❗️❗️\n\nᴛʜɪꜱ ꜰɪʟᴇ / ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b>{DELETE_TIME // 60} Mɪɴᴜᴛᴇꜱ</b> ⏰ (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\nᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ᴛᴏ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛʜᴇʀᴇ.",
    parse_mode=ParseMode.HTML
    )
    
    sent = await app.get_messages(
               chat_id=sent.chat.id,
               message_ids=sent.id
           )

    try:
        log_msg = await sent.copy(chat_id=LOG_CHANNEL_ID)
    except (UserIsBot, PeerIdInvalid):
        logging.error("LOG_CHANNEL_ID is a bot or invalid")
        log_msg = None
    

    try:
        await app.send_message(
            LOG_CHANNEL_ID,
            text=(
                f"Requested by: @{user.username or 'N/A'}\n"
                f"Name: {user.first_name}\n"
                f"User ID: {user.id}\n"
                f"File Code: {file_code}"
            ),
            reply_to_message_id=log_msg.id
        )
    except UserIsBot:
        logging.error("Cannot send log message to bot")

    if log_msg:
        await db.save_file(file_code, log_msg.id)

    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)
    
    USER_BUSY.discard(user_id)

    await asyncio.sleep(DELETE_TIME)
    
    await sent.delete()
    await delmsg.edit_text(
        "<b>ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=getfile_btn,
        )
    
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
    if cb.from_user.is_bot:
        return await cb.answer("Bots are not allowed", show_alert=True)

    data = cb.data
    if data not in STREAM_MAP:
        return

    info = STREAM_MAP[data]   
    user_id = cb.from_user.id

    if await db.is_banned(user_id):
        USER_BUSY.discard(user_id)
        return await cb.answer("You are banned", show_alert=True)
    
    if user_id in USER_BUSY:
        return await cb.answer("Already processing", show_alert=True)

    USER_BUSY.add(user_id)
    chat_id = cb.message.chat.id

    try:
        await cb.answer()
        await cb.message.delete()
            
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
            cb.from_user,  
            cb.from_user.id,
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
    user = message.from_user
    await adds_user(app, message)

    # ban check
    if await db.is_banned(user.id):
        return await message.reply("🚫 You are banned from using this bot.")

    # deep link handling
    if len(message.command) > 1 and message.command[1].startswith("DS_"):
        code = message.command[1][3:]
        data = await db.get_file(code)

        if not data:
            return await message.reply("File not found or expired")

        try:
            sent = await app.copy_message(
                chat_id=message.chat.id,
                from_chat_id=LOG_CHANNEL_ID,
                message_id=data["log_msg_id"]
            )

            delmsg = await app.send_message(
                message.chat.id,
                text=f"❗️❗️❗️ <b>IMPORTANT</b> ❗️❗️❗️\n\nᴛʜɪꜱ ꜰɪʟᴇ / ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b>{DELETE_TIME // 60} Mɪɴᴜᴛᴇꜱ</b> ⏰ (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\nᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ᴛᴏ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛʜᴇʀᴇ.",
                parse_mode=ParseMode.HTML
            )
            
            await asyncio.sleep(DELETE_TIME)
            await sent.delete()
            await delmsg.delete()
            
        except Exception as e:
            return await message.reply("Failed to retrieve file")

        return  
    
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


@app.on_message(filters.command("users") & filters.user(OWNER_ID))
async def get_stats(bot, message):
    mr = await message.reply('**𝙰𝙲𝙲𝙴𝚂𝚂𝙸𝙽𝙶 𝙳𝙴𝚃𝙰𝙸𝙻𝚂.....**')
    total_users = await db.total_users_count()
    await mr.edit( text=f"Total Users : `{total_users}`")

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    all_users = await db.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("broadcast started !") 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await db.total_users_count()
    async for user in all_users:
        uid = user.get("id") or user.get("_id")
        if not uid:
            continue

        sts = await send_msg(uid, broadcast_msg)
        if sts == 200:
            success += 1
        else:
            failed += 1
        if sts == 400:
            await db.delete_user(uid)
        done += 1
        if not done % 20:
           await sts_msg.edit(f"Broadcast in progress:\nnTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Broadcast Completed:\nCompleted in `{completed_in}`.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
 
         
async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        print(f"{user_id} : deactivated")
        return 400
    except UserIsBlocked:
        print(f"{user_id} : blocked the bot")
        return 400
    except PeerIdInvalid:
        print(f"{user_id} : user id invalid")
        return 400
    except Exception as e:
        print(f"{user_id} : {e}")
        return 500

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_handler(_, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /ban user_id")

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("Invalid user id")

    await db.ban_user(user_id)

    # Notify banned user
    try:
        await app.send_message(
            user_id,
            "🚫 **You are banned from using this bot.**\n\n"
            "If you think this is a mistake, contact the admin."
        )
    except:
        pass  # user may have blocked bot

    await message.reply(f"✅ User `{user_id}` has been banned.")

@app.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_handler(_, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /unban user_id")

    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("Invalid user id")

    await db.unban_user(user_id)

    # Notify unbanned user
    try:
        await app.send_message(
            user_id,
            "✅ **You have been unbanned.**\n\n"
            "You can now use the bot again."
        )
    except:
        pass

    await message.reply(f"✅ User `{user_id}` has been unbanned.")

# ==========================================================================================================
# URL HANDLER
# ==========================================================================================================

@app.on_message(filters.private & filters.text & ~filters.regex(r'^/'))
async def url_handler(_, m):
    if await db.is_banned(m.from_user.id):
        return await m.reply("🚫 You are banned from using this bot.")
    
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

async def main():
    await app.start()
    try:
        await app.get_chat(LOG_CHANNEL_ID)
    except Exception as e:
        raise RuntimeError(f"Invalid LOG_CHANNEL_ID: {e}")

    await app.send_message(
        OWNER_ID,
        "𝐁𝐎𝐓 𝐑𝐄𝐒𝐓𝐀𝐑𝐓𝐄𝐃 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘 ✅"
    )
    await idle()
    await app.stop()

app.run(main())
