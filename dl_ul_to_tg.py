import html
import os
import asyncio
import tempfile
import shutil
import logging
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
        f"Duration: {duration}\n\n"
        f"Watch Online: <a href=\"{quality_url}\">Click Here</a>\n\n"
        f"⚡Upload By @{html.escape(bot_username)}"
    )

# ==========================================================================================================

async def upload_hls_to_telegram(app: Client, message, url, title, duration, poster=None):
    import yt_dlp

    temp = tempfile.gettempdir()
    base = os.path.join(temp, f"dl_{uuid4().hex}")

    ydl_opts = {
        "format": "best",
        "outtmpl": base + ".%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "concurrent_fragment_downloads": 8,
        "http_chunk_size": 10 * 1024 * 1024,
    }

    def run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    await asyncio.to_thread(run)

    files = [f for f in os.listdir(temp) if f.startswith(os.path.basename(base))]
    video = os.path.join(temp, files[0])

    sent = await app.send_video(
        chat_id=message.chat.id,
        video=video,
        caption=cap(title, duration, url),
        supports_streaming=True,
        parse_mode=ParseMode.HTML
    )

    delmsg = await app.send_message(
    chat_id=message.chat.id,
    text=f"❗️❗️❗️ <b>IMPORTANT</b> ❗️❗️❗️\n\nᴛʜɪꜱ ꜰɪʟᴇ / ᴠɪᴅᴇᴏ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b>{DELETE_TIME // 60} minutes</b> ⏰ (ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪꜱꜱᴜᴇꜱ).\n\nᴘʟᴇᴀꜱᴇ ꜰᴏʀᴡᴀʀᴅ ᴛʜɪꜱ ꜰɪʟᴇ ᴛᴏ ꜱᴏᴍᴇᴡʜᴇʀᴇ ᴇʟꜱᴇ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛʜᴇʀᴇ.",
    parse_mode=ParseMode.HTML
    )
    
    await asyncio.sleep(DELETE_TIME)
    
    await sent.delete()
    await delmsg.edit_text("ʏᴏᴜʀ ᴠɪᴅᴇᴏ / ꜰɪʟᴇ ɪꜱ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ !!")
    
    try:
        os.remove(video)
    except Exception:
        pass
