import os

# Основные настройки бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', "7831575649:AAH57uaUdPdEq5V5_fwDWARGVjmfXRLLMW4")
API_ID = os.getenv('API_ID', '34000428')
API_HASH = os.getenv('API_HASH', '68c4db995c26cda0187e723168cc6285')

# СЕССИЯ
SESSION_FILE = os.getenv('SESSION_FILE')
SESSION_STRING = os.getenv('SESSION_STRING', "1AgAOMTQ5LjE1NC4xNjcuNDEBu42Ajzk8wH+OKtuvQYjMT+jpw9cHg2CFHGYju7u8V8j52qp2Kg2dasqC5KrFnTfTg3r1N568pfHLeCCVt20lTnHRGZmSu29n19EreqbtAFDZh49fE6B7KIOHHxwOdBRl0jukNHRXlAdPyNPKvE0SRSuMg5VzVVLY4lCjWzrIeRjFO5I5B/kMQnDJBR7k5L4P5zgruE3qbntgaiMDaJmn2c9RbH7a0N+STBCOn5KhEZX7xq72XydZgOia/uI5q3OFN1huvDwcQMMyAkVLkcmvP/BvGU+SRrM9AVxUYZE+37DWwYJutVCbxgtEjAjhEVgYzJ+HENnyRWHr1vgyCRmQqSY=")

# Каналы для подписки
CHANNELS = [
    {'id': -1002938353350, 'name': 'WakeFreez', 'url': 'https://t.me/WakeDeff'},
    {'id': -1002504179787, 'name': 'Логи', 'url': 'https://t.me/WakeNft'}
]

# ГРУППЫ ДЛЯ БАНА
GROUPS = [
    -1003638659955,
    -1003524689431,
    -1003532499825,
    -1003550169206,
    -1003553874960,
    -1003560527969,
    -1003569121206,
    -1003611895403,
    -1003636555785,
    -1003663318633,
    -1003586917703,
    -1003668973847,
    -1003550241722,
    -1003610626300,
    -1003652277998,
    -1003576429923,
    -1003680248803,
    -1003697025287,
    -1003510489331,
    -1003689576802,
    -1003687671247,
    -1003355183473,
    -1003651010227,
    -1003586116805,
    -1003524689431,
    -1003532499825,
    -1003550169206,
    -1003660768783,
    -1003550990838,
    -1003608338829,
    -1003536552505,
    -1003527919582,
    -1003273890583
]

# Логи
LOG_CHANNEL_ID = -1002504179787
LOGS_LINK = 'https://t.me/WakeNft'

# Настройки Crypto Pay
CRYPTOPAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN', "482874:AAuE5RiV2VKd55z0uQzPy18MMKsRvfu8DI2")
CRYPTOPAY_API_URL = os.getenv('CRYPTOPAY_API_URL', 'https://pay.crypt.bot/api/')

# Админы бота
ADMINS = list(map(int, os.getenv('ADMINS', '5522585352').split(',')))

def validate_config():
    """Проверяет обязательные настройки"""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
    if not API_ID:
        raise ValueError("API_ID не установлен")
    if not API_HASH:
        raise ValueError("API_HASH не установлен")
    if not SESSION_STRING and not SESSION_FILE:
        raise ValueError("Укажите либо SESSION_STRING, либо SESSION_FILE")
    
    print("✅ Конфигурация проверена успешно")
    if SESSION_STRING:
        print("📱 Используется строка сессии")
    else:
        print("📁 Используется файл сессии:", SESSION_FILE)

try:
    validate_config()
except ValueError as e:
    print(f"⚠️ Внимание: {e}")