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

# Файл для сохранения статистики
STATS_FILE = "bot_stats.json"

def clean_filename(filename: str) -> str:
    """Очистить имя файла от спецсимволов и лишних пробелов"""
    # Удалить расширение для обработки
    name, ext = os.path.splitext(filename)
    
    # Заменить пробелы на подчёркивание
    name = re.sub(r'\s+', '_', name)
    
    # Удалить все спецсимволы кроме букв, цифр, подчёркивания и дефиса
    name = re.sub(r'[^\w\-]', '', name)
    
    # Удалить дублирующиеся подчёркивания
    name = re.sub(r'_+', '_', name)
    
    # Удалить подчёркивание в начале и конце
    name = name.strip('_')
    
    return name + ext

def get_track_info(url: str) -> dict:
    """Получить информацию о треке (название, артист, обложка)"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'title': info.get('title', ''),
                'artist': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
            }
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о треке: {e}")
        return {
            'title': '',
            'artist': '',
            'thumbnail': '',
            'duration': 0,
        }

def search_youtube_and_download(track_title: str, artist: str = "") -> tuple[bool, str]:
    """Поискать трек на YouTube и скачать как MP3"""
    try:
        # Формируем поисковый запрос
        search_query = f"{track_title} {artist}".strip()
        logger.info(f"Ищу на YouTube: {search_query}")
        
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
            'socket_timeout': 60,
            'http_chunk_size': 1024 * 1024,
            'default_search': 'ytsearch',  # Поиск на YouTube
            'noplaylist': True,  # Только одно видео
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Скачивание из YouTube: {search_query}")
            info = ydl.extract_info(search_query, download=True)
            
            # Получить название скачанного файла
            title = info.get('title', 'track')
            logger.info(f"Найдено на YouTube: {title}")
            
            # Очистить имя файла
            clean_name = clean_filename(title + '.mp3')
            file_path = Path(DOWNLOAD_FOLDER) / clean_name
            
            # Проверить, существует ли файл
            if file_path.exists():
                file_size = file_path.stat().st_size / (1024 * 1024)
                logger.info(f"Файл готов: {file_path} ({file_size:.1f} МБ)")
                return True, str(file_path)
            
            # Если нет, поищем самый свежий файл
            downloads_path = Path(DOWNLOAD_FOLDER)
            mp3_files = list(downloads_path.glob('*.mp3'))
            if mp3_files:
                latest_file = max(mp3_files, key=lambda p: p.stat().st_mtime)
                file_size = latest_file.stat().st_size / (1024 * 1024)
                logger.info(f"Файл найден: {latest_file} ({file_size:.1f} МБ)")
                return True, str(latest_file)
            
            return False, "Ошибка: файл не был создан"
            
    except Exception as e:
        logger.error(f"Ошибка при поиске на YouTube: {str(e)}", exc_info=True)
        return False, f"Ошибка поиска: {str(e)}"

# ===== ФУНКЦИИ СТАТИСТИКИ =====

def load_stats() -> dict:
    """Загрузить статистику из файла"""
    try:
        if Path(STATS_FILE).exists():
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Не удалось загрузить статистику: {e}")
    
    return {
        'total_downloads': 0,
        'total_users': 0,
        'users': {},
        'created_at': datetime.now().isoformat(),
    }

def save_stats(stats: dict) -> None:
    """Сохранить статистику в файл"""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.info("Статистика сохранена")
    except Exception as e:
        logger.warning(f"Не удалось сохранить статистику: {e}")

def update_user_stats(user_id: int, username: str, first_name: str) -> None:
    """Обновить статистику пользователя"""
    try:
        stats = load_stats()
        
        # Если пользователя ещё нет - добавить
        if str(user_id) not in stats['users']:
            stats['total_users'] += 1
            stats['users'][str(user_id)] = {
                'username': username or 'unknown',
                'first_name': first_name or 'unknown',
                'downloads': 0,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
            }
        else:
            # Обновить время последнего использования
            stats['users'][str(user_id)]['last_seen'] = datetime.now().isoformat()
        
        # Увеличить счётчики
        stats['users'][str(user_id)]['downloads'] += 1
        stats['total_downloads'] += 1
        
        save_stats(stats)
        logger.info(f"Статистика обновлена для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статистики: {e}")

def get_stats_text() -> str:
    """Получить текст со статистикой"""
    try:
        stats = load_stats()
        
        total_downloads = stats.get('total_downloads', 0)
        total_users = stats.get('total_users', 0)
        
        # Найти топ 5 пользователей
        users_list = stats.get('users', {})
        top_users = sorted(
            users_list.items(),
            key=lambda x: x[1].get('downloads', 0),
            reverse=True
        )[:5]
        
        text = f"""
📊 СТАТИСТИКА БОТА

🔢 Всего скачиваний: {total_downloads}
👥 Всего пользователей: {total_users}

🏆 ТОП-5 ПОЛЬЗОВАТЕЛЕЙ:
"""
        
        if top_users:
            for i, (user_id, user_data) in enumerate(top_users, 1):
                username = user_data.get('username', 'unknown')
                downloads = user_data.get('downloads', 0)
                text += f"{i}. @{username} - {downloads} скачиваний\n"
        else:
            text += "Пока нет пользователей\n"
        
        return text
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return "❌ Ошибка при получении статистики"

def download_soundcloud(url: str) -> tuple[bool, str]:
    """
    Скачать трек с SoundCloud
    Возвращает (успех, путь_файла_или_ошибка)
    """
    try:
        logger.info(f"Начинаю скачивание: {url}")
        
        # Уменьшенный битрейт для меньшего размера файла (быстрее скачивается и отправляется)
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # Уменьшено с 192 до 128 кбит/с
            }],
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s'),
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 60,
            'http_chunk_size': 1024 * 1024,  # 1MB chunks
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Скачивание: {url}")
            info = ydl.extract_info(url, download=True)
            
            # Получить название трека
            title = info.get('title', 'track')
            logger.info(f"Название трека: {title}")
            
            # Очистить имя файла
            clean_name = clean_filename(title + '.mp3')
            file_path = Path(DOWNLOAD_FOLDER) / clean_name
            
            logger.info(f"Ищу файл: {file_path}")
            
            # Проверить, существует ли файл с расширением .mp3
            if file_path.exists():
                logger.info(f"Файл найден: {file_path}")
                file_size = file_path.stat().st_size / (1024 * 1024)
                logger.info(f"Размер файла: {file_size:.1f} МБ")
                return True, str(file_path)
            
            # Если нет, поищем все файлы в папке downloads
            logger.warning(f"Файл {file_path} не найден, ищу в папке downloads")
            downloads_path = Path(DOWNLOAD_FOLDER)
            
            if downloads_path.exists():
                # Ищем самый свежий MP3 файл
                mp3_files = list(downloads_path.glob('*.mp3'))
                if mp3_files:
                    # Берём самый свежий файл
                    latest_file = max(mp3_files, key=lambda p: p.stat().st_mtime)
                    file_size = latest_file.stat().st_size / (1024 * 1024)
                    logger.info(f"Найден файл: {latest_file} ({file_size:.1f} МБ)")
                    return True, str(latest_file)
                
                # Если MP3 нет, ищем другие аудиофайлы
                audio_files = list(downloads_path.glob('*'))
                if audio_files:
                    latest_file = max(audio_files, key=lambda p: p.stat().st_mtime)
                    file_size = latest_file.stat().st_size / (1024 * 1024)
                    logger.info(f"Найден аудиофайл: {latest_file} ({file_size:.1f} МБ)")
                    return True, str(latest_file)
            
            logger.error(f"Файлы не найдены в папке {DOWNLOAD_FOLDER}")
            return False, "Ошибка: файл не был создан при скачивании"
            
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {str(e)}", exc_info=True)
        return False, f"Ошибка: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    welcome_text = (
        "🎵 Добро пожаловать в Music Downloader!\n\n"
        "Просто отправь мне ссылку на трек с одного из поддерживаемых сервисов, "
        "и я скачаю его для тебя.\n\n"
        "✅ Поддерживаемые сервисы:\n"
        "🎵 SoundCloud - прямое скачивание\n"
        "🎵 Spotify - поиск на YouTube\n"
        "🎵 YouTube - обычный YouTube\n"
        "🎵 Яндекс Музыка - поиск на YouTube\n"
        "🎵 VK Музыка - прямое скачивание\n"
        "🎵 Tidal - прямое скачивание\n\n"
        "Команды:\n"
        "/start - показать это сообщение\n"
        "/help - справка"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "📝 Справка:\n\n"
        "1. Скопируй ссылку на трек из поддерживаемого сервиса\n"
        "2. Отправь её мне в чат\n"
        "3. Подожди, пока трек скачается\n"
        "4. Получи аудиофайл в формате MP3\n\n"
        "✅ ПОДДЕРЖИВАЕМЫЕ СЕРВИСЫ:\n\n"
        "🎵 SoundCloud\n"
        "   Прямое скачивание, полная поддержка\n\n"
        "🎵 Spotify\n"
        "   Поиск трека на YouTube (обходит DRM)\n\n"
        "🎵 YouTube\n"
        "   Все видео с аудио\n\n"
        "🎵 Яндекс Музыка\n"
        "   Поиск трека на YouTube\n\n"
        "🎵 VK Музыка\n"
        "   Треки из ВКонтакте\n\n"
        "🎵 Tidal\n"
        "   Потоковый сервис\n\n"
        "💫 ОСОБЕННОСТИ:\n"
        "✓ Очистка имён файлов\n"
        "✓ Автоматическая обложка\n"
        "✓ MP3 128 кбит/с\n\n"
        "Команды:\n"
        "/start - приветствие\n"
        "/help - эта справка"
    )
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats - только для владельца"""
    # Получить ID владельца из переменной окружения
    owner_id = os.getenv("OWNER_ID")
    user_id = str(update.effective_user.id)
    
    # Проверить, является ли пользователь владельцем
    if owner_id and user_id != owner_id:
        await update.message.reply_text("❌ У тебя нет прав для просмотра статистики.\nЭта команда доступна только владельцу бота.")
        return
    
    stats_text = get_stats_text()
    await update.message.reply_text(stats_text)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ссылок на музыкальные сервисы"""
    url = update.message.text.strip()
    
    # Получить информацию о пользователе
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    # Поддерживаемые сервисы
    supported_services = {
        'soundcloud.com': '🎵 SoundCloud',
        'spotify.com': '🎵 Spotify',
        'youtu.be': '🎵 YouTube',
        'youtube.com': '🎵 YouTube',
        'music.yandex.ru': '🎵 Яндекс Музыка',
        'yandex.ru/music': '🎵 Яндекс Музыка',
        'vk.com': '🎵 VK Музыка',
        'vkontakte.ru': '🎵 VK Музыка',
        'tidal.com': '🎵 Tidal',
    }
    
    # Проверить, поддерживается ли сервис
    service_found = None
    for service, display_name in supported_services.items():
        if service in url.lower():
            service_found = display_name
            break
    
    if not service_found:
        available = "🎵 SoundCloud\n🎵 Spotify\n🎵 YouTube\n🎵 Яндекс Музыка\n🎵 VK Музыка\n🎵 Tidal"
        await update.message.reply_text(
            f"❌ Этот сервис пока не поддерживается.\n\n"
            f"Поддерживаемые сервисы:\n{available}"
        )
        return
    
    # Обновить статистику
    update_user_stats(user_id, username, first_name)
    
    # СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ SPOTIFY
    if 'spotify.com' in url.lower():
        loading_msg = await update.message.reply_text("⏳ Ищу трек на YouTube (Spotify требует поиск)...")
        try:
            # Получить информацию о треке из Spotify URL
            track_info = await asyncio.to_thread(get_track_info, url)
            track_title = track_info.get('title', '')
            artist = track_info.get('artist', '')
            
            if not track_title:
                # Если не получилось получить инфо, просто скажем пользователю
                await loading_msg.delete()
                await update.message.reply_text("❌ Не удалось получить информацию о треке Spotify.\n\nПопробуй скопировать название и артиста и отправь как текст.")
                return
            
            logger.info(f"Spotify трек: {track_title} - {artist}")
            
            # Скачать с YouTube
            success, result = await asyncio.to_thread(search_youtube_and_download, track_title, artist)
            
            if success:
                file_path = Path(result)
                if file_path.exists():
                    try:
                        with open(file_path, 'rb') as audio_file:
                            await update.message.reply_audio(
                                audio_file,
                                title=track_title,
                                performer=artist,
                                caption=f"✅ Найдено на YouTube\n{track_title}",
                                connect_timeout=60,
                                read_timeout=300,
                                write_timeout=300
                            )
                        logger.info(f"Spotify трек отправлен: {file_path.name}")
                        file_path.unlink()
                    except Exception as e:
                        logger.error(f"Ошибка отправки: {e}")
                        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            else:
                await update.message.reply_text(f"❌ {result}")
        
        except Exception as e:
            logger.error(f"Ошибка Spotify: {str(e)}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            try:
                await loading_msg.delete()
            except:
                pass
        return
    
    # СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ЯНДЕКС МУЗЫКИ
    if 'yandex' in url.lower() and 'music' in url.lower():
        loading_msg = await update.message.reply_text("⏳ Ищу трек на YouTube (Яндекс требует поиск)...")
        try:
            # Получить информацию о треке из Яндекс Музыки URL
            track_info = await asyncio.to_thread(get_track_info, url)
            track_title = track_info.get('title', '')
            artist = track_info.get('artist', '')
            
            if not track_title:
                await loading_msg.delete()
                await update.message.reply_text("❌ Не удалось получить информацию о треке Яндекс Музыки.\n\nПопробуй скопировать название и артиста.")
                return
            
            logger.info(f"Яндекс трек: {track_title} - {artist}")
            
            # Скачать с YouTube
            success, result = await asyncio.to_thread(search_youtube_and_download, track_title, artist)
            
            if success:
                file_path = Path(result)
                if file_path.exists():
                    try:
                        with open(file_path, 'rb') as audio_file:
                            await update.message.reply_audio(
                                audio_file,
                                title=track_title,
                                performer=artist,
                                caption=f"✅ Найдено на YouTube\n{track_title}",
                                connect_timeout=60,
                                read_timeout=300,
                                write_timeout=300
                            )
                        logger.info(f"Яндекс трек отправлен: {file_path.name}")
                        file_path.unlink()
                    except Exception as e:
                        logger.error(f"Ошибка отправки: {e}")
                        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            else:
                await update.message.reply_text(f"❌ {result}")
        
        except Exception as e:
            logger.error(f"Ошибка Яндекс: {str(e)}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        finally:
            try:
                await loading_msg.delete()
            except:
                pass
        return
    
    # ОБЫЧНАЯ ОБРАБОТКА (SoundCloud, YouTube, VK, Tidal)
    
    # Отправить статус "загружает видео"
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    except Exception as e:
        logger.warning(f"Не удалось отправить статус действия: {e}")
    
    loading_msg = await update.message.reply_text("⏳ Скачиваю трек...")
    
    try:
        # Скачать в отдельном потоке (чтобы не блокировать бота)
        success, result = await asyncio.to_thread(download_soundcloud, url)
        
        if success:
            # Отправить файл
            file_path = Path(result)
            if file_path.exists():
                try:
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    logger.info(f"Размер файла: {file_size_mb:.1f} МБ")
                    
                    # Проверить размер файла (максимум 50 МБ для Telegram)
                    if file_size_mb > 50:
                        await update.message.reply_text(f"❌ Файл слишком большой ({file_size_mb:.1f} МБ). Telegram не поддерживает файлы больше 50 МБ.")
                        logger.warning(f"Файл слишком большой: {file_size_mb:.1f} МБ")
                        return
                    
                    # Получить информацию о треке (название, артист, обложка)
                    track_info = await asyncio.to_thread(get_track_info, url)
                    logger.info(f"Информация о треке: {track_info}")
                    
                    # Скачать обложку трека если доступна
                    thumbnail = None
                    if track_info.get('thumbnail'):
                        try:
                            thumbnail_path = await asyncio.to_thread(download_thumbnail, track_info['thumbnail'])
                            if thumbnail_path and Path(thumbnail_path).exists():
                                thumbnail = thumbnail_path
                                logger.info(f"Обложка скачана: {thumbnail_path}")
                        except Exception as e:
                            logger.warning(f"Не удалось скачать обложку: {e}")
                    
                    # Отправить файл с повторными попытками
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"Попытка отправки {attempt + 1}/{max_retries}")
                            
                            # Подготовить информацию для отправки
                            title = track_info.get('title', file_path.stem) or file_path.stem
                            artist = track_info.get('artist', '')
                            
                            caption = title
                            if artist:
                                caption = f"{artist} - {title}"
                            
                            with open(file_path, 'rb') as audio_file:
                                await update.message.reply_audio(
                                    audio_file,
                                    title=title,
                                    performer=artist,
                                    thumbnail=thumbnail,
                                    caption=None,  # Не используем caption
                                    connect_timeout=60,
                                    read_timeout=300,
                                    write_timeout=300
                                )
                            
                            logger.info(f"Файл успешно отправлен: {file_path.name}")
                            break
                            
                        except asyncio.TimeoutError:
                            logger.warning(f"Таймаут при отправке (попытка {attempt + 1})")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(5)  # Подожди 5 секунд перед повтором
                            else:
                                raise
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.warning(f"Ошибка при отправке (попытка {attempt + 1}): {e}")
                                await asyncio.sleep(5)
                            else:
                                raise
                    
                    # Удалить локальный файл после отправки
                    try:
                        file_path.unlink()
                        logger.info(f"Локальный файл удалён: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить файл: {e}")
                    
                    # Удалить обложку если была скачана
                    if thumbnail:
                        try:
                            Path(thumbnail).unlink()
                            logger.info(f"Обложка удалена: {thumbnail}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить обложку: {e}")
                        
                except asyncio.TimeoutError:
                    logger.error(f"Ошибка: Таймаут при отправке файла")
                    await update.message.reply_text("❌ Ошибка: Превышено время ожидания при отправке файла. Попробуй позже.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке файла: {e}", exc_info=True)
                    await update.message.reply_text(f"❌ Ошибка при отправке файла: {str(e)}")
            else:
                await update.message.reply_text("❌ Файл не найден после скачивания.")
        else:
            await update.message.reply_text(f"❌ {result}")
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    finally:
        # Удалить сообщение о загрузке
        try:
            await loading_msg.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение о загрузке: {e}")

def main():
    """Главная функция бота"""
    # Замени на свой токен от BotFather
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Установи переменную окружения TELEGRAM_BOT_TOKEN")
        return
    
    # Создать приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавить обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("🤖 Бот запущен!")
    
    # Запустить бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
