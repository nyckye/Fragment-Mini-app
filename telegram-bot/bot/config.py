import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# BOT CONFIGURATION 

BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
WEB_APP_URL = os.getenv('WEB_APP_URL', '').strip()
ADMIN_ID = os.getenv('ADMIN_ID', '').strip()

# VALIDATION 

if not BOT_TOKEN or BOT_TOKEN == 'ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER':
    print("\n❌ ERROR: BOT_TOKEN не настроен!")
    print("\n📝 Как исправить:")
    print("1. Открой @BotFather в Telegram")
    print("2. Создай бота командой /newbot")
    print("3. Скопируй токен")
    print("4. Открой файл .env")
    print("5. Вставь токен в строку: BOT_TOKEN=твой_токен\n")
    exit(1)

if not WEB_APP_URL or WEB_APP_URL == 'https://webstorstars.duckdns.org':
    print("\n⚠️  WARNING: Используется URL по умолчанию")
    print("   WEB_APP_URL = https://webstorstars.duckdns.org")
    print("\n   Если это не твой домен, измени в .env\n")

if not ADMIN_ID or ADMIN_ID == 'ВСТАВЬ_СЮДА_СВОЙ_TELEGRAM_ID':
    print("\n❌ ERROR: ADMIN_ID не настроен!")
    print("\n📝 Как исправить:")
    print("1. Напиши боту @userinfobot")
    print("2. Он покажет твой ID (например: 123456789)")
    print("3. Открой файл .env")
    print("4. Вставь ID в строку: ADMIN_ID=твой_id\n")
    exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    print(f"\n❌ ERROR: ADMIN_ID должен быть числом!")
    print(f"   Сейчас: ADMIN_ID = {ADMIN_ID}")
    print(f"\n📝 Исправь в .env: ADMIN_ID=123456789\n")
    exit(1)

#  SUCCESS 

print("\n✅ Конфигурация загружена успешно!")
print(f"📱 Web App URL: {WEB_APP_URL}")
print(f"👤 Admin ID: {ADMIN_ID}")
print(f"🤖 Bot Token: {BOT_TOKEN[:20]}...\n")
