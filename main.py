import asyncio
import re
import logging
from aiogram import F, types
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import URLInputFile

from config import bot, dp 
from services import download_tiktok, download_universal

logging.basicConfig(level=logging.INFO)

TIKTOK_RE = re.compile(r'(https?://(?:vm|vt|www)\.tiktok\.com/[^\s]+)')
UNIVERSAL_RE = re.compile(
    r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|share)/[^\s]+|'
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+)'
)

@dp.message(F.text)
async def handle_links(message: types.Message):
    text = message.text

    if tiktok_match := TIKTOK_RE.search(text):
        tiktok_url = tiktok_match.group(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        result = await download_tiktok(tiktok_url)
        if not result:
            return
            
        try:
            media_content, audio_info = result
            
            if isinstance(media_content, MediaGroupBuilder):
                await message.reply_media_group(media=media_content.build())
            elif isinstance(media_content, str):
                await message.reply_video(video=media_content)
                
            if message.chat.type == "private" and audio_info:
                await asyncio.sleep(2)
                await bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
                
                audio_file = URLInputFile(
                    audio_info["url"], 
                    filename=f"{audio_info['title']}.mp3"
                )
                
                await message.reply_audio(
                    audio=audio_file,
                    title=audio_info["title"],
                    performer=audio_info["author"]
                )
                    
        except Exception as e:
            logging.error(f"Error sending TikTok media: {e}")

    elif universal_match := UNIVERSAL_RE.search(text):
        target_url = universal_match.group(1)
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        result = await download_universal(target_url)
        if not result:
            return

        try:
            if isinstance(result, MediaGroupBuilder):
                await message.reply_media_group(media=result.build())
            elif isinstance(result, tuple):
                media_type, content = result
                
                if media_type == "text_link":
                    await message.reply(f"⚠️ Video is too long (over 5 minutes).\nDirect link: {content}")
                elif media_type == "video":
                    await message.reply_video(video=content)
                elif media_type == "image":
                    await message.reply_photo(photo=content)
                    
        except Exception as e:
            logging.error(f"Error sending universal media: {e}")


async def main():
    logging.info("Bot started successfully in streaming mode.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())