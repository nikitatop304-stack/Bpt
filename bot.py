import telebot
from telebot import types
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import UserProfilePhoto, ChatPhoto, Photo
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
import asyncio
import time
from threading import Thread
import requests
import json
from datetime import datetime, timedelta
import sqlite3
import traceback
import random
import sys
import os

# ========== ЖЕСТКИЙ КОНФИГ - БЕЗ .env ==========
print("=" * 60)
print("🤖 MONOFREEZ BOT - ПРЯМАЯ ЗАГРУЗКА")
print("=" * 60)

# 🔥 ВСТАВЬ СЮДА СВОЙ ТОКЕН! 🔥
TELEGRAM_BOT_TOKEN = "7831575649:AAFgFYsY7afjBL9PX1JKma9zK0GrpULcBaY"  # ЗАМЕНИ НА СВОЙ!

# Проверка токена
print(f"🔐 Проверяю токен...")
if not TELEGRAM_BOT_TOKEN or ':' not in TELEGRAM_BOT_TOKEN:
    print(f"❌ ТОКЕН НЕВАЛИДНЫЙ!")
    print(f"   Получено: '{TELEGRAM_BOT_TOKEN}'")
    print(f"   Формат должен быть: '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz'")
    print(f"   Получи новый: @BotFather → /mybots → API Token")
    sys.exit(1)

bot_id, bot_secret = TELEGRAM_BOT_TOKEN.split(':', 1)
print(f"✅ Токен валидный!")
print(f"   ID бота: {bot_id}")
print(f"   Секрет: {bot_secret[:5]}...")

# Telegram API (получить на https://my.telegram.org)
API_ID = 34000428  # Должно быть ЧИСЛОМ!
API_HASH = "68c4db995c26cda0187e723168cc6285"

# Строка сессии Telethon
SESSION_STRING = "1AgAOMTQ5LjE1NC4xNjcuNDEBu42Ajzk8wH+OKtuvQYjMT+jpw9cHg2CFHGYju7u8V8j52qp2Kg2dasqC5KrFnTfTg3r1N568pfHLeCCVt20lTnHRGZmSu29n19EreqbtAFDZh49fE6B7KIOHHxwOdBRl0jukNHRXlAdPyNPKvE0SRSuMg5VzVVLY4lCjWzrIeRjFO5I5B/kMQnDJBR7k5L4P5zgruE3qbntgaiMDaJmn2c9RbH7a0N+STBCOn5KhEZX7xq72XydZgOia/uI5q3OFN1huvDwcQMMyAkVLkcmvP/BvGU+SRrM9AVxUYZE+37DWwYJutVCbxgtEjAjhEVgYzJ+HENnyRWHr1vgyCRmQqSY="

# Crypto Pay
CRYPTOPAY_TOKEN = "482874:AAuE5RiV2VKd55z0uQzPy18MMKsRvfu8DI2"
CRYPTOPAY_API_URL = "https://pay.crypt.bot/api/"

# Админы
ADMINS = [5522585352]

# Каналы для подписки
CHANNELS = [
    {'id': -1002938353350, 'name': 'WakeFreez', 'url': 'https://t.me/WakeDeff'},
    {'id': -1002504179787, 'name': 'Логи', 'url': 'https://t.me/WakeNft'}
]

# Группы для бана
GROUPS = [
    -1003638659955, -1003524689431, -1003532499825, -1003550169206,
    -1003553874960, -1003560527969, -1003569121206, -1003611895403,
    -1003636555785, -1003663318633, -1003586917703, -1003668973847,
    -1003550241722, -1003610626300, -1003652277998, -1003576429923,
    -1003680248803, -1003697025287, -1003510489331, -1003689576802,
    -1003687671247, -1003355183473, -1003651010227, -1003586116805,
    -1003524689431, -1003532499825, -1003550169206, -1003660768783,
    -1003550990838, -1003608338829, -1003536552505, -1003527919582,
    -1003273890583
]

# Логи
LOG_CHANNEL_ID = -1002504179787
LOGS_LINK = 'https://t.me/WakeNft'

print("=" * 60)
print("✅ КОНФИГ ЗАГРУЖЕН УСПЕШНО!")
print(f"🤖 Бот: @{bot_id}")
print(f"👑 Админы: {len(ADMINS)}")
print(f"📢 Каналов: {len(CHANNELS)}")
print(f"📊 Групп: {len(GROUPS)}")
print("=" * 60)

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
print("🚀 Инициализирую бота...")
try:
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True, num_threads=10)
    print("✅ Бот инициализирован!")
    
    # Тестовая команда
    @bot.message_handler(commands=['ping'])
    def ping_command(message):
        bot.reply_to(message, "🏓 Понг! Бот работает!")
        
except Exception as e:
    print(f"❌ Ошибка инициализации бота: {e}")
    sys.exit(1)

# ========== КОНСТАНТЫ ==========
SUBSCRIPTION_PLANS = {
    '1_day': {'days': 1, 'price': 2.0, 'label': '1 день - 2$'},
    '7_days': {'days': 7, 'price': 4.5, 'label': '7 дней - 4.5$'},
    '30_days': {'days': 30, 'price': 8.0, 'label': '30 дней - 8$'},
    '90_days': {'days': 90, 'price': 13.0, 'label': '90 дней - 13$'}
}

TELEGRAM_API_DELAY = 0.5
MAX_RETRIES = 3
REQUEST_COOLDOWN = 300

# ========== ЛОГИРОВАНИЕ ==========
class Logger:
    @staticmethod
    def debug(msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()
    
    @staticmethod
    def error(msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"❌ [{timestamp}] {msg}")
        sys.stdout.flush()

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        
        # Простые таблицы
        tables = [
            '''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expires DATETIME,
                plan TEXT,
                created DATETIME DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                target TEXT,
                time DATETIME DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        
        for table in tables:
            try:
                cursor.execute(table)
            except:
                pass
        
        self.conn.commit()
        Logger.debug("База данных инициализирована")
    
    def add_user(self, user_id, username, first_name, last_name):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            self.conn.commit()
        except Exception as e:
            Logger.error(f"Ошибка добавления пользователя: {e}")
    
    def get_subscription(self, user_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM subscriptions WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {'user_id': row[0], 'expires': row[1], 'plan': row[2]}
            return None
        except:
            return None
    
    def add_subscription(self, user_id, days):
        expires = datetime.now() + timedelta(days=days)
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO subscriptions (user_id, expires, plan)
                VALUES (?, ?, ?)
            ''', (user_id, expires, f'{days}_days'))
            self.conn.commit()
            return True
        except Exception as e:
            Logger.error(f"Ошибка добавления подписки: {e}")
            return False
    
    def add_log(self, user_id, action, target=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute('INSERT INTO logs (user_id, action, target) VALUES (?, ?, ?)', 
                          (user_id, action, target))
            self.conn.commit()
        except:
            pass

db = Database()

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
def is_admin(user_id):
    return user_id in ADMINS

def check_subscription(user_id):
    sub = db.get_subscription(user_id)
    if not sub:
        return False
    
    expires = datetime.strptime(sub['expires'], '%Y-%m-%d %H:%M:%S')
    return datetime.now() < expires

def check_channels(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel['id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

# ========== КОМАНДА /start ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    if not check_subscription(user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 Купить подписку", callback_data='buy'))
        bot.send_message(message.chat.id, "❌ Нет подписки!", reply_markup=markup)
        return
    
    if not check_channels(user.id):
        markup = types.InlineKeyboardMarkup()
        for channel in CHANNELS:
            markup.add(types.InlineKeyboardButton(channel['name'], url=channel['url']))
        markup.add(types.InlineKeyboardButton("✅ Проверить", callback_data='check'))
        bot.send_message(message.chat.id, "📢 Подпишитесь на каналы:", reply_markup=markup)
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔨 Бан", callback_data='ban'))
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data='profile'))
    
    bot.send_message(message.chat.id, "👋 Добро пожаловать! Выберите действие:", reply_markup=markup)

# ========== КОМАНДА /admin ==========
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Нет прав!")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Выдать подписку", callback_data='admin_give'))
    markup.add(types.InlineKeyboardButton("📊 Статистика", callback_data='admin_stats'))
    
    bot.send_message(message.chat.id, "👑 Админ-панель:", reply_markup=markup)

# ========== КОЛБЭКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == 'buy':
        markup = types.InlineKeyboardMarkup()
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            markup.add(types.InlineKeyboardButton(plan['label'], callback_data=f'plan_{plan_id}'))
        
        bot.edit_message_text("Выберите план:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data.startswith('plan_'):
        plan_id = call.data.replace('plan_', '')
        plan = SUBSCRIPTION_PLANS[plan_id]
        
        bot.edit_message_text(
            f"План: {plan['label']}\nЦена: {plan['price']}$\n\nОплатите на @CryptoBot",
            call.message.chat.id,
            call.message.message_id
        )
    
    elif call.data == 'ban':
        if not check_subscription(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Нет подписки!", show_alert=True)
            return
        
        msg = bot.send_message(call.message.chat.id, "Введите @username для бана:")
        bot.register_next_step_handler(msg, process_ban)
    
    elif call.data == 'profile':
        sub = db.get_subscription(call.from_user.id)
        if sub:
            expires = datetime.strptime(sub['expires'], '%Y-%m-%d %H:%M:%S')
            text = f"👤 Ваш профиль\n\nПодписка до: {expires.strftime('%d.%m.%Y %H:%M')}"
        else:
            text = "👤 Ваш профиль\n\n❌ Нет подписки"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)

def process_ban(message):
    username = message.text.strip().replace('@', '')
    if not username:
        bot.send_message(message.chat.id, "❌ Неверный username")
        return
    
    bot.send_message(message.chat.id, f"⏳ Начинаю бан @{username}...")
    db.add_log(message.from_user.id, 'ban_attempt', username)
    
    # Здесь будет логика бана
    bot.send_message(message.chat.id, f"✅ Запрос на бан @{username} принят!")

# ========== ЗАПУСК ==========
print("🚀 Запускаю бота...")
print("📌 Команды: /start, /admin, /ping")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except Exception as e:
        Logger.error(f"Ошибка: {e}")
        print("🔄 Перезапуск через 5 секунд...")
        time.sleep(5)
