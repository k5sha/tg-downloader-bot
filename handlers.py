import asyncio
import re
import logging
from aiogram import F, types, Router, Bot
from aiogram.filters import Command
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile, BufferedInputFile
from aiogram.enums import ChatMemberStatus

from config import logger
from services import download_tiktok, download_universal

router = Router()

TIKTOK_RE = re.compile(r'(https?://(?:vm|vt|www|m)\.tiktok\.com/[^\s]+)', re.IGNORECASE)
UNIVERSAL_RE = re.compile(
    r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|share)/[^\s]+|'
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+|'
    r'https?://(?:www\.)?twitter\.com/[^\s]+|'
    r'https?://(?:www\.)?x\.com/[^\s]+)',
    re.IGNORECASE
)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Start command from user {message.from_user.id} in chat {message.chat.id}")
    await message.answer(
        "🎬 <b>TikTok & Instagram Video Downloader</b>\n\n"
        "Надішли посилання на:\n"
        "• TikTok (відео, слайд-шоу)\n"
        "• Instagram (reels, posts, carousel)\n"
        "• YouTube (short та звичайні відео)\n\n"
        "<i>Бот працює безкоштовно</i>",
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Інструкція</b>\n\n"
        "Просто надішли посилання на TikTok/Instagram/YouTube\n\n"
        "<b>Посилання мають виглядати так:</b>\n"
        "• https://vt.tiktok.com/xxx\n"
        "• https://www.tiktok.com/@user/video/xxx\n"
        "• https://www.instagram.com/p/xxx\n"
        "• https://youtu.be/xxx\n\n"
        "<b>Для груп:</b>\n"
        "Бот повинен бути адміністратором групи",
        parse_mode="HTML"
    )

@router.message(F.text)
async def handle_links(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    logger.info(f"Processing message from user {user_id} in {chat_type} (chat: {chat_id})")
    logger.debug(f"Message text: {message.text[:100]}...")
    
    # Перевіряємо чи повідомлення з групи
    is_group = chat_type in ["group", "supergroup"]
    
    # Якщо це група, перевіряємо права бота
    
    
    text = message.text
    
    # Шукаємо TikTok посилання
    tiktok_match = TIKTOK_RE.search(text)
    universal_match = UNIVERSAL_RE.search(text) if not tiktok_match else None
    
    if not tiktok_match and not universal_match:
        # Не наше посилання - ігноруємо
        return
    
    # TikTok
    if tiktok_match:
        tiktok_url = tiktok_match.group(1)
        logger.info(f"Processing TikTok URL: {tiktok_url}")
        
        # Ставимо реакцію або статус друку
        if not is_group:
            try:
                await message.react(emoji="📥")
            except:
                pass
        
        result = await download_tiktok(tiktok_url)
        if not result or not result[0]:
            logger.error(f"Failed to download TikTok content from {tiktok_url}")
            if is_group:
                await message.reply("💔 Не вдалося завантажити відео")
            else:
                try:
                    await message.react(emoji="💔")
                except:
                    await message.reply("💔")
            return
            
        media_content, audio_info, thumbnail_bytes, width, height = result
        
        try:
            # Слайд-шоу (карусель)
            if isinstance(media_content, MediaGroupBuilder):
                logger.info(f"Sending slideshow with {len(media_content.media)} items")
                await message.reply_media_group(media=media_content.build())
                if not is_group:
                    try:
                        await message.react(emoji="✅")
                    except:
                        pass
            
            # Відео
            elif isinstance(media_content, URLInputFile) or isinstance(media_content, str):
                logger.info(f"Sending video (size: {width}x{height if width else 'unknown'})")
                kwargs = {
                    "video": media_content,
                    "supports_streaming": True
                }
                
                if thumbnail_bytes:
                    kwargs["thumbnail"] = BufferedInputFile(thumbnail_bytes, filename="thumb.jpg")
                    logger.info(f"Thumbnail size: {len(thumbnail_bytes)} bytes")
                if width and height:
                    kwargs["width"] = width
                    kwargs["height"] = height
                
                await message.reply_video(**kwargs)
                
                if not is_group:
                    try:
                        await message.react(emoji="✅")
                    except:
                        pass
            
            # Аудіо для приватних чатів
            if not is_group and audio_info:
                logger.info(f"Sending audio: {audio_info['title']}")
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
            
            logger.info(f"Successfully sent TikTok content to user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error sending TikTok media: {e}", exc_info=True)
            if is_group:
                await message.reply("💔 Помилка при відправці")
            else:
                try:
                    await message.react(emoji="💔")
                except:
                    await message.reply("💔")
    
    # Instagram, YouTube та інші
    elif universal_match:
        target_url = universal_match.group(1)
        logger.info(f"Processing universal URL: {target_url}")
        
        if not is_group:
            try:
                await message.react(emoji="📥")
            except:
                pass
        
        result = await download_universal(target_url)
        if not result or not result[0]:
            logger.error(f"Failed to download universal content from {target_url}")
            if is_group:
                await message.reply("💔 Не вдалося завантажити контент")
            else:
                try:
                    await message.react(emoji="💔")
                except:
                    await message.reply("💔")
            return

        media_content, thumbnail_bytes, width, height = result
        
        try:
            if isinstance(media_content, MediaGroupBuilder):
                logger.info(f"Sending universal slideshow")
                await message.reply_media_group(media=media_content.build())
                if not is_group:
                    try:
                        await message.react(emoji="✅")
                    except:
                        pass
            
            elif isinstance(media_content, tuple) and media_content[0] == "text_link":
                logger.info(f"Video too long, sending link")
                await message.reply(f"⚠️ Відео занадто довге (>5 хв)\nПосилання: {media_content[1]}")
                if not is_group:
                    try:
                        await message.react(emoji="⚠️")
                    except:
                        pass
            
            elif isinstance(media_content, tuple) and media_content[0] in ["video", "image"]:
                media_type, media_file = media_content
                logger.info(f"Sending universal {media_type}")
                
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
                
                if not is_group:
                    try:
                        await message.react(emoji="✅")
                    except:
                        pass
            
            logger.info(f"Successfully sent universal content to user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error sending universal media: {e}", exc_info=True)
            if is_group:
                await message.reply("💔 Помилка при відправці")
            else:
                try:
                    await message.react(emoji="💔")
                except:
                    await message.reply("💔")