import asyncio
import re
import logging
from aiogram import F, types, Router, Bot
from aiogram.filters import Command
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile, BufferedInputFile

from config import logger
from services import download_tiktok, download_universal

router = Router()

TIKTOK_RE = re.compile(r'(https?://(?:vm|vt|www)\.tiktok\.com/[^\s]+)')
UNIVERSAL_RE = re.compile(
    r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|share)/[^\s]+|'
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+)'
)

@router.message(F.text)
async def handle_links(message: types.Message, bot: Bot):
    text = message.text
    
    # TikTok
    if tiktok_match := TIKTOK_RE.search(text):
        tiktok_url = tiktok_match.group(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        result = await download_tiktok(tiktok_url)
        if not result or not result[0]:
            await message.react(emoji="💔")
            return
            
        media_content, audio_info, thumbnail_bytes, width, height = result
        
        try:
            # Слайд-шоу (карусель)
            if isinstance(media_content, MediaGroupBuilder):
                await message.reply_media_group(media=media_content.build())
                await message.react(emoji="✅")
            
            # Відео
            elif isinstance(media_content, URLInputFile) or isinstance(media_content, str):
                kwargs = {
                    "video": media_content,
                    "supports_streaming": True
                }
                
                if thumbnail_bytes:
                    kwargs["thumbnail"] = BufferedInputFile(thumbnail_bytes, filename="thumb.jpg")
                if width and height:
                    kwargs["width"] = width
                    kwargs["height"] = height
                
                await message.reply_video(**kwargs)
                await message.react(emoji="✅")
            
            # Аудіо для приватних чатів
            if message.chat.type == "private" and audio_info:
                await asyncio.sleep(1)
                await bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
                
                audio_file = URLInputFile(
                    audio_info["url"], 
                    filename=f"{audio_info['title']}.mp3",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                
                await message.reply_audio(
                    audio=audio_file,
                    title=audio_info["title"],
                    performer=audio_info["author"]
                )
                    
        except Exception as e:
            logging.error(f"Error sending TikTok media: {e}")
            await message.react(emoji="💔")
    
    # Instagram, YouTube та інші
    elif universal_match := UNIVERSAL_RE.search(text):
        target_url = universal_match.group(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        result = await download_universal(target_url)
        if not result or not result[0]:
            await message.react(emoji="💔")
            return

        media_content, thumbnail_bytes, width, height = result
        
        try:
            if isinstance(media_content, MediaGroupBuilder):
                await message.reply_media_group(media=media_content.build())
                await message.react(emoji="✅")
            
            elif isinstance(media_content, tuple) and media_content[0] == "text_link":
                await message.reply(f"⚠️ Відео занадто довге (>5 хв)\nПосилання: {media_content[1]}")
                await message.react(emoji="⚠️")
            
            elif isinstance(media_content, tuple) and media_content[0] in ["video", "image"]:
                media_type, media_file = media_content
                
                if media_type == "video":
                    kwargs = {
                        "video": media_file,
                        "supports_streaming": True
                    }
                    
                    if thumbnail_bytes:
                        kwargs["thumbnail"] = BufferedInputFile(thumbnail_bytes, filename="thumb.jpg")
                    if width and height:
                        kwargs["width"] = width
                        kwargs["height"] = height
                    
                    await message.reply_video(**kwargs)
                elif media_type == "image":
                    await message.reply_photo(photo=media_file)
                
                await message.react(emoji="✅")
                    
        except Exception as e:
            logging.error(f"Error sending universal media: {e}")
            await message.react(emoji="💔")

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎬 <b>TikTok & Instagram Video Downloader</b>\n\n"
        "Надішли посилання на:\n"
        "• TikTok (відео, слайд-шоу)\n"
        "• Instagram (reels, posts, carousel)\n"
        "• YouTube (short та звичайні відео)\n\n"
        "<i>Бот працює безкоштовно</i>",
        parse_mode="HTML"
    )