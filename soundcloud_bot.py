import logging
import os
import re
import asyncio
import json
from pathlib import Path
from datetime import datetime
import yt_dlp
import urllib.request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DOWNLOAD_FOLDER = "downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)
STATS_FILE = "bot_stats.json"

def clean_filename(filename: str) -> str:
    """Очистить имя файла"""
    name, ext = os.path.splitext(filename)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-]', '', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_') + ext

def download_thumbnail(thumb_url: str) -> str:
    """Скачать обложку"""
    if not thumb_url:
        return None
    try:
        thumb_path = os.path.join(DOWNLOAD_FOLDER, 'thumb.jpg')
        urllib.request.urlretrieve(thumb_url, thumb_path)
        logger.info(f"Обложка: {thumb_path}")
        return thumb_path
    except Exception as e:
        logger.warning(f"Обложка ошибка: {e}")
        return None

def get_track_info(url: str) -> dict:
    """Получить инфо о треке"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', ''),
                'artist': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
            }
    except:
        return {'title': '', 'artist': '', 'thumbnail': ''}

def download_music(url: str) -> tuple[bool, str]:
    """Скачать музыку"""
    try:
        logger.info(f"Скачиваю: {url}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s'),
            'quiet': False,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Поищем файл
            mp3_files = list(Path(DOWNLOAD_FOLDER).glob('*.mp3'))
            if mp3_files:
                latest = max(mp3_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Файл: {latest}")
                return True, str(latest)
            
            return False, "Файл не найден"
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False, str(e)

def search_music(query: str) -> tuple[bool, str]:
    """Поиск музыки"""
    try:
        logger.info(f"Ищу: {query}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s'),
            'default_search': 'ytsearch',
            'noplaylist': True,
            'quiet': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            
            mp3_files = list(Path(DOWNLOAD_FOLDER).glob('*.mp3'))
            if mp3_files:
                latest = max(mp3_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Найдено: {latest}")
                return True, str(latest)
            
            return False, "Не найдено"
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False, str(e)

# ===== СТАТИСТИКА =====

def load_stats() -> dict:
    try:
        if Path(STATS_FILE).exists():
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'total_downloads': 0, 'total_users': 0, 'users': {}}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except:
        pass

def update_user_stats(user_id, username, first_name):
    stats = load_stats()
    if str(user_id) not in stats['users']:
        stats['total_users'] += 1
        stats['users'][str(user_id)] = {
            'username': username or 'user',
            'downloads': 0,
        }
    stats['users'][str(user_id)]['downloads'] += 1
    stats['total_downloads'] += 1
    save_stats(stats)

def get_stats_text() -> str:
    stats = load_stats()
    users_list = stats.get('users', {})
    top = sorted(users_list.items(), key=lambda x: x[1].get('downloads', 0), reverse=True)[:5]
    
    text = f"📊 СТАТИСТИКА\n🔢 Скачиваний: {stats.get('total_downloads', 0)}\n👥 Пользователей: {stats.get('total_users', 0)}\n\n🏆 ТОП:\n"
    for i, (_, data) in enumerate(top, 1):
        text += f"{i}. @{data.get('username')} - {data.get('downloads')} 🎵\n"
    return text

# ===== КОМАНДЫ =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "🎵 Music Downloader\n\nОтправь ссылку на трек:\n🎵 SoundCloud\n🎵 Spotify\n🎵 YouTube\n🎵 Яндекс Музыка\n🎵 VK\n🎵 Tidal\n\n/help - справка"
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "📝 Как использовать:\n1️⃣ Скопируй ссылку на трек\n2️⃣ Отправь в чат\n3️⃣ Получи MP3 файл\n\n✅ Поддержка:\n🎵 SoundCloud\n🎵 Spotify\n🎵 YouTube\n🎵 Яндекс Музыка\n🎵 VK Музыка\n🎵 Tidal"
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner_id = os.getenv("OWNER_ID")
    if owner_id and str(update.effective_user.id) != owner_id:
        await update.message.reply_text("❌ Только для владельца")
        return
    await update.message.reply_text(get_stats_text())

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    update_user_stats(user_id, username, first_name)
    
    supported = ['soundcloud.com', 'youtube.com', 'youtu.be', 'vk.com', 'vkontakte.ru', 'tidal.com', 'spotify.com', 'yandex.ru', 'music.yandex']
    
    if not any(s in url.lower() for s in supported):
        await update.message.reply_text("❌ Ссылка не поддерживается\n\nПоддерживаемые: SoundCloud, Spotify, YouTube, Яндекс, VK, Tidal")
        return
    
    loading_msg = await update.message.reply_text("⏳ Ищу трек...")
    
    try:
        # SPOTIFY
        if 'spotify.com' in url.lower():
            try:
                info = await asyncio.to_thread(get_track_info, url)
                title = info.get('title', '')
                artist = info.get('artist', '')
                
                if not title:
                    await loading_msg.edit_text("❌ Не удалось получить информацию")
                    return
                
                search_query = f"{title} {artist}".strip()
                success, result = await asyncio.to_thread(search_music, search_query)
            except:
                success, result = await asyncio.to_thread(search_music, url)
        
        # ЯНДЕКС МУЗЫКА
        elif 'yandex' in url.lower():
            try:
                info = await asyncio.to_thread(get_track_info, url)
                title = info.get('title', '')
                artist = info.get('artist', '')
                
                if not title:
                    await loading_msg.edit_text("❌ Не удалось получить информацию")
                    return
                
                search_query = f"{title} {artist}".strip()
                success, result = await asyncio.to_thread(search_music, search_query)
            except:
                success, result = await asyncio.to_thread(search_music, url)
        
        # ОСТАЛЬНЫЕ СЕРВИСЫ
        else:
            success, result = await asyncio.to_thread(download_music, url)
        
        if not success:
            await loading_msg.edit_text(f"❌ Ошибка: {result}")
            return
        
        # ОТПРАВКА ФАЙЛА
        file_path = Path(result)
        if not file_path.exists():
            await loading_msg.edit_text("❌ Файл не найден")
            return
        
        file_size = file_path.stat().st_size / (1024 * 1024)
        logger.info(f"Отправляю: {file_path} ({file_size:.1f} МБ)")
        
        # Получить инфо и обложку
        track_info = await asyncio.to_thread(get_track_info, url)
        title = track_info.get('title', file_path.stem)
        artist = track_info.get('artist', '')
        thumbnail = None
        
        if track_info.get('thumbnail'):
            thumbnail = await asyncio.to_thread(download_thumbnail, track_info['thumbnail'])
        
        # Отправить
        try:
            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio_file,
                    title=title,
                    performer=artist,
                    thumbnail=thumbnail,
                    connect_timeout=60,
                    read_timeout=300,
                    write_timeout=300
                )
            logger.info(f"✅ Отправлено: {file_path.name}")
            file_path.unlink()
            
            if thumbnail and Path(thumbnail).exists():
                Path(thumbnail).unlink()
        
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            await update.message.reply_text(f"❌ Ошибка отправки: {str(e)}")
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    finally:
        try:
            await loading_msg.delete()
        except:
            pass

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Установи TELEGRAM_BOT_TOKEN")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
