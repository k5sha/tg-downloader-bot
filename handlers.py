import asyncio
import os
import re
import shutil
from aiogram import F, types, Router, Bot
from aiogram.filters import Command
from aiogram.types import URLInputFile, BufferedInputFile, FSInputFile
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest

from config import logger
from services import download_tiktok, download_video

router = Router()

TIKTOK_RE = re.compile(r'(https?://(?:vm|vt|www|m)\.tiktok\.com/[^\s]+)', re.IGNORECASE)
URL_RE = re.compile(r'https?://[^\s<]+', re.IGNORECASE)


async def handle_video(message: types.Message, bot: Bot):
    match = URL_RE.search(message.text)
    if not match:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)
    result = await download_video(match.group(0).rstrip(".,!?)]}"))
    if not result:
        await message.reply("Не вдалося завантажити відео або воно завелике")
        return

    path = result
    try:
        video = FSInputFile(path, filename=f"video{os.path.splitext(path)[1]}")
        if path.lower().endswith(".mp4"):
            await message.reply_video(video=video, supports_streaming=True)
        else:
            await message.reply_document(document=video)
    except Exception as e:
        logger.error(f"Video send error: {e}", exc_info=True)
        await message.reply("Помилка при відправці відео")
    finally:
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Start command from user {message.from_user.id}")
    await message.answer(
        "🎬 <b>TikTok Video Downloader</b>\n\n"
        "Надішли посилання на TikTok відео\n\n"
        "<b>Приклади посилань:</b>\n"
        "• https://vt.tiktok.com/xxx\n"
        "• https://www.tiktok.com/@user/video/xxx\n\n"
        "<b>Для груп:</b>\n"
        "Бот повинен бути адміністратором групи\n\n"
        "<i>Бот працює безкоштовно</i>",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Інструкція</b>\n\n"
        "Просто надішли посилання на TikTok\n"
        "Бот автоматично завантажить відео\n\n"
        "<b>Посилання мають виглядати так:</b>\n"
        "• https://vt.tiktok.com/xxx\n"
        "• https://www.tiktok.com/@user/video/xxx\n\n"
        "<b>Для груп:</b>\n"
        "Бот повинен бути адміністратором групи",
        parse_mode="HTML"
    )


@router.message(F.text)
async def handle_tiktok(message: types.Message, bot: Bot):
    tiktok_match = TIKTOK_RE.search(message.text)
    if not tiktok_match:
        return await handle_video(message, bot)
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    
    tiktok_url = tiktok_match.group(1)
    logger.info(f"Processing TikTok URL from {user_id}: {tiktok_url}")
    
    if not is_group:
        try:
            await message.react(emoji="📥")
        except Exception:
            pass
    
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    result = await download_tiktok(tiktok_url)
    
    if not result or not result[0]:
        logger.error(f"Failed to download: {tiktok_url}")
        if is_group:
            await message.reply("Не вдалося завантажити відео")
        else:
            try:
                await message.react(emoji="💔")
            except Exception:
                await message.reply("Не вдалося завантажити")
        return
    
    media_content, audio_info, thumbnail_bytes, width, height = result
    
    try:
        # 1. SLIDESHOW PROCESSING (PHOTO LIST)
        if isinstance(media_content, list):
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
            logger.info(f"Sending slideshow to {user_id}")
            
            # Send albums sequentially (10 photos per group)
            for group in media_content:
                await message.reply_media_group(media=group)
                await asyncio.sleep(0.5)  # Delay to avoid FloodWait
            
            if not is_group:
                try:
                    await message.react(emoji="✅")
                except Exception:
                    pass

        # 2. VIDEO PROCESSING
        elif isinstance(media_content, (URLInputFile, FSInputFile, str)):
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
            logger.info(f"Sending video to {user_id}")
            
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
            
            if not is_group:
                try:
                    await message.react(emoji="✅")
                except Exception:
                    pass

        # 3. AUDIO PROCESSING
        if not is_group and audio_info:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VOICE)
            logger.info(f"Sending audio: {audio_info['title']}")
            await asyncio.sleep(0.5)
            
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
        
        logger.info(f"Successfully sent to {user_id}")
        
    except TelegramBadRequest as e:
        logger.error(f"Telegram error: {e}")
        await message.reply("Помилка при відправці")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.reply("Помилка при відправці")