import os
import sys
import subprocess
from pathlib import Path

print("=" * 60)
print("🔍 ДИАГНОСТИКА SOUNDCLOUD БОТА")
print("=" * 60)

# Проверка Python
print("\n1️⃣ Проверка Python:")
print(f"   Версия: {sys.version}")
print(f"   Путь: {sys.executable}")

# Проверка FFmpeg
print("\n2️⃣ Проверка FFmpeg:")
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    if result.returncode == 0:
        first_line = result.stdout.split('\n')[0]
        print(f"   ✅ {first_line}")
    else:
        print("   ❌ FFmpeg не работает правильно")
except FileNotFoundError:
    print("   ❌ FFmpeg не установлен!")
    print("   ➜ Установи: choco install ffmpeg")

# Проверка pip пакетов
print("\n3️⃣ Проверка установленных пакетов:")
try:
    import telegram
    print(f"   ✅ python-telegram-bot: {telegram.__version__}")
except ImportError:
    print("   ❌ python-telegram-bot не установлен")

try:
    import yt_dlp
    print(f"   ✅ yt-dlp: {yt_dlp.__version__}")
except ImportError:
    print("   ❌ yt-dlp не установлен")

# Проверка файлов проекта
print("\n4️⃣ Проверка файлов проекта:")
required_files = ['soundcloud_bot.py', 'requirements.txt']
for file in required_files:
    if Path(file).exists():
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} НЕ НАЙДЕН")

# Проверка папки downloads
print("\n5️⃣ Проверка папки downloads:")
downloads_path = Path('downloads')
if downloads_path.exists():
    files = list(downloads_path.glob('*'))
    print(f"   ✅ Папка существует ({len(files)} файлов)")
    if files:
        for f in files[-5:]:  # Показываем последние 5 файлов
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"      - {f.name} ({size_mb:.1f} МБ)")
else:
    print(f"   ⚠️ Папка downloads не существует (будет создана автоматически)")

# Проверка интернета
print("\n6️⃣ Проверка интернета:")
try:
    import urllib.request
    urllib.request.urlopen('https://soundcloud.com', timeout=5)
    print("   ✅ Интернет подключен")
except Exception as e:
    print(f"   ❌ Нет доступа в интернет: {e}")

# Проверка токена
print("\n7️⃣ Проверка токена:")
token = os.getenv("TELEGRAM_BOT_TOKEN")
if token:
    print(f"   ✅ Переменная TELEGRAM_BOT_TOKEN установлена")
    print(f"      Токен (частично): {token[:20]}...{token[-10:]}")
else:
    print(f"   ❌ TELEGRAM_BOT_TOKEN не установлена")

print("\n" + "=" * 60)
print("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 60)
