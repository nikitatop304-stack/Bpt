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

# ========== КОНФИГУРАЦИЯ ==========
# ВАЖНО: создай файл .env в той же папке с этими данными!

# Импортируем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# Telegram Bot Token (получить у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7831575649:AAFgFYsY7afjBL9PX1JKma9zK0GrpULcBaY')

# Telegram API (получить на my.telegram.org)
API_ID = int(os.getenv('API_ID', '34000428'))
API_HASH = os.getenv('API_HASH', '68c4db995c26cda0187e723168cc6285')

# Telethon Session (строка сессии)
SESSION_STRING = os.getenv('SESSION_STRING', '1AgAOMTQ5LjE1NC4xNjcuNDEBu42Ajzk8wH+OKtuvQYjMT+jpw9cHg2CFHGYju7u8V8j52qp2Kg2dasqC5KrFnTfTg3r1N568pfHLeCCVt20lTnHRGZmSu29n19EreqbtAFDZh49fE6B7KIOHHxwOdBRl0jukNHRXlAdPyNPKvE0SRSuMg5VzVVLY4lCjWzrIeRjFO5I5B/kMQnDJBR7k5L4P5zgruE3qbntgaiMDaJmn2c9RbH7a0N+STBCOn5KhEZX7xq72XydZgOia/uI5q3OFN1huvDwcQMMyAkVLkcmvP/BvGU+SRrM9AVxUYZE+37DWwYJutVCbxgtEjAjhEVgYzJ+HENnyRWHr1vgyCRmQqSY=')

# Crypto Pay Token (получить у @CryptoBot)
CRYPTOPAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN', '482874:AAuE5RiV2VKd55z0uQzPy18MMKsRvfu8DI2')
CRYPTOPAY_API_URL = os.getenv('CRYPTOPAY_API_URL', 'https://pay.crypt.bot/api/')

# Админы бота (ID через запятую)
ADMINS_STR = os.getenv('ADMINS', '5522585352')
ADMINS = []
if ADMINS_STR:
    for admin_id in ADMINS_STR.split(','):
        try:
            ADMINS.append(int(admin_id.strip()))
        except:
            pass

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

# Тарифы подписок
SUBSCRIPTION_PLANS = {
    '1_day': {'days': 1, 'price': 2.0, 'label': '1 день - 2$'},
    '7_days': {'days': 7, 'price': 4.5, 'label': '7 дней - 4.5$'},
    '30_days': {'days': 30, 'price': 8.0, 'label': '30 дней - 8$'},
    '90_days': {'days': 90, 'price': 13.0, 'label': '90 дней - 13$'}
}

# Настройки
TELEGRAM_API_DELAY = 0.5
MAX_RETRIES = 3
REQUEST_COOLDOWN = 300  # 5 минут

# ========== ИНИЦИАЛИЗАЦИЯ ==========
print("=" * 50)
print("🤖 Запуск бота MonoFreez...")
print(f"🔑 Токен: {TELEGRAM_BOT_TOKEN[:15]}...")
print(f"👑 Админы: {ADMINS}")
print(f"📢 Каналов: {len(CHANNELS)}")
print(f"📊 Групп: {len(GROUPS)}")
print("=" * 50)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True, num_threads=10)

# ========== ЛОГИРОВАНИЕ ==========
def debug_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[DEBUG {timestamp}] {message}")
    sys.stdout.flush()

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self, db_name='bot_database.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        tables = [
            '''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0
            )''',
            
            '''CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_id TEXT,
                expires_at TIMESTAMP,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_id INTEGER,
                days INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )''',
            
            '''CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT UNIQUE,
                user_id INTEGER,
                amount REAL,
                asset TEXT,
                plan_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )''',
            
            '''CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_username TEXT,
                action TEXT,
                details TEXT DEFAULT '',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
            )''',
            
            '''CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )''',
            
            '''CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_user_id INTEGER,
                target_username TEXT,
                banned_by INTEGER,
                groups_banned INTEGER,
                total_groups INTEGER,
                errors TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (banned_by) REFERENCES users (user_id) ON DELETE SET NULL
            )''',
            
            '''CREATE TABLE IF NOT EXISTS group_stats (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                bans_sent INTEGER DEFAULT 0,
                last_activity TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )'''
        ]
        
        for table_sql in tables:
            try:
                cursor.execute(table_sql)
            except Exception as e:
                debug_log(f"Ошибка создания таблицы: {e}")
        
        conn.commit()
        conn.close()
        debug_log(f"База данных {self.db_name} инициализирована")
    
    def add_user(self, user_id, username, first_name, last_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
            debug_log(f"Пользователь {user_id} добавлен")
        except Exception as e:
            debug_log(f"Ошибка добавления пользователя {user_id}: {e}")
        finally:
            conn.close()
    
    def update_activity(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            debug_log(f"Ошибка обновления активности {user_id}: {e}")
        finally:
            conn.close()
    
    def is_user_banned(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result and result[0] == 1
        except Exception as e:
            debug_log(f"Ошибка проверки бана {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_active_subscription(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM subscriptions 
                WHERE user_id = ? AND is_active = 1 AND expires_at > datetime('now')
                LIMIT 1
            ''', (user_id,))
            
            result = cursor.fetchone()
            if result:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            debug_log(f"Ошибка получения подписки {user_id}: {e}")
            return None
        finally:
            conn.close()
    
    def add_subscription(self, user_id, plan_id, days, admin_id=None):
        expires_at = datetime.now() + timedelta(days=days)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Деактивируем старые подписки
            cursor.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1', (user_id,))
            
            # Добавляем новую
            cursor.execute('''
                INSERT INTO subscriptions (user_id, plan_id, expires_at, admin_id, days)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, plan_id, expires_at, admin_id, days))
            
            conn.commit()
            debug_log(f"Подписка добавлена: user={user_id}, days={days}")
            return True
        except Exception as e:
            debug_log(f"Ошибка добавления подписки: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def remove_subscription(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1', (user_id,))
            conn.commit()
            debug_log(f"Подписка удалена для user_id={user_id}")
            return True
        except Exception as e:
            debug_log(f"Ошибка удаления подписки {user_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def add_invoice(self, invoice_id, user_id, amount, asset, plan_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoices (invoice_id, user_id, amount, asset, plan_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (invoice_id, user_id, amount, asset, plan_id))
            conn.commit()
            debug_log(f"Счет {invoice_id} добавлен для user_id={user_id}")
            return True
        except sqlite3.IntegrityError:
            debug_log(f"Счет {invoice_id} уже существует")
            return False
        except Exception as e:
            debug_log(f"Ошибка добавления счета: {e}")
            return False
        finally:
            conn.close()
    
    def update_invoice(self, invoice_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if status == 'paid':
                cursor.execute('''
                    UPDATE invoices 
                    SET status = ?, paid_at = datetime('now') 
                    WHERE invoice_id = ?
                ''', (status, invoice_id))
            else:
                cursor.execute('UPDATE invoices SET status = ? WHERE invoice_id = ?', (status, invoice_id))
            
            conn.commit()
            debug_log(f"Счет {invoice_id} обновлен: {status}")
            return True
        except Exception as e:
            debug_log(f"Ошибка обновления счета {invoice_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_invoice(self, invoice_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM invoices WHERE invoice_id = ?', (invoice_id,))
            result = cursor.fetchone()
            if result:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            debug_log(f"Ошибка получения счета {invoice_id}: {e}")
            return None
        finally:
            conn.close()
    
    def set_cooldown(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO cooldowns (user_id, last_used)
                VALUES (?, datetime('now'))
            ''', (user_id,))
            conn.commit()
            return True
        except Exception as e:
            debug_log(f"Ошибка установки кулдауна {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_cooldown(self, user_id, cooldown_seconds=REQUEST_COOLDOWN):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT last_used FROM cooldowns WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result:
                last_used = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                time_passed = (datetime.now() - last_used).total_seconds()
                if time_passed < cooldown_seconds:
                    return cooldown_seconds - time_passed
            return 0
        except Exception as e:
            debug_log(f"Ошибка получения кулдауна {user_id}: {e}")
            return 0
        finally:
            conn.close()
    
    def add_log(self, user_id, action, target=None, details=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO logs (user_id, target_username, action, details)
                VALUES (?, ?, ?, ?)
            ''', (user_id, target, action, details))
            conn.commit()
        except Exception as e:
            debug_log(f"Ошибка добавления лога: {e}")
        finally:
            conn.close()
    
    def add_ban_record(self, target_user_id, target_username, banned_by, groups_banned, total_groups, errors=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO bans (target_user_id, target_username, banned_by, groups_banned, total_groups, errors)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (target_user_id, target_username, banned_by, groups_banned, total_groups, errors))
            conn.commit()
            debug_log(f"Запись бана добавлена: target={target_username}, bans={groups_banned}")
        except Exception as e:
            debug_log(f"Ошибка добавления записи бана: {e}")
        finally:
            conn.close()
    
    def get_user_stats(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return None
            
            columns = [description[0] for description in cursor.description]
            stats = dict(zip(columns, result))
            
            # Количество запросов
            cursor.execute('SELECT COUNT(*) FROM logs WHERE user_id = ?', (user_id,))
            stats['requests_count'] = cursor.fetchone()[0]
            
            # Количество банов
            cursor.execute('SELECT COUNT(*) FROM bans WHERE banned_by = ?', (user_id,))
            stats['bans_count'] = cursor.fetchone()[0]
            
            return stats
        except Exception as e:
            debug_log(f"Ошибка получения статистики {user_id}: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id FROM users')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            debug_log(f"Ошибка получения всех пользователей: {e}")
            return []
        finally:
            conn.close()
    
    def get_bot_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE is_active = 1 AND expires_at > datetime("now")')
            active_subs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM bans')
            total_bans = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT target_user_id) FROM bans')
            unique_banned = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(groups_banned) FROM bans')
            total_groups_banned = cursor.fetchone()[0] or 0
            
            return {
                'total_users': total_users,
                'active_subs': active_subs,
                'total_bans': total_bans,
                'unique_banned': unique_banned,
                'total_groups_banned': total_groups_banned
            }
        except Exception as e:
            debug_log(f"Ошибка получения статистики бота: {e}")
            return {}
        finally:
            conn.close()

# Инициализация БД
db = Database()

# ========== ТЕЛЕТХОН КЛИЕНТ ==========
def create_telethon_client():
    session = StringSession(SESSION_STRING)
    return TelegramClient(session, API_ID, API_HASH)

async def ban_user_in_groups(username):
    debug_log(f"Начинаю бан @{username} в {len(GROUPS)} группах")
    
    banned_count = 0
    errors = []
    
    try:
        client = create_telethon_client()
        await client.start()
        
        # Получаем пользователя
        try:
            user = await client.get_entity(username)
        except Exception as e:
            debug_log(f"Пользователь @{username} не найден: {e}")
            await client.disconnect()
            return 0, len(GROUPS), ["Пользователь не найден"]
        
        # Права бана
        ban_rights = ChatBannedRights(
            until_date=None,
            view_messages=True,
            send_messages=True,
            send_media=True,
            send_stickers=True,
            send_gifs=True,
            send_games=True,
            send_inline=True,
            embed_links=True,
            send_polls=True,
            change_info=True,
            invite_users=True,
            pin_messages=True
        )
        
        # Бан в каждой группе
        for i, group_id in enumerate(GROUPS, 1):
            try:
                group = await client.get_entity(group_id)
                
                await client(EditBannedRequest(
                    channel=group,
                    participant=user,
                    banned_rights=ban_rights
                ))
                
                banned_count += 1
                debug_log(f"✅ Забанен в группе {i}/{len(GROUPS)}")
                
                # Задержка
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                error_msg = str(e)
                debug_log(f"❌ Ошибка в группе {group_id}: {error_msg[:50]}")
                errors.append(f"Группа {group_id}: {error_msg[:50]}")
        
        await client.disconnect()
        debug_log(f"🎯 Итог: забанен в {banned_count}/{len(GROUPS)} группах")
        return banned_count, len(GROUPS), errors
        
    except Exception as e:
        debug_log(f"💀 Критическая ошибка бана: {e}")
        return 0, len(GROUPS), [f"Критическая ошибка: {str(e)[:100]}"]

async def get_user_dc(username):
    try:
        client = create_telethon_client()
        await client.start()
        
        user = await client.get_entity(username)
        photo = user.photo
        
        dc_id = None
        if isinstance(photo, (UserProfilePhoto, ChatPhoto, Photo)):
            dc_id = photo.dc_id
        
        await client.disconnect()
        return dc_id
    except Exception as e:
        debug_log(f"Ошибка получения DC: {e}")
        return None

async def send_glban_command(username):
    try:
        client = create_telethon_client()
        await client.start()
        
        await client.send_message('me', f'.glban2 {username}')
        await client.disconnect()
        
        debug_log(f"Команда glban2 отправлена для @{username}")
        return True
    except Exception as e:
        debug_log(f"Ошибка отправки glban2: {e}")
        return False

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def is_admin(user_id):
    return user_id in ADMINS

def check_subscription(user_id):
    subscription = db.get_active_subscription(user_id)
    return subscription is not None

def check_channel_subscription(user_id):
    for channel in CHANNELS:
        try:
            time.sleep(TELEGRAM_API_DELAY)
            member = bot.get_chat_member(channel['id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            debug_log(f"Ошибка проверки подписки на канал: {e}")
            return False
    return True

def create_crypto_invoice(amount, plan_id):
    try:
        headers = {
            'Crypto-Pay-API-Token': CRYPTOPAY_TOKEN,
            'Content-Type': 'application/json'
        }
        
        data = {
            'amount': str(amount),
            'asset': 'USDT',
            'description': f'Подписка - {SUBSCRIPTION_PLANS[plan_id]["days"]} дней',
        }
        
        debug_log(f"Создаю счет на {amount} USDT")
        
        response = requests.post(
            f'{CRYPTOPAY_API_URL}createInvoice',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                invoice = result['result']
                return {
                    'invoice_id': invoice['invoice_id'],
                    'pay_url': invoice['pay_url'],
                    'amount': invoice['amount'],
                    'asset': invoice['asset']
                }
        return None
    except Exception as e:
        debug_log(f"Ошибка создания счета: {e}")
        return None

def check_invoice_status(invoice_id):
    try:
        headers = {'Crypto-Pay-API-Token': CRYPTOPAY_TOKEN}
        
        response = requests.get(
            f'{CRYPTOPAY_API_URL}getInvoices?invoice_ids={invoice_id}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok') and result['result']['items']:
                return result['result']['items'][0]['status']
        
        return None
    except Exception as e:
        debug_log(f"Ошибка проверки счета: {e}")
        return None

def send_log_to_channel(message_text):
    try:
        time.sleep(TELEGRAM_API_DELAY)
        bot.send_message(LOG_CHANNEL_ID, message_text, parse_mode='Markdown')
        debug_log("Лог отправлен в канал")
        return True
    except Exception as e:
        debug_log(f"Ошибка отправки лога: {e}")
        return False

def safe_send_message(chat_id, text, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(TELEGRAM_API_DELAY)
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка отправки (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                debug_log(f"Не удалось отправить сообщение: {e}")
                raise
    return None

def safe_edit_message(chat_id, message_id, text, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(TELEGRAM_API_DELAY)
            return bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка редактирования (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                debug_log(f"Не удалось отредактировать сообщение: {e}")
                raise
    return None

# ========== МЕНЮ ==========
def get_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Отправка", callback_data='send'),
        types.InlineKeyboardButton("Профиль", callback_data='profile')
    )
    markup.add(types.InlineKeyboardButton("Логи бота", url=LOGS_LINK))
    return markup

def get_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        markup.add(types.InlineKeyboardButton(plan['label'], callback_data=f'plan_{plan_id}'))
    return markup

def get_payment_menu(invoice_id, pay_url):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 Оплатить", url=pay_url),
        types.InlineKeyboardButton("✅ Проверить", callback_data=f'check_{invoice_id}')
    )
    return markup

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    db.update_activity(user.id)
    
    debug_log(f"Пользователь {user.id} запустил /start")
    
    if db.is_user_banned(user.id):
        safe_send_message(message.chat.id, "🚫 Вы забанены в боте!")
        return
    
    if not check_subscription(user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 Купить подписку", callback_data='buy_subscription'))
        
        safe_send_message(
            message.chat.id,
            "MonoFreez - Добро пожаловать!\n\nУ вас нет активной подписки.",
            reply_markup=markup
        )
        return
    
    if not check_channel_subscription(user.id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in CHANNELS:
            markup.add(types.InlineKeyboardButton(channel['name'], url=channel['url']))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data='check_channels'))
        
        safe_send_message(
            message.chat.id,
            "Для работы с ботом подпишитесь на наши каналы:",
            reply_markup=markup
        )
        return
    
    safe_send_message(
        message.chat.id,
        "MonoFreez - Добро пожаловать!\n\nВыберите действие:",
        reply_markup=get_main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == 'buy_subscription')
def handle_buy_subscription(call):
    bot.answer_callback_query(call.id)
    
    if db.is_user_banned(call.from_user.id):
        return
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "Выберите срок подписки:",
        reply_markup=get_subscription_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('plan_'))
def handle_plan_selection(call):
    bot.answer_callback_query(call.id)
    
    if db.is_user_banned(call.from_user.id):
        return
    
    plan_id = call.data.replace('plan_', '')
    if plan_id not in SUBSCRIPTION_PLANS:
        return
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    invoice = create_crypto_invoice(plan['price'], plan_id)
    
    if not invoice:
        safe_send_message(call.from_user.id, "❌ Ошибка создания счета. Попробуйте позже.")
        return
    
    db.add_invoice(invoice['invoice_id'], call.from_user.id, invoice['amount'], invoice['asset'], plan_id)
    
    invoice_text = f"""✅ Счет создан!

💳 Сумма: {plan['price']}$
📅 Срок: {plan['days']} дней

После оплаты нажмите "Проверить"."""
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        invoice_text,
        reply_markup=get_payment_menu(invoice['invoice_id'], invoice['pay_url'])
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def handle_check_payment(call):
    invoice_id = call.data.replace('check_', '')
    user_id = call.from_user.id
    
    bot.answer_callback_query(call.id, "Проверяем оплату...")
    
    if db.is_user_banned(user_id):
        return
    
    invoice = db.get_invoice(invoice_id)
    if not invoice or invoice['user_id'] != user_id:
        bot.answer_callback_query(call.id, "Счет не найден", show_alert=True)
        return
    
    status = check_invoice_status(invoice_id)
    
    if status == 'paid':
        db.update_invoice(invoice_id, 'paid')
        
        plan = SUBSCRIPTION_PLANS[invoice['plan_id']]
        db.add_subscription(user_id, invoice['plan_id'], plan['days'])
        
        expires_at = datetime.now() + timedelta(days=plan['days'])
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        success_msg = f"""✅ Оплата получена!

📅 Подписка активирована на {plan['days']} дней
📆 Действует до: {expires_str}

Напишите /start для продолжения"""
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            success_msg
        )
        
        log_msg = f"""💰 *Успешная оплата*

👤 Пользователь: @{call.from_user.username or call.from_user.id}
💳 Сумма: {plan['price']}$
📅 Срок: {plan['days']} дней"""
        send_log_to_channel(log_msg)
        
    elif status == 'active':
        bot.answer_callback_query(call.id, "⏳ Оплата еще не получена", show_alert=True)
    else:
        db.update_invoice(invoice_id, status or 'failed')
        bot.answer_callback_query(call.id, f"❌ Статус: {status or 'ошибка'}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'check_channels')
def handle_check_channels(call):
    bot.answer_callback_query(call.id)
    
    if check_channel_subscription(call.from_user.id):
        if check_subscription(call.from_user.id):
            safe_edit_message(
                call.message.chat.id,
                call.message.message_id,
                "✅ Отлично! Доступ разрешен.\n\nНапишите /start"
            )
        else:
            bot.answer_callback_query(call.id, "❌ Нет подписки!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "❌ Подпишитесь на все каналы!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'send')
def handle_send_request(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    if db.is_user_banned(user_id):
        return
    
    if not check_subscription(user_id):
        bot.answer_callback_query(call.id, "❌ Нет подписки!", show_alert=True)
        return
    
    if not check_channel_subscription(user_id):
        bot.answer_callback_query(call.id, "❌ Подпишитесь на каналы!", show_alert=True)
        return
    
    cooldown = db.get_cooldown(user_id)
    if cooldown > 0:
        minutes = int(cooldown // 60)
        seconds = int(cooldown % 60)
        bot.answer_callback_query(
            call.id,
            f"⏳ Подождите {minutes}:{seconds:02d}",
            show_alert=True
        )
        return
    
    db.set_cooldown(user_id)
    
    msg = safe_send_message(
        call.message.chat.id,
        "🔗 Отправьте username пользователя (например: @username или просто username):"
    )
    
    if msg:
        bot.register_next_step_handler(msg, process_username)

def process_username(message):
    user_id = message.from_user.id
    username_input = message.text.strip()
    
    if username_input.startswith('@'):
        username = username_input[1:]
    else:
        username = username_input
    
    username = username.strip()
    
    if not username or len(username) < 3 or ' ' in username:
        safe_send_message(message.chat.id, "❌ Некорректный username. Минимум 3 символа, без пробелов.")
        return
    
    debug_log(f"Обработка username @{username} от пользователя {user_id}")
    
    status_msg = safe_send_message(
        message.chat.id,
        f"✅ Запрос принят!\n\n👤 Цель: @{username}\n📊 Групп: {len(GROUPS)}\n⏳ Обработка..."
    )
    
    def process_background():
        try:
            db.add_log(user_id, 'request_started', username)
            
            initiator = f"@{message.from_user.username}" if message.from_user.username else f"ID:{user_id}"
            log_start = f"""📥 *Новый запрос*

👤 Инициатор: {initiator}
🎯 Цель: @{username}
🕐 Время: {datetime.now().strftime('%H:%M:%S')}"""
            send_log_to_channel(log_start)
            
            # Проверяем DC
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            dc_id = loop.run_until_complete(get_user_dc(username))
            allowed_dc = [1, 3, 5]
            
            if dc_id and dc_id not in allowed_dc:
                reject_log = f"""❌ *Запрос отклонен!*

🎯 Цель: @{username}
⚡ DC: {dc_id}
❌ Причина: Недопустимый датацентр"""
                
                send_log_to_channel(reject_log)
                db.add_log(user_id, 'rejected_dc', username, f"DC:{dc_id}")
                
                safe_send_message(
                    message.chat.id,
                    f"❌ Запрос отклонен!\n\nЦель: @{username}\nПричина: Недопустимый DC{dc_id}"
                )
                return
            
            # Отправляем glban2
            glban_success = loop.run_until_complete(send_glban_command(username))
            
            glban_log = f"""⚡ *Команда glban2*

🎯 Цель: @{username}
✅ Статус: {'Отправлена' if glban_success else 'Ошибка'}"""
            send_log_to_channel(glban_log)
            
            # Выполняем бан
            ban_start_log = f"""🔨 *Начало бана*

🎯 Цель: @{username}
📊 Групп: {len(GROUPS)}"""
            send_log_to_channel(ban_start_log)
            
            start_time = time.time()
            banned_count, total_groups, errors = loop.run_until_complete(ban_user_in_groups(username))
            duration = time.time() - start_time
            
            # Сохраняем результат
            target_user_id = 0
            try:
                client = create_telethon_client()
                loop.run_until_complete(client.start())
                user = loop.run_until_complete(client.get_entity(username))
                target_user_id = user.id
                loop.run_until_complete(client.disconnect())
            except:
                pass
            
            db.add_ban_record(target_user_id, username, user_id, banned_count, total_groups, errors)
            
            # Отправляем результат
            if banned_count > 0:
                result_msg = f"""✅ Бан выполнен!

👤 Цель: @{username}
🚫 Забанен в: {banned_count} группах
📊 Всего групп: {total_groups}
⏱️ Время: {duration:.1f} сек"""
                
                if errors:
                    result_msg += f"\n\n⚠️ Ошибок: {len(errors)}"
                
                result_log = f"""✅ *Бан выполнен*

🎯 Цель: @{username}
📊 Результат: {banned_count}/{total_groups}
⏱️ Время: {duration:.1f}сек"""
                
                db.add_log(user_id, 'ban_success', username, f"{banned_count}/{total_groups}")
            else:
                result_msg = f"""❌ Бан не выполнен

👤 Цель: @{username}
📊 Групп проверено: {total_groups}
⏱️ Время: {duration:.1f} сек
❌ Причина: {errors[0] if errors else 'Неизвестная ошибка'}"""
                
                result_log = f"""❌ *Бан не выполнен*

🎯 Цель: @{username}
📊 Результат: 0/{total_groups}
❌ Ошибка: {errors[0][:100] if errors else 'Неизвестно'}"""
                
                db.add_log(user_id, 'ban_failed', username, errors[0] if errors else '')
            
            send_log_to_channel(result_log)
            safe_send_message(message.chat.id, result_msg)
            
            # Показываем меню
            safe_send_message(
                message.chat.id,
                "Выберите действие:",
                reply_markup=get_main_menu()
            )
            
            loop.close()
            
        except Exception as e:
            debug_log(f"Ошибка обработки username: {e}")
            safe_send_message(
                message.chat.id,
                f"❌ Критическая ошибка!\n\n{str(e)[:100]}"
            )
    
    thread = Thread(target=process_background)
    thread.start()

@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def handle_profile(call):
    bot.answer_callback_query(call.id)
    
    user_id = call.from_user.id
    stats = db.get_user_stats(user_id)
    
    if not stats:
        safe_send_message(call.message.chat.id, "❌ Профиль не найден!")
        return
    
    profile_text = f"""📊 Ваш профиль

🆔 ID: {user_id}
👤 Имя: {stats.get('first_name', 'Не указано')}
🔗 Username: @{stats.get('username', 'Не указано')}
📅 Регистрация: {stats.get('registered_at', 'Неизвестно')}
📊 Запросов: {stats.get('requests_count', 0)}
🚫 Банов: {stats.get('bans_count', 0)}"""
    
    subscription = db.get_active_subscription(user_id)
    if subscription:
        expires_date = datetime.strptime(subscription['expires_at'], '%Y-%m-%d %H:%M:%S')
        expires_str = expires_date.strftime("%d.%m.%Y %H:%M")
        profile_text += f"\n\n💎 Подписка: ✅ Активна\n📆 Действует до: {expires_str}"
    else:
        profile_text += "\n\n💎 Подписка: ❌ Не активна"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏪ Назад", callback_data='back_to_menu'))
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        profile_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_menu')
def handle_back_to_menu(call):
    bot.answer_callback_query(call.id)
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "Выберите действие:",
        reply_markup=get_main_menu()
    )

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['sub'])
def handle_admin_subscription(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ Нет прав!")
        return
    
    try:
        args = message.text.split()
        if len(args) < 3:
            safe_send_message(message.chat.id, "Используйте: /sub ID_пользователя дни")
            return
        
        target_id = int(args[1])
        days = int(args[2])
        
        if days <= 0:
            safe_send_message(message.chat.id, "❌ Дни должны быть > 0")
            return
        
        if db.add_subscription(target_id, 'manual', days, user_id):
            expires_at = datetime.now() + timedelta(days=days)
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            
            admin_msg = f"""✅ Подписка выдана!

👤 ID: {target_id}
📅 Срок: {days} дней
📆 Действует до: {expires_str}"""
            
            safe_send_message(message.chat.id, admin_msg)
        else:
            safe_send_message(message.chat.id, "❌ Ошибка выдачи подписки")
            
    except ValueError:
        safe_send_message(message.chat.id, "❌ Неверный формат!")
    except Exception as e:
        debug_log(f"Ошибка /sub: {e}")
        safe_send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unsub'])
def handle_admin_unsubscribe(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ Нет прав!")
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            safe_send_message(message.chat.id, "Используйте: /unsub ID_пользователя")
            return
        
        target_id = int(args[1])
        
        if db.remove_subscription(target_id):
            safe_send_message(message.chat.id, f"✅ Подписка снята для {target_id}")
        else:
            safe_send_message(message.chat.id, "❌ Ошибка или подписка не найдена")
            
    except ValueError:
        safe_send_message(message.chat.id, "❌ Неверный ID!")
    except Exception as e:
        debug_log(f"Ошибка /unsub: {e}")
        safe_send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stats'])
def handle_admin_stats(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ Нет прав!")
        return
    
    stats = db.get_bot_stats()
    
    if not stats:
        safe_send_message(message.chat.id, "❌ Ошибка получения статистики")
        return
    
    stats_text = f"""📈 Статистика бота:

👥 Всего пользователей: {stats['total_users']}
💎 Активных подписок: {stats['active_subs']}
🚫 Всего банов: {stats['total_bans']}
👤 Уникальных забаненных: {stats['unique_banned']}
📊 Групп забанено: {stats['total_groups_banned']}

🕐 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
    
    safe_send_message(message.chat.id, stats_text)

@bot.message_handler(commands=['broadcast'])
def handle_admin_broadcast(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ Нет прав!")
        return
    
    text = message.text[10:].strip()
    
    if not text:
        safe_send_message(message.chat.id, "Используйте: /broadcast текст_рассылки")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Отправить", callback_data=f'broadcast_confirm_{user_id}'),
        types.InlineKeyboardButton("❌ Отмена", callback_data='broadcast_cancel')
    )
    
    safe_send_message(
        message.chat.id,
        f"📢 Подтвердите рассылку:\n\n{text[:500]}",
        reply_markup=markup
    )
    
    if not hasattr(bot, 'broadcasts'):
        bot.broadcasts = {}
    bot.broadcasts[user_id] = text

@bot.callback_query_handler(func=lambda call: call.data.startswith('broadcast_confirm_'))
def handle_broadcast_confirm(call):
    admin_id = int(call.data.split('_')[-1])
    
    if call.from_user.id != admin_id or not hasattr(bot, 'broadcasts') or admin_id not in bot.broadcasts:
        bot.answer_callback_query(call.id, "❌ Ошибка!", show_alert=True)
        return
    
    text = bot.broadcasts[admin_id]
    bot.answer_callback_query(call.id, "⏳ Начинаю рассылку...")
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "⏳ Рассылка начата..."
    )
    
    users = db.get_all_users()
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            safe_send_message(user_id, f"📢 Рассылка от администратора\n\n{text}")
            success += 1
            time.sleep(TELEGRAM_API_DELAY)
        except Exception as e:
            failed += 1
            debug_log(f"Ошибка рассылки пользователю {user_id}: {e}")
    
    result_text = f"""✅ Рассылка завершена!

📊 Статистика:
✅ Успешно: {success}
❌ Не удалось: {failed}
📈 Всего: {len(users)}"""
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        result_text
    )
    
    del bot.broadcasts[admin_id]

@bot.callback_query_handler(func=lambda call: call.data == 'broadcast_cancel')
def handle_broadcast_cancel(call):
    bot.answer_callback_query(call.id)
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "❌ Рассылка отменена"
    )

# ========== ЗАПУСК БОТА ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 Бот запускается...")
    print(f"👑 Админов: {len(ADMINS)}")
    print(f"📢 Каналов: {len(CHANNELS)}")
    print(f"📊 Групп: {len(GROUPS)}")
    print("=" * 50)
    
    while True:
        try:
            debug_log("Запускаю polling...")
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except KeyboardInterrupt:
            debug_log("Бот остановлен пользователем")
            break
        except Exception as e:
            debug_log(f"Ошибка polling: {e}")
            debug_log("Перезапуск через 10 секунд...")
            time.sleep(10)
