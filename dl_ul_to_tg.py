import html
import os
import aiohttp
import asyncio
import tempfile
import shutil
import logging
import yt_dlp
from uuid import uuid4
from PIL import Image
from pyrogram.enums import ParseMode
from pyrogram import Client

DELETE_TIME = int(os.environ.get("DELETE_TIME", "900"))

def cap(title, duration, quality_url, bot_username, filesize, quality):
    title = html.escape(title or "Video")
    duration = duration or "N/A"
    quality_url = html.escape(quality_url)

    return (
        f"<blockquote>𝖥𝗂𝗅𝖾 𝖭𝖺𝗆𝖾: <code>{title}</code></blockquote>\n\n"
        f"<blockquote>"
        f"𝖶𝖺𝗍𝖼𝗁 𝖮𝗇𝗅𝗂𝗇𝖾: <a href=\"{quality_url}\">Click Here</a>\n"
        f"𝖣𝗎𝗋𝖺𝗍𝗂𝗈𝗇: {duration} 𝖬𝗂𝗇𝗎𝗍𝖾𝗌\n"
        f"𝖥𝗂𝗅𝖾 𝖲𝗂𝗓𝖾: {filesize}\n"
        f"𝖰𝗎𝖺𝗅𝗂𝗍𝗒: {quality}"
        f"</blockquote>\n\n"
        f"<b>⚡ 𝖴𝗉𝗅𝗈𝖺𝖽 𝖡𝗒 - <a href=\"https://t.me/{html.escape(bot_username)}\">𝖣𝖲𝖠𝖽𝗎𝗅𝗍𝖡𝗈𝗍 🔞</a></b>"
       )

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
    
    sent = await app.send_video(
        chat_id=message.chat.id,
        video=video,
        caption="Loading...",
        supports_streaming=True,
        thumb=thumb_path,
        parse_mode=ParseMode.HTML
    )

    video_obj = sent.video or sent.document
    filesize = human_size(video_obj.file_size)

    await sent.edit_caption(
        cap(
            title=title,
            duration=int(duration.split(":")[0]) * 60 + int(duration.split(":")[1]) if ":" in duration else None,
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
        
    await asyncio.sleep(DELETE_TIME)
    
    await sent.delete()
    await delmsg.edit_text("ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!")
    
    try:
        os.remove(video)
    except Exception:
        pass
