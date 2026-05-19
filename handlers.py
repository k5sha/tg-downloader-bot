import asyncio
import re
from aiogram import F, types, Router, Bot
from aiogram.filters import Command
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile, BufferedInputFile
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest

from config import logger
from services import download_tiktok

router = Router()

TIKTOK_RE = re.compile(r'(https?://(?:vm|vt|www|m)\.tiktok\.com/[^\s]+)', re.IGNORECASE)


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
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_type = message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    
    tiktok_url = tiktok_match.group(1)
    logger.info(f"Processing TikTok URL from {user_id}: {tiktok_url}")
    
    if not is_group:
        try:
            await message.react(emoji="📥")
        except:
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
            except:
                await message.reply("Не вдалося завантажити")
        return
    
    media_content, audio_info, thumbnail_bytes, width, height = result
    
    try:
        if isinstance(media_content, MediaGroupBuilder):
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
            logger.info(f"Sending slideshow to {user_id}")
            await message.reply_media_group(media=media_content.build())
            
            if not is_group:
                try:
                    await message.react(emoji="✅")
                except:
                    pass
        
        elif isinstance(media_content, URLInputFile) or isinstance(media_content, str):
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
                except:
                    pass
        
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