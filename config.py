import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# ========== ПОЛУЧЕНИЕ ТОКЕНОВ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==========

# Токен бота Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    print("⚠️ ВНИМАНИЕ: TELEGRAM_BOT_TOKEN не установлен в .env файле!")
    print("❌ Бот не будет работать без токена")
    exit(1)

# API ID и Hash для Telethon
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
    print("⚠️ ВНИМАНИЕ: API_ID или API_HASH не установлены в .env файле!")
    print("⚠️ Функции Telethon могут не работать")

# Строка сессии Telethon
SESSION_STRING = os.getenv('SESSION_STRING')

# Токен Crypto Pay
CRYPTOPAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN')
CRYPTOPAY_API_URL = os.getenv('CRYPTOPAY_API_URL', 'https://pay.crypt.bot/api/')

# Админы бота
ADMINS_STR = os.getenv('ADMINS', '')
if ADMINS_STR:
    ADMINS = list(map(int, ADMINS_STR.split(',')))
else:
    ADMINS = []
    print("⚠️ ВНИМАНИЕ: ADMINS не установлены в .env файле!")

# ========== ПРОВЕРКА КОНФИГУРАЦИИ ==========

def validate_config():
    """Проверяет обязательные настройки"""
    errors = []
    
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не установлен")
    
    if not API_ID:
        errors.append("API_ID не установлен")
    elif not API_ID.isdigit():
        errors.append("API_ID должен быть числом")
    else:
        API_ID = int(API_ID)
    
    if not API_HASH:
        errors.append("API_HASH не установлен")
    
    if not SESSION_STRING:
        print("⚠️ Предупреждение: SESSION_STRING не установлен")
        print("   Telethon сессии будут храниться в файле")
    
    if errors:
        print("\n❌ Ошибки конфигурации:")
        for error in errors:
            print(f"   - {error}")
        print("\n📁 Проверьте .env файл")
        return False
    
    return True

# ========== ВЫВОД ИНФОРМАЦИИ (БЕЗ ПОЛНЫХ КЛЮЧЕЙ) ==========

print("✅ Конфигурация загружена из .env файла")
print(f"🤖 Бот: {TELEGRAM_BOT_TOKEN[:15]}...")
print(f"🔑 API ID: {API_ID[:5]}...") if API_ID else print("🔑 API ID: Не установлен")
print(f"👥 Админы: {len(ADMINS)} пользователей")
if CRYPTOPAY_TOKEN:
    print(f"💰 Crypto Pay: настроен")
else:
    print("⚠️ Crypto Pay: токен не установлен")

# Проверяем конфигурацию
if not validate_config():
    exit(1)

# ========== ОСТАЛЬНОЙ КОД (каналы, группы, логи) ==========

# Каналы для подписки (остаются как были)
CHANNELS = [
    {'id': -1002938353350, 'name': 'WakeFreez', 'url': 'https://t.me/WakeDeff'},
    {'id': -1002504179787, 'name': 'Логи', 'url': 'https://t.me/WakeNft'}
]

# Группы для бана (остаются как были)
GROUPS = [
    -1003638659955,
    -1003524689431,
    # ... остальные группы
]

# Логи
LOG_CHANNEL_ID = -1002504179787
LOGS_LINK = 'https://t.me/WakeNft'

print(f"\n📊 Настроено:")
print(f"   📢 Каналов для подписки: {len(CHANNELS)}")
print(f"   🚫 Групп для бана: {len(GROUPS)}")
print(f"   📝 Логирование в: {LOG_CHANNEL_ID}")
