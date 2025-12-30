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

def cap(title, duration, url):
    title = html.escape(title) if title else "Video"
    duration = duration or "N/A"
    url = html.escape(url)
    return f"<b>{title}</b>\nDuration: {duration}\n<a href='{url}'>Watch Online</a>"

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

    await asyncio.sleep(DELETE_TIME)
    await sent.delete()

    try:
        os.remove(video)
    except Exception:
        pass
