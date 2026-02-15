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
    name = name.strip('_')
    return name + ext

def download_music(url: str) -> tuple[bool, str]:
    """Скачать трек"""
    try:
        logger.info(f"Скачивание: {url}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_filename = ydl.prepare_filename(info)
            
            original_path = Path(original_filename)
            clean_name = clean_filename(original_path.name)
            new_path = original_path.parent / clean_name
            
            if original_path.exists() and original_path != new_path:
                original_path.rename(new_path)
                return True, str(new_path)
            
            return True, original_filename
            
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        return False, f"Ошибка: {str(e)}"

def search_music(query: str) -> tuple[bool, str]:
    """Поиск музыки на YouTube"""
    try:
        logger.info(f"Поиск: {query}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'default_search': 'ytsearch',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            original_filename = ydl.prepare_filename(info)
            
            original_path = Path(original_filename)
            clean_name = clean_filename(original_path.name)
            new_path = original_path.parent / clean_name
            
            if original_path.exists() and original_path != new_path:
                original_path.rename(new_path)
                return True, str(new_path)
            
            return True, original_filename
            
    except Exception as e:
        logger.error(f"Ошибка поиска: {str(e)}")
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
    except Exception as e:
        logger.warning(f"Ошибка статистики: {e}")

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
        "🎵 Добро пожаловать в Music Downloader!\n\n"
        "Отправь ссылку на трек:\n"
        "🎵 SoundCloud\n"
        "🎵 Spotify\n"
        "🎵 YouTube\n"
        "🎵 Яндекс Музыка\n"
        "🎵 VK Музыка\n"
        "🎵 Tidal\n\n"
        "Команды:\n"
        "/start - это сообщение\n"
        "/help - справка"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help"""
    help_text = (
        "📝 Справка:\n\n"
        "1. Скопируй ссылку на трек\n"
        "2. Отправь в чат\n"
        "3. Получи MP3 файл\n\n"
        "✅ Поддерживаемые сервисы:\n"
        "🎵 SoundCloud\n"
        "🎵 Spotify\n"
        "🎵 YouTube\n"
        "🎵 Яндекс Музыка\n"
        "🎵 VK Музыка\n"
        "🎵 Tidal\n\n"
        "💫 Файл будет очищен:\n"
        "✓ Пробелы → подчёркивание\n"
        "✓ Спецсимволы удалены\n"
        "✓ MP3 192 кбит/с"
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
    """Обработчик ссылок"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    
    # Обновить статистику
    update_user_stats(user_id, username)
    
    # Проверка сервиса
    supported = ['soundcloud.com', 'spotify.com', 'youtube.com', 'youtu.be', 'yandex', 'vk.com', 'vkontakte.ru', 'tidal.com']
    
    if not any(s in url.lower() for s in supported):
        await update.message.reply_text("❌ Сервис не поддерживается")
        return
    
    # Статус
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    except:
        pass
    
    loading_msg = await update.message.reply_text("⏳ Ищу трек...")
    
    try:
        # Spotify и Яндекс - ищем на YouTube
        if 'spotify.com' in url.lower() or 'yandex' in url.lower():
            success, result = await asyncio.to_thread(search_music, url)
        else:
            success, result = await asyncio.to_thread(download_music, url)
        
        if success:
            file_path = Path(result)
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as audio_file:
                        await update.message.reply_audio(
                            audio_file,
                            caption=f"✅ {file_path.stem}"
                        )
                    logger.info(f"Отправлено: {file_path.name}")
                    
                    try:
                        file_path.unlink()
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
