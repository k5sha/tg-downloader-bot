import logging
import asyncio
import aiohttp
import ssl
import cv2
import tempfile
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional, Dict
import yt_dlp
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile
from config import MAX_VIDEO_SIZE_BYTES

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_session: Optional[aiohttp.ClientSession] = None
_cache: Dict[str, Tuple] = {}
_ytdlp_semaphore = asyncio.Semaphore(1)

async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=2, limit_per_host=1)
        _session = aiohttp.ClientSession(
            connector=connector,
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=30, connect=10)
        )
    return _session

async def close_downloader():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
    _cache.clear()

def get_video_info(video_bytes: bytes) -> Tuple[Optional[int], Optional[int], Optional[bytes]]:
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
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return width, height, None
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        thumbnail_bytes = buffer.tobytes()
        
        return width, height, thumbnail_bytes
        
    except Exception as e:
        logging.error(f"Video info error: {e}")
        return None, None, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

async def download_file(url: str, max_retries: int = 2) -> Optional[bytes]:
    for attempt in range(max_retries):
        try:
            session = await get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    continue
                return await response.read()
        except:
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(0.5)
    return None

async def download_video(url: str) -> Optional[str]:
    def _download():
        directory = tempfile.mkdtemp(prefix="ytdlp_")
        try:
            with yt_dlp.YoutubeDL({
                "format": "b[ext=mp4]/b",
                "format_sort": ["res:720", f"filesize:{MAX_VIDEO_SIZE_BYTES}"],
                "max_filesize": MAX_VIDEO_SIZE_BYTES,
                "match_filter": yt_dlp.utils.match_filter_func("!is_live"),
                "noplaylist": True,
                "js_runtimes": {"deno": {}},
                "socket_timeout": 20,
                "retries": 2,
                "fragment_retries": 2,
                "cachedir": False,
                "outtmpl": os.path.join(directory, "%(id)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }) as ydl:
                ydl.extract_info(url, download=True)
            path = next((p for p in Path(directory).iterdir() if p.is_file() and p.suffix != ".part"), None)
            if path and path.stat().st_size > MAX_VIDEO_SIZE_BYTES:
                raise ValueError("Downloaded video exceeds the configured size limit")
            return str(path) if path else None
        except Exception as e:
            logging.error(f"yt-dlp error: {e}")
            shutil.rmtree(directory, ignore_errors=True)
            return None

    async with _ytdlp_semaphore:
        return await asyncio.to_thread(_download)

async def download_tiktok(url: str) -> Tuple[Optional[any], Optional[Dict], Optional[bytes], Optional[int], Optional[int]]:
    cache_key = url
    if cache_key in _cache:
        return _cache[cache_key]
    
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
                video_versions = data.get("video_versions", [])
                max_elements = min(len(images), 10)
                
                media_group = MediaGroupBuilder()
                for i in range(max_elements):
                    if i < len(video_versions) and video_versions[i]:
                        media_group.add_video(media=video_versions[i])
                    else:
                        media_group.add_photo(media=images[i])
                
                result = (media_group, audio_info, None, None, None)
                _cache[cache_key] = result
                return result
            
            if "play" in data and data["play"]:
                video_url = data["play"]
                video_bytes = await download_file(video_url)
                if not video_bytes:
                    return None, None, None, None, None
                
                width, height, thumbnail_bytes = get_video_info(video_bytes)
                if not width:
                    width = data.get("width")
                    height = data.get("height")
                
                video_file = URLInputFile(video_url, filename="video.mp4", headers=HEADERS)
                result = (video_file, audio_info, thumbnail_bytes, width, height)
                _cache[cache_key] = result
                return result
                    
    except Exception as e:
        logging.error(f"TikTok error: {e}")
    
    return None, None, None, None, None
