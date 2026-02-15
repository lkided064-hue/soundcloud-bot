import logging
import os
import re
import asyncio
import json
from pathlib import Path
from datetime import datetime
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Папка для сохранения музыки
DOWNLOAD_FOLDER = "downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

# Файл для статистики
STATS_FILE = "bot_stats.json"

def clean_filename(filename: str) -> str:
    """Очистить имя файла от спецсимволов и лишних пробелов"""
    name, ext = os.path.splitext(filename)
    
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\-]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    
    return name + ext

def download_soundcloud(url: str) -> tuple[bool, str]:
    """Скачать трек с SoundCloud"""
    try:
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
            logger.info(f"Скачивание: {url}")
            info = ydl.extract_info(url, download=True)
            
            # Ищем MP3 файлы в папке
            mp3_files = list(Path(DOWNLOAD_FOLDER).glob('*.mp3'))
            if mp3_files:
                # Берём самый свежий файл
                latest = max(mp3_files, key=lambda p: p.stat().st_mtime)
                clean_name = clean_filename(latest.name)
                new_path = Path(DOWNLOAD_FOLDER) / clean_name
                
                if latest != new_path:
                    latest.rename(new_path)
                
                return True, str(new_path)
            
            return False, "MP3 файл не найден"
            
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {str(e)}")
        return False, f"Ошибка: {str(e)}"

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
    """Обработчик команды /start"""
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
    """Обработчик команды /help"""
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
    """Обработчик команды /stats - только для владельца"""
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
    
    # Проверка, что это ссылка на SoundCloud
    if "soundcloud.com" not in url:
        await update.message.reply_text("❌ Это не ссылка на SoundCloud.\nПожалуйста, отправь ссылку на трек с SoundCloud.")
        return
    
    # Отправить статус
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    except Exception as e:
        logger.warning(f"Не удалось отправить статус действия: {e}")
    
    loading_msg = await update.message.reply_text("⏳ Скачиваю трек...")
    
    try:
        # Скачать в отдельном потоке
        success, result = await asyncio.to_thread(download_soundcloud, url)
        
        if success:
            # Отправить файл
            file_path = Path(result)
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as audio_file:
                        await update.message.reply_audio(
                            audio_file,
                            caption=f"✅ {file_path.stem}"
                        )
                    logger.info(f"Файл отправлен: {file_path.name}")
                    
                    # Удалить локальный файл после отправки
                    try:
                        file_path.unlink()
                        logger.info(f"Локальный файл удалён: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить файл: {e}")
                        
                except Exception as e:
                    logger.error(f"Ошибка при отправке файла: {e}")
                    await update.message.reply_text(f"❌ Ошибка при отправке файла: {str(e)}")
            else:
                await update.message.reply_text("❌ Файл не найден после скачивания.")
        else:
            await update.message.reply_text(f"❌ {result}")
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Удалить сообщение о загрузке
        try:
            await loading_msg.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение о загрузке: {e}")

def main():
    """Главная функция бота"""
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Установи переменную окружения TELEGRAM_BOT_TOKEN")
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
