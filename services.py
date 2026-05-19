import logging
import asyncio
import aiohttp
import ssl
import cv2
import tempfile
import os
from typing import Tuple, Optional, List, Dict, Any
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile, BufferedInputFile

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# Глобальна сесія
_session: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    """Отримує глобальну сесію"""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        _session = aiohttp.ClientSession(
            connector=connector,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=30)
        )
    return _session

async def close_downloader():
    """Закриває глобальну сесію"""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

def get_video_info(video_bytes: bytes) -> Tuple[Optional[int], Optional[int], Optional[bytes]]:
    """
    Отримує розміри відео та створює прев'ю з першого кадру
    Returns: (width, height, thumbnail_bytes)
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_file.write(video_bytes)
            tmp_path = tmp_file.name
        
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return None, None, None
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Беремо перший кадр для прев'ю
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return width, height, None
        
        # Конвертуємо в JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        thumbnail_bytes = buffer.tobytes()
        
        return width, height, thumbnail_bytes
        
    except Exception as e:
        logging.error(f"Error getting video info: {e}")
        return None, None, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

async def download_tiktok(url: str) -> Tuple[Optional[MediaGroupBuilder | str], Optional[Dict], Optional[bytes], Optional[int], Optional[int]]:
    """
    Завантажує TikTok контент
    Returns: (media_content, audio_info, thumbnail_bytes, width, height)
    """
    api_url = f"https://www.tikwm.com/api/?url={url}"
    try:
        session = await get_session()
        async with session.get(api_url) as response:
            if response.status != 200:
                return None, None, None, None, None
            
            json_data = await response.json()
            if json_data.get("code") != 0 or "data" not in json_data:
                return None, None, None, None, None
            
            data = json_data["data"]
            
            # Аудіо інформація
            music_data = data.get("music_info", {})
            audio_info = None
            if data.get("music"):
                audio_info = {
                    "url": data["music"],
                    "title": music_data.get("title", "TikTok Audio"),
                    "author": music_data.get("author", "Unknown")
                }
            
            # Слайд-шоу (карусель)
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
                
                return media_group, audio_info, None, None, None
            
            # Відео
            if "play" in data and data["play"]:
                video_url = data["play"]
                
                # Завантажуємо відео для отримання розмірів та прев'ю
                async with session.get(video_url) as video_resp:
                    if video_resp.status == 200:
                        video_bytes = await video_resp.read()
                        width, height, thumbnail_bytes = get_video_info(video_bytes)
                        
                        # Створюємо URLInputFile для відео
                        video_file = URLInputFile(
                            video_url, 
                            filename="video.mp4",
                            headers=HEADERS
                        )
                        return video_file, audio_info, thumbnail_bytes, width, height
                
                return video_url, audio_info, None, None, None
                    
    except Exception as e:
        logging.error(f"TikTok parser error: {e}")
    
    return None, None, None, None, None

async def download_universal(url: str) -> Tuple[Optional[MediaGroupBuilder | str], Optional[bytes], Optional[int], Optional[int]]:
    """
    Завантажує контент з Instagram, YouTube та інших платформ
    Returns: (media_content, thumbnail_bytes, width, height)
    """
    from yt_dlp import YoutubeDL
    
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
            return None, None, None, None

        # Карусель (декілька медіа)
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
            return media_group, None, None, None

        # Один медіафайл
        else:
            duration = info.get('duration', 0)
            if duration and duration > 300:
                return ("text_link", url), None, None, None

            file_url = info.get('url')
            if not file_url and info.get('formats'):
                file_url = info['formats'][-1].get('url')

            if not file_url:
                return None, None, None, None

            is_video = info.get('ext') == 'mp4' or info.get('vcodec') != 'none' or 'youtube' in info.get('extractor', '')
            media_type = "video" if is_video else "image"
            
            filename = "video.mp4" if is_video else "photo.jpg"
            media_file = URLInputFile(file_url, filename=filename, headers=HEADERS)
            
            # Отримуємо прев'ю
            thumbnail_bytes = None
            width = height = None
            
            if is_video and info.get('thumbnail'):
                session = await get_session()
                try:
                    async with session.get(info['thumbnail']) as thumb_resp:
                        if thumb_resp.status == 200:
                            thumbnail_bytes = await thumb_resp.read()
                except:
                    pass
            
            return (media_type, media_file), thumbnail_bytes, width, height

    except Exception as e:
        logging.error(f"Universal parser error (yt-dlp): {e}")
        return None, None, None, None