import logging
import asyncio
import aiohttp
from yt_dlp import YoutubeDL
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile

async def download_tiktok(url: str) -> tuple[MediaGroupBuilder | str, dict | None] | None:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return None
                
                json_data = await response.json()
                if json_data.get("code") != 0 or "data" not in json_data:
                    return None
                
                data = json_data["data"]
                
                music_data = data.get("music_info", {})
                audio_info = None
                if data.get("music"):
                    audio_info = {
                        "url": data["music"],
                        "title": music_data.get("title", "TikTok Audio"),
                        "author": music_data.get("author", "Unknown")
                    }
                
                if "images" in data and data["images"]:
                    images = data["images"]
                    live_images = data.get("live_images", [])
                    max_elements = min(len(images), 10)
                    
                    media_group = MediaGroupBuilder()
                    for i in range(max_elements):
                        if i < len(live_images) and live_images[i] and ("video" in live_images[i] or "http" in live_images[i]):
                            media_group.add_video(media=live_images[i])
                        else:
                            media_group.add_photo(media=images[i])
                            
                    return (media_group, audio_info)
                
                if "play" in data and data["play"]:
                    return (data["play"], audio_info)
                    
    except Exception as e:
        logging.error(f"TikTok parser error: {e}")
    return None


async def download_universal(url: str) -> MediaGroupBuilder | tuple[str, URLInputFile | str] | None:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
    }
    
    try:
        loop = asyncio.get_event_loop()
        with YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
            
        if not info:
            return None

        if 'entries' in info:
            media_group = MediaGroupBuilder()
            entries = info['entries']
            max_elements = min(len(entries), 10)
            
            for entry in entries[:max_elements]:
                if not entry:
                    continue
                file_url = entry.get('url') or entry.get('requested_downloads', [{}])[0].get('url')
                if not file_url:
                    continue
                    
                if entry.get('ext') == 'mp4' or 'video' in entry.get('format_id', ''):
                    media_group.add_video(media=file_url)
                else:
                    media_group.add_photo(media=file_url)
            return media_group

        else:
            duration = info.get('duration', 0)
            if duration and duration > 300:
                return ("text_link", url)

            file_url = info.get('url')
            if not file_url and info.get('formats'):
                file_url = info['formats'][-1].get('url')

            if not file_url:
                return None

            is_video = info.get('ext') == 'mp4' or info.get('vcodec') != 'none' or 'youtube' in info.get('extractor', '')
            media_type = "video" if is_video else "image"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            filename = "video.mp4" if is_video else "photo.jpg"
            stream_file = URLInputFile(file_url, filename=filename, headers=headers)

            return (media_type, stream_file)

    except Exception as e:
        logging.error(f"Universal parser error (yt-dlp): {e}")
    return None