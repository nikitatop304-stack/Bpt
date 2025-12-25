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
import config

# ========== ЗАГРУЗКА КОНФИГА ==========
print("=" * 60)
print("🤖 MONOFREEZ BOT - ЗАПУСК")
print("=" * 60)

# Берем настройки напрямую из config
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
API_ID = config.API_ID
API_HASH = config.API_HASH
SESSION_STRING = config.SESSION_STRING
CRYPTOPAY_TOKEN = config.CRYPTOPAY_TOKEN
CRYPTOPAY_API_URL = config.CRYPTOPAY_API_URL
ADMINS = config.ADMINS
CHANNELS = config.CHANNELS
GROUPS = config.GROUPS
LOG_CHANNEL_ID = config.LOG_CHANNEL_ID
LOGS_LINK = config.LOGS_LINK

# Валидация токена
print("🔐 Проверка токена...")
if not TELEGRAM_BOT_TOKEN or ':' not in TELEGRAM_BOT_TOKEN:
    print("❌ ОШИБКА: Невалидный токен!")
    print("   Получи новый: @BotFather → /mybots → API Token")
    sys.exit(1)

bot_id = TELEGRAM_BOT_TOKEN.split(':')[0]
print(f"✅ Токен валидный! Бот ID: {bot_id}")
print(f"👑 Админы: {len(ADMINS)}")
print(f"📢 Каналов: {len(CHANNELS)}")
print(f"📊 Групп: {len(GROUPS)}")
print("=" * 60)

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

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
print("🚀 Инициализация бота...")
try:
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True, num_threads=10)
    print("✅ Бот инициализирован!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(1)

# ========== ЛОГИРОВАНИЕ ==========
def log_debug(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[DEBUG {timestamp}] {message}")
    sys.stdout.flush()

def log_error(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"❌ [ERROR {timestamp}] {message}")
    sys.stdout.flush()

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self, db_name='monofreez.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_id TEXT,
                expires_at TIMESTAMP,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица счетов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT UNIQUE,
                user_id INTEGER,
                amount REAL,
                asset TEXT,
                plan_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP
            )
        ''')
        
        # Таблица логов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_username TEXT,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица кулдаунов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица банов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_user_id INTEGER,
                target_username TEXT,
                banned_by INTEGER,
                groups_banned INTEGER,
                total_groups INTEGER,
                errors TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        log_debug(f"База данных {self.db_name} инициализирована")
    
    def add_user(self, user_id, username, first_name, last_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
            log_debug(f"Пользователь {user_id} добавлен")
        except Exception as e:
            log_error(f"Ошибка добавления пользователя: {e}")
        finally:
            conn.close()
    
    def update_activity(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            log_error(f"Ошибка обновления активности: {e}")
        finally:
            conn.close()
    
    def add_subscription(self, user_id, plan_id, days):
        expires_at = datetime.now() + timedelta(days=days)
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Деактивируем старые подписки
            cursor.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ?', (user_id,))
            
            # Добавляем новую
            cursor.execute('''
                INSERT INTO subscriptions (user_id, plan_id, expires_at)
                VALUES (?, ?, ?)
            ''', (user_id, plan_id, expires_at))
            
            conn.commit()
            log_debug(f"Подписка добавлена: user={user_id}, plan={plan_id}, days={days}")
            return True
        except Exception as e:
            log_error(f"Ошибка добавления подписки: {e}")
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
            
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            log_error(f"Ошибка получения подписки: {e}")
            return None
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
            log_debug(f"Счет {invoice_id} добавлен")
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            log_error(f"Ошибка добавления счета: {e}")
            return False
        finally:
            conn.close()
    
    def update_invoice(self, invoice_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if status == 'paid':
                cursor.execute('''
                    UPDATE invoices SET status = ?, paid_at = datetime('now') 
                    WHERE invoice_id = ?
                ''', (status, invoice_id))
            else:
                cursor.execute('UPDATE invoices SET status = ? WHERE invoice_id = ?', (status, invoice_id))
            
            conn.commit()
            log_debug(f"Счет {invoice_id} обновлен: {status}")
            return True
        except Exception as e:
            log_error(f"Ошибка обновления счета: {e}")
            return False
        finally:
            conn.close()
    
    def get_invoice(self, invoice_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM invoices WHERE invoice_id = ?', (invoice_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            log_error(f"Ошибка получения счета: {e}")
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
            log_error(f"Ошибка установки кулдауна: {e}")
            return False
        finally:
            conn.close()
    
    def get_cooldown(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT last_used FROM cooldowns WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                last_used = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                time_passed = (datetime.now() - last_used).total_seconds()
                if time_passed < REQUEST_COOLDOWN:
                    return REQUEST_COOLDOWN - time_passed
            return 0
        except Exception as e:
            log_error(f"Ошибка получения кулдауна: {e}")
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
            log_error(f"Ошибка добавления лога: {e}")
        finally:
            conn.close()
    
    def add_ban_record(self, target_user_id, target_username, banned_by, groups_banned, total_groups, errors=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO bans (target_user_id, target_username, banned_by, groups_banned, total_groups, errors)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (target_user_id, target_username, banned_by, groups_banned, total_groups, str(errors) if errors else None))
            conn.commit()
            log_debug(f"Запись бана добавлена: {target_username}")
        except Exception as e:
            log_error(f"Ошибка добавления записи бана: {e}")
        finally:
            conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id FROM users')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            log_error(f"Ошибка получения пользователей: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_stats(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if user:
                columns = [description[0] for description in cursor.description]
                stats = dict(zip(columns, user))
                
                cursor.execute('SELECT COUNT(*) FROM logs WHERE user_id = ?', (user_id,))
                stats['logs_count'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM bans WHERE banned_by = ?', (user_id,))
                stats['bans_count'] = cursor.fetchone()[0]
                
                return stats
            return None
        except Exception as e:
            log_error(f"Ошибка получения статистики: {e}")
            return None
        finally:
            conn.close()

# Инициализация БД
db = Database()

# ========== СЕРВИСНЫЕ ФУНКЦИИ ==========
def create_telethon_client():
    """Создание клиента Telethon"""
    if SESSION_STRING:
        session = StringSession(SESSION_STRING)
        log_debug("Использую строковую сессию")
    else:
        raise ValueError("Нет строки сессии")
    
    return TelegramClient(session, API_ID, API_HASH)

async def ban_user_in_groups(username):
    """Бан пользователя в группах"""
    log_debug(f"Начинаю бан @{username} в {len(GROUPS)} группах")
    
    banned_count = 0
    errors = []
    
    try:
        client = create_telethon_client()
        await client.start()
        
        # Получаем пользователя
        try:
            user = await client.get_entity(username)
            log_debug(f"Пользователь найден: @{username} (ID: {user.id})")
        except Exception as e:
            log_error(f"Пользователь @{username} не найден: {e}")
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
                group_name = group.title if hasattr(group, 'title') else f"ID: {group_id}"
                
                log_debug(f"Бан в группе {i}/{len(GROUPS)}: {group_name}")
                
                await client(EditBannedRequest(
                    channel=group,
                    participant=user,
                    banned_rights=ban_rights
                ))
                
                banned_count += 1
                log_debug(f"✅ Забанен в {group_name}")
                
                # Задержка 1-3 секунды
                await asyncio.sleep(random.uniform(1, 3))
                
            except Exception as e:
                error_msg = str(e)
                log_error(f"Ошибка в группе {group_id}: {error_msg[:100]}")
                
                if "CHAT_ADMIN_REQUIRED" in error_msg:
                    errors.append(f"Нет прав админа в группе {group_id}")
                elif "USER_NOT_PARTICIPANT" in error_msg:
                    errors.append(f"Пользователь не участник группы {group_id}")
                elif "CHANNEL_PRIVATE" in error_msg:
                    errors.append(f"Нет доступа к группе {group_id}")
                else:
                    errors.append(f"Группа {group_id}: {error_msg[:50]}")
        
        await client.disconnect()
        log_debug(f"Бан завершен: {banned_count}/{len(GROUPS)} групп")
        return banned_count, len(GROUPS), errors
        
    except Exception as e:
        log_error(f"Критическая ошибка бана: {e}")
        return 0, len(GROUPS), [f"Критическая ошибка: {str(e)[:100]}"]

async def get_user_dc(username):
    """Получение датацентра пользователя"""
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
        log_error(f"Ошибка получения DC для @{username}: {e}")
        return None

async def send_glban_command(username):
    """Отправка glban команды"""
    try:
        client = create_telethon_client()
        await client.start()
        
        await client.send_message('me', f'.glban2 {username}')
        await client.disconnect()
        
        log_debug(f"Команда glban2 отправлена для @{username}")
        return True
    except Exception as e:
        log_error(f"Ошибка отправки glban2: {e}")
        return False

def is_admin(user_id):
    """Проверка админских прав"""
    return user_id in ADMINS

def check_subscription(user_id):
    """Проверка активной подписки"""
    subscription = db.get_active_subscription(user_id)
    return subscription is not None

def check_channel_subscription(user_id):
    """Проверка подписки на каналы"""
    for channel in CHANNELS:
        try:
            time.sleep(TELEGRAM_API_DELAY)
            member = bot.get_chat_member(channel['id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            log_error(f"Ошибка проверки подписки на канал {channel['id']}: {e}")
            return False
    return True

def create_crypto_invoice(amount, plan_id):
    """Создание счета в Crypto Pay"""
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
        
        log_debug(f"Создаю счет на {amount} USDT для плана {plan_id}")
        
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
                log_debug(f"Счет создан: {invoice['invoice_id']}")
                return {
                    'invoice_id': invoice['invoice_id'],
                    'pay_url': invoice['pay_url'],
                    'amount': invoice['amount'],
                    'asset': invoice['asset']
                }
            else:
                log_error(f"CryptoPay ошибка: {result.get('error')}")
        else:
            log_error(f"HTTP ошибка: {response.status_code} - {response.text}")
        
        return None
    except Exception as e:
        log_error(f"Ошибка создания счета: {e}")
        return None

def check_invoice_status(invoice_id):
    """Проверка статуса счета"""
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
        log_error(f"Ошибка проверки счета: {e}")
        return None

def send_log(message_text):
    """Отправка лога в канал"""
    try:
        time.sleep(TELEGRAM_API_DELAY)
        bot.send_message(LOG_CHANNEL_ID, message_text, parse_mode='Markdown')
        log_debug("Лог отправлен в канал")
        return True
    except Exception as e:
        log_error(f"Ошибка отправки лога: {e}")
        return False

def safe_send_message(chat_id, text, **kwargs):
    """Безопасная отправка сообщения"""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(TELEGRAM_API_DELAY)
            return bot.send_message(chat_id, text, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                log_debug(f"Ошибка отправки (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                log_error(f"Не удалось отправить сообщение: {e}")
                raise
    return None

def safe_edit_message(chat_id, message_id, text, **kwargs):
    """Безопасное редактирование сообщения"""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(TELEGRAM_API_DELAY)
            return bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                log_debug(f"Ошибка редактирования (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                log_error(f"Не удалось отредактировать сообщение: {e}")
                raise
    return None

# ========== МЕНЮ ==========
def get_main_menu():
    """Главное меню"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Отправка", callback_data='send'),
        types.InlineKeyboardButton("Профиль", callback_data='profile')
    )
    markup.add(types.InlineKeyboardButton("Логи бота", url=LOGS_LINK))
    return markup

def get_subscription_menu():
    """Меню подписок"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        markup.add(types.InlineKeyboardButton(plan['label'], callback_data=f'plan_{plan_id}'))
    return markup

def get_payment_menu(invoice_id, pay_url):
    """Меню оплаты"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💳 Оплатить", url=pay_url),
        types.InlineKeyboardButton("✅ Проверить", callback_data=f'check_{invoice_id}')
    )
    return markup

# ========== КОМАНДА /start ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработка /start"""
    user = message.from_user
    
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    db.update_activity(user.id)
    
    log_debug(f"Пользователь {user.id} запустил /start")
    
    # Проверка подписки
    if not check_subscription(user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 Купить подписку", callback_data='buy'))
        
        safe_send_message(
            message.chat.id,
            "👋 Добро пожаловать!\n\nУ вас нет активной подписки.",
            reply_markup=markup
        )
        return
    
    # Проверка подписки на каналы
    if not check_channel_subscription(user.id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for channel in CHANNELS:
            markup.add(types.InlineKeyboardButton(channel['name'], url=channel['url']))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data='check_channels'))
        
        safe_send_message(
            message.chat.id,
            "📢 Для работы подпишитесь на наши каналы:",
            reply_markup=markup
        )
        return
    
    safe_send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\nВыберите действие:",
        reply_markup=get_main_menu()
    )

# ========== ПОКУПКА ПОДПИСКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'buy')
def handle_buy(call):
    """Покупка подписки"""
    bot.answer_callback_query(call.id)
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "💎 Выберите срок подписки:",
        reply_markup=get_subscription_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('plan_'))
def handle_plan(call):
    """Выбор плана"""
    bot.answer_callback_query(call.id)
    
    plan_id = call.data.replace('plan_', '')
    if plan_id not in SUBSCRIPTION_PLANS:
        return
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    # Создаем счет
    invoice = create_crypto_invoice(plan['price'], plan_id)
    
    if not invoice:
        safe_send_message(call.from_user.id, "❌ Ошибка создания счета. Попробуйте позже.")
        return
    
    # Сохраняем в БД
    db.add_invoice(invoice['invoice_id'], call.from_user.id, invoice['amount'], invoice['asset'], plan_id)
    
    invoice_text = f"""✅ Счет создан!

💳 Сумма: {plan['price']}$
📅 Срок: {plan['days']} дней
🆔 ID: {invoice['invoice_id']}

После оплаты нажмите "Проверить"."""
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        invoice_text,
        reply_markup=get_payment_menu(invoice['invoice_id'], invoice['pay_url'])
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def handle_check(call):
    """Проверка оплаты"""
    invoice_id = call.data.replace('check_', '')
    user_id = call.from_user.id
    
    bot.answer_callback_query(call.id, "Проверяем оплату...")
    
    # Проверяем счет
    invoice = db.get_invoice(invoice_id)
    if not invoice or invoice['user_id'] != user_id:
        bot.answer_callback_query(call.id, "Счет не найден", show_alert=True)
        return
    
    # Проверяем статус
    status = check_invoice_status(invoice_id)
    
    if status == 'paid':
        # Обновляем статус
        db.update_invoice(invoice_id, 'paid')
        
        # Активируем подписку
        plan = SUBSCRIPTION_PLANS[invoice['plan_id']]
        db.add_subscription(user_id, invoice['plan_id'], plan['days'])
        
        expires_at = datetime.now() + timedelta(days=plan['days'])
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        success_msg = f"""✅ Оплата получена!

📅 Подписка активирована на {plan['days']} дней
📆 Действует до: {expires_str}

Напишите /start"""
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            success_msg
        )
        
        # Логируем
        log_msg = f"""💰 *Успешная оплата*

👤 Пользователь: @{call.from_user.username or call.from_user.id}
💳 Сумма: {plan['price']}$
📅 Срок: {plan['days']} дней"""
        send_log(log_msg)
        
    elif status == 'active':
        bot.answer_callback_query(call.id, "⏳ Оплата еще не получена", show_alert=True)
    else:
        db.update_invoice(invoice_id, status or 'failed')
        bot.answer_callback_query(call.id, f"❌ Статус: {status or 'ошибка'}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'check_channels')
def handle_check_channels(call):
    """Проверка подписки на каналы"""
    bot.answer_callback_query(call.id)
    
    if check_channel_subscription(call.from_user.id):
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "✅ Отлично! Доступ разрешен.\n\nНапишите /start"
        )
    else:
        bot.answer_callback_query(call.id, "❌ Подпишитесь на все каналы!", show_alert=True)

# ========== ОТПРАВКА (БАН) ==========
@bot.callback_query_handler(func=lambda call: call.data == 'send')
def handle_send(call):
    """Запрос на бан"""
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    if not check_subscription(user_id):
        bot.answer_callback_query(call.id, "❌ Нет подписки!", show_alert=True)
        return
    
    if not check_channel_subscription(user_id):
        bot.answer_callback_query(call.id, "❌ Подпишитесь на каналы!", show_alert=True)
        return
    
    # Проверка кулдауна
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
    
    # Устанавливаем кулдаун
    db.set_cooldown(user_id)
    
    msg = safe_send_message(
        call.message.chat.id,
        "🔗 Отправьте @username пользователя (например: @username или просто username):"
    )
    
    if msg:
        bot.register_next_step_handler(msg, process_username)
    else:
        safe_send_message(call.message.chat.id, "❌ Ошибка. Попробуйте /start")

def process_username(message):
    """Обработка username"""
    user_id = message.from_user.id
    username_input = message.text.strip()
    
    # Очистка username
    if username_input.startswith('@'):
        username = username_input[1:]
    else:
        username = username_input
    
    username = username.strip()
    
    # Валидация
    if not username or len(username) < 3 or ' ' in username:
        safe_send_message(message.chat.id, "❌ Некорректный username. Минимум 3 символа, без пробелов.")
        return
    
    log_debug(f"Обработка username @{username} от {user_id}")
    
    # Статус
    status_msg = safe_send_message(
        message.chat.id,
        f"✅ Запрос принят!\n\n👤 Цель: @{username}\n📊 Групп: {len(GROUPS)}\n⏳ Обработка..."
    )
    
    # Запускаем в фоне
    def process_background():
        try:
            # 1. Логируем начало
            db.add_log(user_id, 'request_started', username)
            
            initiator = f"@{message.from_user.username}" if message.from_user.username else f"ID:{user_id}"
            log_start = f"""📥 *Новый запрос*

👤 Инициатор: {initiator}
🎯 Цель: @{username}
🕐 Время: {datetime.now().strftime('%H:%M:%S')}"""
            send_log(log_start)
            
            # 2. Проверяем DC
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            dc_id = loop.run_until_complete(get_user_dc(username))
            allowed_dc = [1, 3, 5]
            
            if dc_id and dc_id not in allowed_dc:
                reject_log = f"""❌ *Запрос отклонен!*

🎯 Цель: @{username}
⚡ DC: {dc_id}
❌ Причина: Недопустимый датацентр"""
                
                send_log(reject_log)
                db.add_log(user_id, 'rejected_dc', username, f"DC:{dc_id}")
                
                safe_send_message(
                    message.chat.id,
                    f"❌ Запрос отклонен!\n\nЦель: @{username}\nПричина: DC{dc_id}"
                )
                return
            
            # 3. Отправляем glban2
            glban_success = loop.run_until_complete(send_glban_command(username))
            
            glban_log = f"""⚡ *Команда glban2*

🎯 Цель: @{username}
✅ Статус: {'Отправлена' if glban_success else 'Ошибка'}"""
            send_log(glban_log)
            
            # 4. Выполняем бан
            ban_start_log = f"""🔨 *Начало бана*

🎯 Цель: @{username}
📊 Групп: {len(GROUPS)}"""
            send_log(ban_start_log)
            
            start_time = time.time()
            banned_count, total_groups, errors = loop.run_until_complete(ban_user_in_groups(username))
            duration = time.time() - start_time
            
            # 5. Сохраняем результат
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
            
            # 6. Отправляем результат
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
            
            send_log(result_log)
            safe_send_message(message.chat.id, result_msg)
            
            # 7. Показываем меню
            safe_send_message(
                message.chat.id,
                "Выберите действие:",
                reply_markup=get_main_menu()
            )
            
            loop.close()
            
        except Exception as e:
            log_error(f"Ошибка обработки: {e}")
            traceback.print_exc()
            safe_send_message(
                message.chat.id,
                f"❌ Критическая ошибка!\n\n{str(e)[:100]}"
            )
    
    # Запускаем поток
    thread = Thread(target=process_background)
    thread.start()

# ========== ПРОФИЛЬ ==========
@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def handle_profile(call):
    """Профиль пользователя"""
    bot.answer_callback_query(call.id)
    
    user_id = call.from_user.id
    stats = db.get_user_stats(user_id)
    subscription = db.get_active_subscription(user_id)
    
    if not stats:
        profile_text = "❌ Профиль не найден"
    else:
        profile_text = f"""📊 Ваш профиль

🆔 ID: {user_id}
👤 Имя: {stats.get('first_name', 'Не указано')}
🔗 Username: @{stats.get('username', 'Не указано')}
📅 Регистрация: {stats.get('registered_at', 'Неизвестно')}
📊 Запросов: {stats.get('logs_count', 0)}
🚫 Банов: {stats.get('bans_count', 0)}"""
        
        if subscription:
            expires_date = datetime.strptime(subscription['expires_at'], '%Y-%m-%d %H:%M:%S')
            expires_str = expires_date.strftime("%d.%m.%Y %H:%M")
            profile_text += f"\n\n💎 Подписка: ✅ Активна\n📆 Действует до: {expires_str}"
        else:
            profile_text += "\n\n💎 Подписка: ❌ Не активна"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⏪ Назад", callback_data='back'))
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        profile_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'back')
def handle_back(call):
    """Назад в меню"""
    bot.answer_callback_query(call.id)
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        "Выберите действие:",
        reply_markup=get_main_menu()
    )

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        safe_send_message(message.chat.id, "❌ Нет прав!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Выдать подписку", callback_data='admin_give'),
        types.InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')
    )
    markup.add(
        types.InlineKeyboardButton("👤 Инфо пользователя", callback_data='admin_userinfo'),
        types.InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast')
    )
    
    safe_send_message(
        message.chat.id,
        "👑 Админ-панель:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'admin_give')
def handle_admin_give(call):
    """Выдача подписки"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет прав!", show_alert=True)
        return
    
    msg = bot.send_message(call.message.chat.id, "Введите ID пользователя и количество дней (через пробел):\nПример: 123456789 30")
    bot.register_next_step_handler(msg, process_admin_give)

def process_admin_give(message):
    """Обработка выдачи подписки"""
    try:
        parts = message.text.split()
        if len(parts) != 2:
            safe_send_message(message.chat.id, "❌ Неверный формат!")
            return
        
        user_id = int(parts[0])
        days = int(parts[1])
        
        if days <= 0:
            safe_send_message(message.chat.id, "❌ Дни должны быть > 0")
            return
        
        # Добавляем подписку
        plan_id = f"{days}_days"
        if db.add_subscription(user_id, plan_id, days):
            expires_at = datetime.now() + timedelta(days=days)
            expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
            
            admin_msg = f"""✅ Подписка выдана!

👤 ID: {user_id}
📅 Срок: {days} дней
📆 Действует до: {expires_str}"""
            
            safe_send_message(message.chat.id, admin_msg)
            
            # Уведомляем пользователя
            try:
                user_msg = f"""✅ Вам выдана подписка на {days} дней!

Действует до: {expires_str}"""
                safe_send_message(user_id, user_msg)
            except:
                pass
        else:
            safe_send_message(message.chat.id, "❌ Ошибка выдачи подписки")
            
    except ValueError:
        safe_send_message(message.chat.id, "❌ Неверный формат!")
    except Exception as e:
        log_error(f"Ошибка выдачи подписки: {e}")
        safe_send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_stats')
def handle_admin_stats(call):
    """Статистика бота"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Нет прав!", show_alert=True)
        return
    
    users = db.get_all_users()
    
    # Считаем активные подписки
    active_subs = 0
    for user_id in users:
        if db.get_active_subscription(user_id):
            active_subs += 1
    
    stats_text = f"""📈 Статистика бота:

👥 Всего пользователей: {len(users)}
💎 Активных подписок: {active_subs}
📊 Групп для бана: {len(GROUPS)}

🕐 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
    
    safe_edit_message(
        call.message.chat.id,
        call.message.message_id,
        stats_text
    )

# ========== ЗАПУСК ==========
print("🚀 Бот запущен и готов к работе!")
print("📌 Основные команды:")
print("   /start - Главное меню")
print("   /admin - Админ-панель (для админов)")
print("=" * 60)

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=30)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        break
    except Exception as e:
        log_error(f"Ошибка polling: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        time.sleep(10)
