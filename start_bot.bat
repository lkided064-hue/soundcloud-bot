@echo off
cd /d C:\Users\shin\Desktop\MusicBOT
call venv\Scripts\activate.bat
set TELEGRAM_BOT_TOKEN=8299611361:AAGVpVQ5I3hMmveFRRzlkGzy7xcWhlxzeo4
python soundcloud_bot.py
pause