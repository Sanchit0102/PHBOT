import html
import os
import aiohttp
import asyncio
import tempfile
import shutil
import logging
import yt_dlp
from uuid import uuid4
from pyrogram.enums import ParseMode
from pyrogram import Client

DELETE_TIME = int(os.environ.get("DELETE_TIME", "900"))

def cap(title, duration, quality_url, bot_username):
    title = html.escape(title or "Video")
    duration = duration or "N/A"
    quality_url = html.escape(quality_url)

    return (
        f"<b>{title}</b>\n\n"
        f"<b>Duration: {duration}</b>\n\n"
        f"<b>Watch Online: <a href=\"{quality_url}\">Click Here</a></b>\n\n"
        f"<b>⚡Upload By @{html.escape(bot_username)}</b>"
    )

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

async def upload_hls_to_telegram(app: Client, message, url, title, duration, poster):
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
    
    sent = await app.send_video(
        chat_id=message.chat.id,
        video=video,
        caption=cap(title, duration, url, me.username or "THE_DS_OFFICIAL_BOT"),
        supports_streaming=True,
        thumb=thumb_path,
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
