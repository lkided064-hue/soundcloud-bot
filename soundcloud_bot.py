import logging
import os
import re
import asyncio
import json
from pathlib import Path
import urllib.request
import yt_dlp
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

def download_soundcloud(url: str) -> tuple[bool, str, dict]:
    """Скачать трек с SoundCloud"""
    try:
        logger.info(f"Скачивание: {url}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s'),
            'quiet': False,
            'no_warnings': False,
            'keepvideo': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', '')
            artist = info.get('uploader', '')
            thumbnail = info.get('thumbnail', '')
            
            # Ищем MP3 файлы
            mp3_files = list(Path(DOWNLOAD_FOLDER).glob('*.mp3'))
            if mp3_files:
                latest = max(mp3_files, key=lambda p: p.stat().st_mtime)
                return True, str(latest), {
                    'title': title,
                    'artist': artist,
                    'thumbnail': thumbnail,
                }
            
            return False, "MP3 файл не найден", {}
            
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        return False, f"Ошибка: {str(e)}", {}

def download_thumbnail(thumb_url: str) -> str:
    """Скачать обложку"""
    if not thumb_url:
        return None
    try:
        thumb_path = os.path.join(DOWNLOAD_FOLDER, 'thumbnail.jpg')
        urllib.request.urlretrieve(thumb_url, thumb_path)
        logger.info(f"Обложка: {thumb_path}")
        return thumb_path
    except Exception as e:
        logger.warning(f"Ошибка обложки: {e}")
        return None

# ===== СТАТИСТИКА =====

def load_stats() -> dict:
    """Загрузить статистику"""
    try:
        if Path(STATS_FILE).exists():
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'total_downloads': 0, 'total_users': 0, 'users': {}}

def save_stats(stats: dict) -> None:
    """Сохранить статистику"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except:
        pass

def update_user_stats(user_id: int, username: str) -> None:
    """Обновить статистику"""
    try:
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
    except:
        pass

def get_stats_text() -> str:
    """Получить текст статистики"""
    try:
        stats = load_stats()
        users = stats.get('users', {})
        top = sorted(users.items(), key=lambda x: x[1].get('downloads', 0), reverse=True)[:5]
        
        text = f"📊 СТАТИСТИКА\n🔢 Скачиваний: {stats.get('total_downloads', 0)}\n👥 Пользователей: {stats.get('total_users', 0)}\n\n🏆 ТОП:\n"
        for i, (_, data) in enumerate(top, 1):
            text += f"{i}. @{data.get('username')} - {data.get('downloads')} 🎵\n"
        return text
    except:
        return "❌ Ошибка статистики"

# ===== КОМАНДЫ =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    welcome_text = (
        "🎵 Добро пожаловать в SoundCloud Music Downloader!\n\n"
        "Просто отправь мне ссылку на трек с SoundCloud, и я скачаю его для тебя.\n\n"
        "Команды:\n"
        "/start - показать это сообщение\n"
        "/help - справка\n\n"
        "Пример: https://soundcloud.com/artist/track-name"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    help_text = (
        "📝 Справка:\n\n"
        "1. Скопируй ссылку на трек из SoundCloud\n"
        "2. Отправь её мне в чат\n"
        "3. Подожди, пока трек скачается\n"
        "4. Получи аудиофайл в формате MP3\n\n"
        "Имя файла будет очищено:\n"
        "- Пробелы заменены на подчёркивание\n"
        "- Удалены спецсимволы\n"
        "- Оставлены только буквы, цифры и дефис"
    )
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /stats - только для владельца"""
    owner_id = os.getenv("OWNER_ID")
    user_id = str(update.effective_user.id)
    
    if not owner_id or user_id != owner_id:
        await update.message.reply_text("❌ У тебя нет доступа")
        return
    
    await update.message.reply_text(get_stats_text())

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ссылок на SoundCloud"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    
    # Обновить статистику
    update_user_stats(user_id, username)
    
    # Проверка SoundCloud
    if "soundcloud.com" not in url:
        await update.message.reply_text("❌ Это не ссылка на SoundCloud.\nПожалуйста, отправь ссылку на трек с SoundCloud.")
        return
    
    # Статус
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    except:
        pass
    
    loading_msg = await update.message.reply_text("⏳ Ищу трек...")
    
    try:
        # Скачать
        success, result, info = await asyncio.to_thread(download_soundcloud, url)
        
        if success:
            file_path = Path(result)
            if file_path.exists():
                try:
                    # Получить чистый текст (без подчёркиваний)
                    clean_title = file_path.stem.replace('_', ' ')
                    artist = info.get('artist', '')
                    thumbnail = None
                    
                    # Скачать обложку если есть
                    if info.get('thumbnail'):
                        thumbnail = await asyncio.to_thread(download_thumbnail, info['thumbnail'])
                    
                    with open(file_path, 'rb') as audio_file:
                        await update.message.reply_audio(
                            audio_file,
                            title=clean_title,
                            performer=artist,
                            thumbnail=thumbnail,
                            caption=f"✅ {clean_title}"
                        )
                    logger.info(f"Файл отправлен: {file_path.name}")
                    
                    # Удалить файлы
                    try:
                        file_path.unlink()
                    except:
                        pass
                    
                    if thumbnail:
                        try:
                            Path(thumbnail).unlink()
                        except:
                            pass
                        
                except Exception as e:
                    logger.error(f"Ошибка отправки: {e}")
                    await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            else:
                await update.message.reply_text("❌ Файл не найден")
        else:
            await update.message.reply_text(f"❌ {result}")
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    finally:
        try:
            await loading_msg.delete()
        except:
            pass

def main():
    """Главная функция"""
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
