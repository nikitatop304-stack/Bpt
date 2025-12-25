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
from config import *

# Инициализация конфигурации
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_ID = int(os.getenv('API_ID', 0))  # Конвертируем в число
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING')
CRYPTOPAY_TOKEN = os.getenv('CRYPTOPAY_TOKEN')
CRYPTOPAY_API_URL = os.getenv('CRYPTOPAY_API_URL', 'https://pay.crypt.bot/api/')

# Админы
ADMINS_STR = os.getenv('ADMINS', '')
ADMINS = list(map(int, ADMINS_STR.split(','))) if ADMINS_STR else []
CHANNELS = config.CHANNELS
LOG_CHANNEL_ID = config.LOG_CHANNEL_ID
LOGS_LINK = config.LOGS_LINK

# Тарифы подписок
SUBSCRIPTION_PLANS = {
    '1_day': {'days': 1, 'price': 2.0, 'label': '1 день - 2$'},
    '7_days': {'days': 7, 'price': 4.5, 'label': '7 дней - 4.5$'},
    '30_days': {'days': 30, 'price': 8.0, 'label': '30 дней - 8$'},
    '90_days': {'days': 90, 'price': 13.0, 'label': '90 дней - 13$'}
}

# Настройки
TELEGRAM_API_DELAY = 0.1
MAX_RETRIES = 3

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=True, num_threads=10)

# ============= ДЕБАГ ЛОГИ =============
def debug_log(message):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[DEBUG {timestamp}] {message}")
    sys.stdout.flush()

# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============
def create_telethon_client():
    if SESSION_STRING:
        debug_log("Использую строку сессии")
        session = StringSession(SESSION_STRING)
    elif SESSION_FILE:
        debug_log(f"Использую файл сессии: {SESSION_FILE}")
        session = SESSION_FILE
    else:
        raise ValueError("Не указан тип сессии")
    
    return TelegramClient(session, int(API_ID), API_HASH)

async def ban_user_in_all_groups_async(username):
    debug_log(f"Начинаю бан @{username} в {len(GROUPS)} группах")
    
    banned_in = 0
    total_groups = len(GROUPS)
    errors = []
    
    try:
        client = create_telethon_client()
        await client.start()
        debug_log("Telethon клиент запущен")
        
        try:
            user_entity = await client.get_entity(username)
            debug_log(f"Пользователь найден: @{username} (ID: {user_entity.id})")
        except Exception as e:
            debug_log(f"❌ Пользователь @{username} не найден: {e}")
            await client.disconnect()
            return 0, total_groups, [f"Пользователь не найден: {e}"]
        
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
        
        for index, group_id in enumerate(GROUPS, 1):
            try:
                group = await client.get_entity(group_id)
                group_name = group.title if hasattr(group, 'title') else f"ID: {group_id}"
                
                debug_log(f"Группа {index}/{total_groups}: {group_name}")
                
                await client(EditBannedRequest(
                    channel=group,
                    participant=user_entity,
                    banned_rights=ban_rights
                ))
                
                debug_log(f"✅ Забанен в группе: {group_name}")
                banned_in += 1
                
                # Обновляем статистику
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO group_stats (group_id, group_name, bans_sent, last_activity)
                        VALUES (?, ?, COALESCE((SELECT bans_sent FROM group_stats WHERE group_id = ?), 0) + 1, CURRENT_TIMESTAMP)
                    ''', (group_id, group_name, group_id))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    debug_log(f"Ошибка обновления статистики группы: {e}")
                
                # Задержка
                delay = random.uniform(1, 3)
                debug_log(f"Задержка {delay:.1f} сек")
                await asyncio.sleep(delay)
                
            except Exception as e:
                error_msg = str(e)
                debug_log(f"❌ Ошибка в группе {group_id}: {error_msg[:50]}")
                
                if "CHAT_ADMIN_REQUIRED" in error_msg:
                    errors.append(f"Нет прав админа в группе {group_id}")
                elif "USER_NOT_PARTICIPANT" in error_msg:
                    errors.append(f"Пользователь не участник группы {group_id}")
                elif "CHANNEL_PRIVATE" in error_msg:
                    errors.append(f"Нет доступа к группе {group_id}")
                else:
                    errors.append(f"Ошибка в группе {group_id}: {error_msg[:50]}")
        
        await client.disconnect()
        debug_log(f"🎯 Итог: забанен в {banned_in}/{total_groups} группах")
        return banned_in, total_groups, errors
        
    except Exception as e:
        debug_log(f"💀 Критическая ошибка бана: {e}")
        traceback.print_exc()
        return 0, total_groups, [f"Критическая ошибка: {e}"]

def ban_user_in_all_groups(username):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(ban_user_in_all_groups_async(username))
        return result
    finally:
        loop.close()

# ============= БАЗА ДАННЫХ =============
class Database:
    def __init__(self, db_name='bot_database.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем существующие таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        debug_log(f"Существующие таблицы: {existing_tables}")
        
        # Создаем таблицы если их нет
        tables_to_create = [
            ('users', '''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('subscriptions', '''
                CREATE TABLE subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    plan_id TEXT,
                    expires_at TIMESTAMP,
                    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    admin_id INTEGER,
                    days INTEGER,
                    is_active INTEGER DEFAULT 1
                )
            '''),
            ('invoices', '''
                CREATE TABLE invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    user_id INTEGER,
                    amount REAL,
                    asset TEXT,
                    plan_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP
                )
            '''),
            ('logs', '''
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    target_username TEXT,
                    action TEXT,
                    details TEXT DEFAULT '',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('cooldowns', '''
                CREATE TABLE cooldowns (
                    user_id INTEGER PRIMARY KEY,
                    last_used TIMESTAMP
                )
            '''),
            ('bans', '''
                CREATE TABLE bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_user_id INTEGER,
                    target_username TEXT,
                    banned_by INTEGER,
                    groups_banned INTEGER,
                    total_groups INTEGER,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    errors TEXT
                )
            '''),
            ('group_stats', '''
                CREATE TABLE group_stats (
                    group_id INTEGER PRIMARY KEY,
                    group_name TEXT,
                    bans_sent INTEGER DEFAULT 0,
                    last_activity TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
        ]
        
        for table_name, create_sql in tables_to_create:
            if table_name not in existing_tables:
                debug_log(f"Создаю таблицу: {table_name}")
                try:
                    cursor.execute(create_sql)
                    debug_log(f"Таблица {table_name} создана успешно")
                except Exception as e:
                    debug_log(f"Ошибка при создании таблицы {table_name}: {e}")
        
        conn.commit()
        conn.close()
        debug_log(f"База данных {self.db_name} инициализирована")
    
    def add_user(self, user_id, username, first_name, last_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_activity)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
            conn.commit()
            debug_log(f"Пользователь {user_id} добавлен в БД")
        except Exception as e:
            debug_log(f"Ошибка при добавлении пользователя {user_id}: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def update_user_activity(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            debug_log(f"Ошибка обновления активности {user_id}: {e}")
        finally:
            conn.close()
    
    def add_subscription(self, user_id, plan_id, expires_at, admin_id=None, days=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Деактивируем старую подписку
            cursor.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1', (user_id,))
            
            # Добавляем новую
            cursor.execute('''
            INSERT INTO subscriptions (user_id, plan_id, expires_at, admin_id, days, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            ''', (user_id, plan_id, expires_at, admin_id, days))
            
            conn.commit()
            debug_log(f"Добавлена подписка для user_id={user_id}, дней={days}")
        except Exception as e:
            debug_log(f"Ошибка добавления подписки: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_active_subscription(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT * FROM subscriptions 
            WHERE user_id = ? AND is_active = 1 AND expires_at > CURRENT_TIMESTAMP
            ''', (user_id,))
            subscription = cursor.fetchone()
            
            if subscription:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, subscription))
            return None
        except Exception as e:
            debug_log(f"Ошибка получения подписки: {e}")
            return None
        finally:
            conn.close()
    
    def remove_subscription(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1', (user_id,))
            conn.commit()
            debug_log(f"Удалена подписка для user_id={user_id}")
        except Exception as e:
            debug_log(f"Ошибка удаления подписки: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def add_invoice(self, invoice_id, user_id, amount, asset, plan_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO invoices (invoice_id, user_id, amount, asset, plan_id, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (invoice_id, user_id, amount, asset, plan_id))
            conn.commit()
            debug_log(f"Добавлен счет {invoice_id} для user_id={user_id}")
        except Exception as e:
            debug_log(f"Ошибка добавления счета: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def update_invoice_status(self, invoice_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if status == 'paid':
                cursor.execute('''
                UPDATE invoices SET status = ?, paid_at = CURRENT_TIMESTAMP 
                WHERE invoice_id = ?
                ''', (status, invoice_id))
            else:
                cursor.execute('''
                UPDATE invoices SET status = ? WHERE invoice_id = ?
                ''', (status, invoice_id))
            conn.commit()
            debug_log(f"Обновлен счет {invoice_id} на статус {status}")
        except Exception as e:
            debug_log(f"Ошибка обновления счета: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_invoice(self, invoice_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM invoices WHERE invoice_id = ?', (invoice_id,))
            invoice = cursor.fetchone()
            
            if invoice:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, invoice))
            return None
        except Exception as e:
            debug_log(f"Ошибка получения счета: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_invoices(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM invoices WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
            invoices = cursor.fetchall()
            
            columns = [description[0] for description in cursor.description]
            result = [dict(zip(columns, invoice)) for invoice in invoices]
            
            return result
        except Exception as e:
            debug_log(f"Ошибка получения счетов пользователя: {e}")
            return []
        finally:
            conn.close()
    
    def add_log(self, user_id, target_username, action, details=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO logs (user_id, target_username, action, details)
            VALUES (?, ?, ?, ?)
            ''', (user_id, target_username, action, details))
            conn.commit()
        except Exception as e:
            debug_log(f"Ошибка добавления лога: {e}")
        finally:
            conn.close()
    
    def set_cooldown(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO cooldowns (user_id, last_used)
            VALUES (?, CURRENT_TIMESTAMP)
            ''', (user_id,))
            conn.commit()
        except Exception as e:
            debug_log(f"Ошибка установки кулдауна: {e}")
        finally:
            conn.close()
    
    def get_cooldown(self, user_id, cooldown_seconds=300):
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
            debug_log(f"Ошибка получения кулдауна: {e}")
            return 0
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
        except Exception as e:
            debug_log(f"Ошибка добавления записи бана: {e}")
        finally:
            conn.close()
    
    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT user_id FROM users')
            users = cursor.fetchall()
            return [user[0] for user in users]
        except Exception as e:
            debug_log(f"Ошибка получения пользователей: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_stats(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user_info = cursor.fetchone()
            
            if user_info:
                columns = [description[0] for description in cursor.description]
                user_dict = dict(zip(columns, user_info))
                
                cursor.execute('SELECT COUNT(*) FROM logs WHERE user_id = ?', (user_id,))
                user_dict['log_count'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM bans WHERE banned_by = ?', (user_id,))
                user_dict['bans_count'] = cursor.fetchone()[0]
                
                return user_dict
            return None
        except Exception as e:
            debug_log(f"Ошибка получения статистики пользователя: {e}")
            return None
        finally:
            conn.close()
    
    def get_ban_stats(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM bans')
            total_bans = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT target_user_id) FROM bans')
            unique_users = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(groups_banned) FROM bans')
            total_groups_banned = cursor.fetchone()[0] or 0
            
            return total_bans, unique_users, total_groups_banned
        except Exception as e:
            debug_log(f"Ошибка получения статистики банов: {e}")
            return 0, 0, 0
        finally:
            conn.close()

# Инициализация базы данных
db = Database()
subscribed_users = {}
pending_invoices = {}

# ============= ОСНОВНЫЕ ФУНКЦИИ =============
def is_admin(user_id):
    return user_id in ADMINS

def check_subscription(user_id):
    if user_id in subscribed_users:
        subscription = subscribed_users[user_id]
        if datetime.now().timestamp() < subscription['expires_at']:
            return True
        else:
            del subscribed_users[user_id]
            return False
    
    subscription = db.get_active_subscription(user_id)
    if subscription:
        expires_at = datetime.strptime(subscription['expires_at'], '%Y-%m-%d %H:%M:%S').timestamp()
        subscribed_users[user_id] = {
            'expires_at': expires_at,
            'plan': subscription['plan_id']
        }
        return True
    return False

def check_channel_subscription(user_id):
    try:
        for channel in CHANNELS:
            try:
                time.sleep(TELEGRAM_API_DELAY)
                member = bot.get_chat_member(channel['id'], user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception as e:
                debug_log(f"Ошибка проверки подписки на {channel['name']}: {e}")
                return False
        return True
    except Exception as e:
        debug_log(f"Общая ошибка проверки подписки: {e}")
        return False

def create_invoice(amount, plan_id):
    try:
        headers = {
            'Crypto-Pay-API-Token': CRYPTOPAY_TOKEN,
            'Content-Type': 'application/json'
        }
        
        data = {
            'amount': str(amount),
            'asset': 'USDT',
            'description': f'Подписка MonoFreez - {SUBSCRIPTION_PLANS[plan_id]["days"]} дней',
        }
        
        debug_log(f"Создаю счет на сумму {amount} USDT для плана {plan_id}")
        
        response = requests.post(
            f'{CRYPTOPAY_API_URL}createInvoice', 
            headers=headers, 
            json=data,
            timeout=30
        )
        
        debug_log(f"Ответ CryptoPay: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            debug_log(f"Результат CryptoPay: {result}")
            
            if result.get('ok'):
                invoice = result['result']
                return {
                    'invoice_id': str(invoice['invoice_id']),
                    'pay_url': invoice['pay_url'],
                    'amount': invoice['amount'],
                    'asset': invoice['asset']
                }
            else:
                debug_log(f"Ошибка CryptoPay: {result.get('error', 'Неизвестная ошибка')}")
        else:
            debug_log(f"HTTP ошибка: {response.status_code} - {response.text}")
        
        return None
    except Exception as e:
        debug_log(f"Ошибка при создании счета: {e}")
        traceback.print_exc()
        return None

def check_invoice_status(invoice_id):
    try:
        headers = {
            'Crypto-Pay-API-Token': CRYPTOPAY_TOKEN
        }
        
        debug_log(f"Проверяю статус счета {invoice_id}")
        
        response = requests.get(
            f'{CRYPTOPAY_API_URL}getInvoices?invoice_ids={invoice_id}', 
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            debug_log(f"Статус счета: {result}")
            
            if result.get('ok') and result['result']['items']:
                invoice = result['result']['items'][0]
                return invoice['status']
        return None
    except Exception as e:
        debug_log(f"Ошибка при проверке счета: {e}")
        return None

async def send_glban_message_async(username):
    try:
        client = create_telethon_client()
        await client.start()
        await client.send_message('me', f'.glban2 {username}')
        await client.disconnect()
        return True
    except Exception as e:
        debug_log(f"Ошибка отправки glban2: {e}")
        return False

def send_glban_message(username):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_glban_message_async(username))
        return result
    finally:
        loop.close()

async def check_user_dc_async(username):
    try:
        client = create_telethon_client()
        await client.start()
        user = await client.get_entity(username)
        photo = user.photo
        dc_id = None
        
        if isinstance(photo, UserProfilePhoto):
            dc_id = photo.dc_id
        elif isinstance(photo, ChatPhoto):
            dc_id = photo.dc_id
        elif isinstance(photo, Photo):
            dc_id = photo.dc_id
        
        await client.disconnect()
        return dc_id
    except Exception as e:
        debug_log(f"Ошибка проверки DC: {e}")
        return None
    return None

def check_user_dc(username):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(check_user_dc_async(username))
        return result
    finally:
        loop.close()

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
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = 5
                debug_log(f"Ошибка 429. Ждем {retry_after} секунд")
                time.sleep(retry_after)
            elif attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка отправки (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                debug_log(f"Финальная ошибка отправки: {e}")
                # Попробуем отправить без форматирования
                try:
                    return bot.send_message(chat_id, text, parse_mode=None)
                except:
                    raise e
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка отправки (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                raise e
    return None

def safe_edit_message_text(chat_id, message_id, text, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(TELEGRAM_API_DELAY)
            return bot.edit_message_text(text, chat_id, message_id, **kwargs)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 429:
                retry_after = 5
                debug_log(f"Ошибка 429 при редактировании. Ждем {retry_after} секунд")
                time.sleep(retry_after)
            elif attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка редактирования (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                debug_log(f"Финальная ошибка редактирования: {e}")
                try:
                    return bot.edit_message_text(text, chat_id, message_id, parse_mode=None)
                except:
                    raise e
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                debug_log(f"Ошибка редактирования (попытка {attempt + 1}): {e}")
                time.sleep(1)
            else:
                raise e
    return None

# ============= МЕНЮ =============
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    send_btn = types.InlineKeyboardButton("Отправка", callback_data='send')
    profile_btn = types.InlineKeyboardButton("Профиль", callback_data='profile')
    logs_btn = types.InlineKeyboardButton("Логи бота", url=LOGS_LINK)
    markup.add(send_btn, profile_btn, logs_btn)
    return markup

def subscription_plans_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        btn = types.InlineKeyboardButton(text=plan['label'], callback_data=f'plan_{plan_id}')
        markup.add(btn)
    return markup

def payment_menu(invoice_id, pay_url):
    markup = types.InlineKeyboardMarkup(row_width=2)
    pay_btn = types.InlineKeyboardButton(text="💳 Оплатить", url=pay_url)
    check_btn = types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f'check_payment_{invoice_id}')
    markup.add(pay_btn, check_btn)
    return markup

# ============= АДМИНСКИЕ КОМАНДЫ =============
@bot.message_handler(commands=['sub'])
def handle_subscription_grant(message):
    debug_log(f"Команда /sub от {message.from_user.id}")
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 3:
            safe_send_message(message.chat.id, 
                            "❌ Неправильный формат команды\n\n"
                            "Используйте: /sub ID_пользователя дни\n\n"
                            "Пример: /sub 5522585352 30")
            return
        
        target_user_id = int(args[1])
        days = int(args[2])
        
        if days <= 0:
            safe_send_message(message.chat.id, "❌ Количество дней должно быть больше 0!")
            return
        
        expires_at = datetime.now() + timedelta(days=days)
        
        db.add_subscription(
            target_user_id,
            'manual',
            expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            user_id,
            days
        )
        
        subscribed_users[target_user_id] = {
            'expires_at': expires_at.timestamp(),
            'plan': 'manual',
            'admin': user_id,
            'granted_at': datetime.now().timestamp(),
            'days': days
        }
        
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        admin_msg = f"""✅ Подписка успешно выдана!

👤 ID пользователя: {target_user_id}
📅 Срок: {days} дней
📆 Действует до: {expires_str}
👑 Выдал: @{message.from_user.username if message.from_user.username else 'админ'}"""
        
        safe_send_message(message.chat.id, admin_msg)
        
        # Пробуем уведомить пользователя
        try:
            user_msg = f"""✅ Вам выдана подписка на бота!

📅 Срок подписки: {days} дней
📆 Действует до: {expires_str}

Для активации напишите /start"""
            safe_send_message(target_user_id, user_msg)
        except Exception as e:
            debug_log(f"Не удалось уведомить пользователя {target_user_id}: {e}")
            safe_send_message(message.chat.id, f"⚠️ Не удалось отправить уведомление пользователю {target_user_id}")
        
    except ValueError:
        safe_send_message(message.chat.id, "❌ Ошибка! Убедитесь, что ID и количество дней указаны цифрами!")
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        debug_log(f"Ошибка в /sub: {e}")

@bot.message_handler(commands=['unsub'])
def handle_subscription_revoke(message):
    debug_log(f"Команда /unsub от {message.from_user.id}")
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 2:
            safe_send_message(message.chat.id, 
                            "❌ Неправильный формат команды!\n\n"
                            "Используйте: /unsub ID_пользователя\n\n"
                            "Пример: /unsub 5522585352")
            return
        
        target_user_id = int(args[1])
        
        subscription = db.get_active_subscription(target_user_id)
        
        if subscription:
            db.remove_subscription(target_user_id)
            
            if target_user_id in subscribed_users:
                del subscribed_users[target_user_id]
            
            admin_msg = f"""✅ Подписка успешно снята!

👤 ID пользователя: {target_user_id}
👑 Снял: @{message.from_user.username if message.from_user.username else 'админ'}"""
            
            safe_send_message(message.chat.id, admin_msg)
            
            # Пробуем уведомить пользователя
            try:
                user_msg = f"""⚠️ Ваша подписка на бота была снята администратором!

Если это ошибка, обратитесь к администрации."""
                safe_send_message(target_user_id, user_msg)
            except Exception as e:
                debug_log(f"Не удалось уведомить пользователя {target_user_id}: {e}")
                safe_send_message(message.chat.id, f"⚠️ Не удалось отправить уведомление пользователю {target_user_id}")
        else:
            safe_send_message(message.chat.id, f"❌ У пользователя {target_user_id} нет активной подписки!")
            
    except ValueError:
        safe_send_message(message.chat.id, "❌ Ошибка! Убедитесь, что ID указан цифрами!")
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        debug_log(f"Ошибка в /unsub: {e}")

@bot.message_handler(commands=['userinfo'])
def handle_user_info(message):
    debug_log(f"Команда /userinfo от {message.from_user.id}")
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 2:
            safe_send_message(message.chat.id, 
                            "❌ Неправильный формат команды!\n\n"
                            "Используйте: /userinfo ID_пользователя\n\n"
                            "Пример: /userinfo 5522585352")
            return
        
        target_user_id = int(args[1])
        user_stats = db.get_user_stats(target_user_id)
        
        if user_stats:
            subscription = db.get_active_subscription(target_user_id)
            
            if subscription:
                expires_date = datetime.strptime(subscription['expires_at'], '%Y-%m-%d %H:%M:%S')
                expires_str = expires_date.strftime("%d.%m.%Y %H:%M")
                subscription_info = f"✅ Активна (до {expires_str})"
            else:
                subscription_info = "❌ Не активна"
            
            info_msg = f"""📊 Информация о пользователе:

🆔 ID: {target_user_id}
👤 Имя: {user_stats.get('first_name', 'Не указано')}
📛 Фамилия: {user_stats.get('last_name', 'Не указано')}
🔗 Username: @{user_stats.get('username', 'Не указано')}
📅 Зарегистрирован: {user_stats.get('registered_at', 'Не известно')}
📊 Количество запросов: {user_stats.get('log_count', 0)}
🚫 Банов выполнено: {user_stats.get('bans_count', 0)}
💎 Подписка: {subscription_info}"""
            
            safe_send_message(message.chat.id, info_msg)
        else:
            safe_send_message(message.chat.id, f"❌ Пользователь {target_user_id} не найден в базе данных!")
            
    except ValueError:
        safe_send_message(message.chat.id, "❌ Ошибка! Убедитесь, что ID указан цифрами!")
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        debug_log(f"Ошибка в /userinfo: {e}")

@bot.message_handler(commands=['stats'])
def handle_bot_stats(message):
    debug_log(f"Команда /stats от {message.from_user.id}")
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        total_users = len(db.get_all_users())
        
        # Получаем активные подписки
        active_subs = 0
        for user_id in db.get_all_users():
            if db.get_active_subscription(user_id):
                active_subs += 1
        
        total_bans, unique_banned_users, total_groups_banned = db.get_ban_stats()
        
        stats_msg = f"""📈 Статистика бота:

👥 Всего пользователей: {total_users}
💎 Активных подписок: {active_subs}

🔒 Статистика банов:
🚫 Всего банов: {total_bans}
👤 Уникальных забаненных: {unique_banned_users}
📊 Всего групп забанено: {total_groups_banned}

Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
        
        safe_send_message(message.chat.id, stats_msg)
        
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка при получении статистики: {str(e)}")
        debug_log(f"Ошибка в /stats: {e}")

@bot.message_handler(commands=['rs'])
def handle_broadcast(message):
    debug_log(f"Команда /rs от {message.from_user.id}")
    
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        safe_send_message(message.chat.id, "❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        broadcast_text = message.text[4:].strip()
        
        if not broadcast_text:
            safe_send_message(message.chat.id, 
                            "❌ Укажите текст для рассылки!\n\n"
                            "Используйте: /rs ваш_текст")
            return
        
        markup = types.InlineKeyboardMarkup()
        confirm_btn = types.InlineKeyboardButton("✅ Да, отправить", callback_data=f'broadcast_confirm_{user_id}')
        cancel_btn = types.InlineKeyboardButton("❌ Отмена", callback_data='broadcast_cancel')
        markup.add(confirm_btn, cancel_btn)
        
        safe_send_message(
            message.chat.id,
            f"📢 Подтверждение рассылки\n\nТекст:\n{broadcast_text}\n\nОтправить всем пользователям?",
            reply_markup=markup
        )
        
        if not hasattr(bot, 'broadcast_messages'):
            bot.broadcast_messages = {}
        bot.broadcast_messages[user_id] = broadcast_text
        
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка: {str(e)}")
        debug_log(f"Ошибка в /rs: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('broadcast_confirm_'))
def handle_broadcast_confirm(call):
    admin_id = int(call.data.split('_')[-1])
    
    if call.from_user.id != admin_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша рассылка!", show_alert=True)
        return
    
    if not hasattr(bot, 'broadcast_messages') or admin_id not in bot.broadcast_messages:
        bot.answer_callback_query(call.id, "❌ Текст рассылки не найден!", show_alert=True)
        return
    
    broadcast_text = bot.broadcast_messages[admin_id]
    
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⏳ Начинаю рассылку..."
    )
    
    all_users = db.get_all_users()
    
    for admin in ADMINS:
        if admin not in all_users:
            all_users.append(admin)
    
    success_count = 0
    fail_count = 0
    
    for user_id in all_users:
        try:
            final_text = f"""📢 Рассылка от администратора\n\n{broadcast_text}"""
            
            safe_send_message(user_id, final_text)
            success_count += 1
            time.sleep(TELEGRAM_API_DELAY)
            
        except Exception as e:
            fail_count += 1
            debug_log(f"Ошибка при отправке пользователю {user_id}: {e}")
    
    report = f"""✅ Рассылка завершена!

📊 Статистика:
✅ Успешно: {success_count}
❌ Не удалось: {fail_count}
📈 Всего: {len(all_users)}"""
    
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=report
    )
    
    if hasattr(bot, 'broadcast_messages'):
        bot.broadcast_messages.pop(admin_id, None)

@bot.callback_query_handler(func=lambda call: call.data == 'broadcast_cancel')
def handle_broadcast_cancel(call):
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="❌ Рассылка отменена"
    )

# ============= ОСНОВНЫЕ КОМАНДЫ =============
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    debug_log(f"Пользователь {user_id} запустил /start")
    
    try:
        db.add_user(user_id, username, first_name, last_name)
        debug_log(f"Пользователь {user_id} добавлен в БД")
    except Exception as e:
        debug_log(f"Ошибка добавления пользователя {user_id}: {e}")
    
    if check_subscription(user_id):
        if check_channel_subscription(user_id):
            safe_send_message(message.chat.id, 
                           "MonoFreez - Добро пожаловать!\n\nВыбирай что делаем:", 
                           reply_markup=main_menu())
        else:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for channel in CHANNELS:
                btn = types.InlineKeyboardButton(text=channel['name'], url=channel['url'])
                markup.add(btn)
            check_btn = types.InlineKeyboardButton(text="Я подписался", callback_data='check_channel_subscription')
            markup.add(check_btn)
            
            safe_send_message(message.chat.id,
                           "Для начала необходимо подписаться на каналы ниже\n\nПосле подписки нажмите кнопку \"Я подписался\"",
                           reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        buy_btn = types.InlineKeyboardButton("💰 Купить подписку", callback_data='buy_subscription')
        markup.add(buy_btn)
        
        safe_send_message(message.chat.id,
                       "MonoFreez - Добро пожаловать!\n\nПохоже, ваша подписка истекла, пожалуйста, приобретите её по кнопке ниже:",
                       reply_markup=markup)

# ============= ОПЛАТА =============
@bot.callback_query_handler(func=lambda call: call.data == 'buy_subscription')
def handle_buy_subscription(call):
    debug_log(f"Покупка подписки user_id={call.from_user.id}")
    bot.answer_callback_query(call.id)
    
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="⚡ Выберите срок подписки:",
        reply_markup=subscription_plans_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('plan_'))
def handle_plan_selection(call):
    user_id = call.from_user.id
    plan_id = call.data.replace('plan_', '')
    
    debug_log(f"Выбран план {plan_id} user_id={user_id}")
    
    if plan_id not in SUBSCRIPTION_PLANS:
        bot.answer_callback_query(call.id, "❌ Неверный план подписки", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    # Создаем счет
    invoice = create_invoice(plan['price'], plan_id)
    
    if invoice:
        # Сохраняем счет в БД
        db.add_invoice(invoice['invoice_id'], user_id, invoice['amount'], invoice['asset'], plan_id)
        
        # Сохраняем в кэш
        pending_invoices[invoice['invoice_id']] = {
            'user_id': user_id,
            'amount': invoice['amount'],
            'asset': invoice['asset'],
            'plan_id': plan_id
        }
        
        invoice_text = f"""✅ Создан счет на оплату!

💳 Сумма: {plan['price']}$
📅 Количество дней: {plan['days']}
🆔 ID Счета: {invoice['invoice_id']}

👇 После оплаты нажмите на кнопку ниже"""
        
        safe_edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=invoice_text,
            reply_markup=payment_menu(invoice['invoice_id'], invoice['pay_url'])
        )
    else:
        debug_log(f"Ошибка создания счета для плана {plan_id}")
        safe_edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Ошибка при создании счета. Попробуйте позже."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment_'))
def handle_check_payment(call):
    invoice_id = call.data.replace('check_payment_', '')
    user_id = call.from_user.id
    
    debug_log(f"Проверка оплаты invoice_id={invoice_id} user_id={user_id}")
    
    # Получаем счет из БД
    invoice = db.get_invoice(invoice_id)
    
    if not invoice:
        debug_log(f"Счет {invoice_id} не найден в БД")
        bot.answer_callback_query(call.id, "❌ Счет не найден", show_alert=True)
        return
    
    if invoice['user_id'] != user_id:
        debug_log(f"Пользователь {user_id} пытается проверить чужой счет")
        bot.answer_callback_query(call.id, "❌ Это не ваш счет", show_alert=True)
        return
    
    # Проверяем статус счета
    status = check_invoice_status(invoice_id)
    debug_log(f"Статус счета {invoice_id}: {status}")
    
    if status == 'paid':
        # Обновляем статус в БД
        db.update_invoice_status(invoice_id, 'paid')
        
        # Активируем подписку
        plan_id = invoice['plan_id']
        plan = SUBSCRIPTION_PLANS[plan_id]
        
        expires_at = datetime.now() + timedelta(days=plan['days'])
        db.add_subscription(
            user_id,
            plan_id,
            expires_at.strftime('%Y-%m-%d %H:%M:%S'),
            None,
            plan['days']
        )
        
        # Обновляем кэш
        subscribed_users[user_id] = {
            'expires_at': expires_at.timestamp(),
            'plan': plan_id,
            'activated_at': datetime.now().timestamp()
        }
        
        # Удаляем из pending_invoices
        if invoice_id in pending_invoices:
            del pending_invoices[invoice_id]
        
        expires_str = expires_at.strftime("%d.%m.%Y %H:%M")
        
        success_msg = f"""✅ Оплата получена!

🌟 Подписка активирована!
📅 Срок: {plan['days']} дней
📆 Действует до: {expires_str}

Для продолжения напишите /start"""
        
        safe_edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=success_msg
        )
        
        # Логируем успешную оплату
        log_msg = f"""💰 *Успешная оплата подписки*

👤 *Пользователь:* @{call.from_user.username if call.from_user.username else call.from_user.id}
💳 *Сумма:* {plan['price']}$
📅 *Срок:* {plan['days']} дней
🆔 *ID счета:* {invoice_id}"""
        
        send_log_to_channel(log_msg)
        
    elif status == 'active':
        bot.answer_callback_query(
            call.id,
            "⏳ Оплата еще не получена. Попробуйте позже.",
            show_alert=True
        )
    elif status == 'expired':
        db.update_invoice_status(invoice_id, 'expired')
        bot.answer_callback_query(
            call.id,
            "❌ Счет просрочен. Создайте новый.",
            show_alert=True
        )
    else:
        bot.answer_callback_query(
            call.id,
            f"❌ Статус счета: {status or 'неизвестен'}",
            show_alert=True
        )

# ============= ОСТАЛЬНЫЕ ОБРАБОТЧИКИ =============
@bot.callback_query_handler(func=lambda call: call.data == 'check_channel_subscription')
def handle_check_channel_subscription(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    if check_channel_subscription(user_id):
        if check_subscription(user_id):
            safe_edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ Отлично! Доступ к боту разрешён!\n\nПиши /start"
            )
        else:
            bot.answer_callback_query(call.id, "❌ У вас нет активной подписки!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "❌ Кажется, ты не подписался на все каналы!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == 'send')
def handle_send_button(call):
    user_id = call.from_user.id
    debug_log(f"Нажата кнопка Отправка user_id={user_id}")
    
    db.update_user_activity(user_id)
    
    # Ответ на callback ВСЕГДА первым делом
    bot.answer_callback_query(call.id)
    
    if not check_subscription(user_id):
        safe_send_message(call.message.chat.id, "❌ У вас нет активной подписки!")
        return
    
    if not check_channel_subscription(user_id):
        safe_send_message(call.message.chat.id, "❌ Сначала необходимо подписаться на каналы!")
        return
    
    cooldown_remaining = db.get_cooldown(user_id)
    if cooldown_remaining > 0:
        minutes = int(cooldown_remaining // 60)
        seconds = int(cooldown_remaining % 60)
        safe_send_message(call.message.chat.id, f"⏳ Подождите {minutes}:{seconds:02d} перед повторным использованием!")
        return
    
    db.set_cooldown(user_id)
    
    # Отправляем новое сообщение вместо редактирования
    msg = safe_send_message(
        call.message.chat.id,
        "🔗 Отправь мне @username пользователя:\n\nПример: @username или просто username\n\nОтправляй username одним сообщением"
    )
    
    if msg:
        debug_log("Сообщение отправлено, регистрируем обработчик")
        bot.register_next_step_handler(msg, process_username_step)
    else:
        debug_log("Ошибка отправки сообщения")
        safe_send_message(call.message.chat.id, "❌ Ошибка. Попробуйте снова /start")

def process_username_step(message):
    debug_log(f"НАЧАЛО process_username_step от {message.from_user.id}")
    
    user_id = message.from_user.id
    username_input = message.text.strip()
    
    debug_log(f"Получен текст: '{username_input}'")
    
    # Удаляем @ если есть
    if username_input.startswith('@'):
        username_input = username_input[1:]
    
    username = username_input.strip()
    
    debug_log(f"Очищенный username: '{username}'")
    
    # Проверка валидности
    if not username or len(username) < 3 or ' ' in username:
        debug_log(f"Некорректный username")
        safe_send_message(
            message.chat.id,
            "❌ Некорректный username. Минимум 3 символа, без пробелов.\n\nВернитесь в меню /start"
        )
        return
    
    # ОТВЕЧАЕМ ПОЛЬЗОВАТЕЛЮ СРАЗУ (без Markdown)
    status_msg = safe_send_message(
        message.chat.id,
        f"✅ Запрос принят!\n\n👤 Цель: @{username}\n📊 Групп для обработки: {len(GROUPS)}\n⏳ Начинаю обработку..."
    )
    
    if not status_msg:
        debug_log("Не удалось отправить статус")
        return
    
    # Запускаем обработку в отдельном потоке
    def process_in_background():
        try:
            debug_log(f"Начинаем фоновую обработку @{username}")
            
            # 1. Логируем в канал
            initiator = message.from_user.username if message.from_user.username else message.from_user.id
            log_msg = f"""*📥 Получен новый запрос*

👤 *Инициатор:* @{initiator}
🎯 *Цель:* @{username}
🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}
📊 *Групп:* {len(GROUPS)}"""
            
            send_log_to_channel(log_msg)
            db.add_log(user_id, username, 'request_received', f"Групп: {len(GROUPS)}")
            
            # 2. Проверяем DC
            debug_log("Проверка DC...")
            dc_id = check_user_dc(username.lower())
            allowed_dc = [1, 3, 5]
            
            if dc_id is not None:
                dc_log = f"""*🔍 Проверка DC*

🎯 *Цель:* @{username}
⚡ *Датацентр:* {dc_id}
✅ *Статус:* {'✅ Допустим' if dc_id in allowed_dc else '❌ Недопустим'}"""
                send_log_to_channel(dc_log)
            
            # 3. Проверка на недопустимый DC
            if dc_id is not None and dc_id not in allowed_dc:
                reject_log = f"""*❌ Запрос отклонён!*

👤 *Инициатор:* @{initiator}
🎯 *Цель:* @{username}
⚡ *DC:* {dc_id}
❌ *Причина:* Недопустимый датацентр (разрешены: 1/3/5)"""
                
                send_log_to_channel(reject_log)
                db.add_log(user_id, username, 'rejected_dc', f"DC: {dc_id}")
                
                # Уведомляем пользователя
                safe_send_message(
                    message.chat.id,
                    f"❌ Запрос отклонён!\n\nЦель: @{username}\nПричина: Недопустимый датацентр (DC{dc_id})\nРазрешены: DC1, DC3, DC5"
                )
                return
            
            # 4. Отправляем glban2 команду
            debug_log("Отправка glban2 команды...")
            glban_success = send_glban_message(username.lower())
            
            glban_log = f"""*⚡ Команда glban2*

🎯 *Цель:* @{username}
✅ *Статус:* {'Отправлена' if glban_success else 'Ошибка отправки'}"""
            send_log_to_channel(glban_log)
            
            # 5. Выполняем автоматический бан
            debug_log("Начинаем автоматический бан...")
            start_time = datetime.now()
            
            ban_start_log = f"""*🔨 Начало автоматического бана*

🎯 *Цель:* @{username}
📊 *Групп:* {len(GROUPS)}
🕐 *Время:* {start_time.strftime('%H:%M:%S')}"""
            send_log_to_channel(ban_start_log)
            
            banned_count, total_groups, errors = ban_user_in_all_groups(username)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 6. Сохраняем результат
            target_user_id = 0
            try:
                client = create_telethon_client()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(client.start())
                user_entity = loop.run_until_complete(client.get_entity(username))
                target_user_id = user_entity.id
                loop.run_until_complete(client.disconnect())
                loop.close()
            except:
                pass
            
            db.add_ban_record(
                target_user_id=target_user_id,
                target_username=username,
                banned_by=user_id,
                groups_banned=banned_count,
                total_groups=total_groups,
                errors=errors
            )
            
            # 7. Логируем результат
            if banned_count > 0:
                result_log = f"""*✅ Бан выполнен успешно!*

🎯 *Цель:* @{username}
📊 *Результат:* {banned_count}/{total_groups} групп
⏱️ *Длительность:* {duration:.1f} сек
✅ *Статус:* Успешно"""
                
                if errors:
                    result_log += f"\n\n⚠️ *Ошибок:* {len(errors)}"
                
                db.add_log(user_id, username, 'ban_completed', f"Успешно: {banned_count}/{total_groups}")
                
                # Уведомляем пользователя об успехе
                user_result = f"""✅ Автоматический бан выполнен!

👤 Цель: @{username}
🚫 Забанен в: {banned_count} группах
📊 Всего групп: {total_groups}
⏱️ Время: {duration:.1f} сек"""
                
                if errors:
                    user_result += f"\n\n⚠️ Ошибок: {len(errors)}"
                
            else:
                result_log = f"""*❌ Бан не выполнен!*

🎯 *Цель:* @{username}
📊 *Результат:* 0/{total_groups} групп
⏱️ *Длительность:* {duration:.1f} сек
❌ *Статус:* Неудача"""
                
                if errors:
                    error_msg = errors[0] if errors else "Неизвестная ошибка"
                    result_log += f"\n\n❌ *Ошибка:* {error_msg}"
                
                db.add_log(user_id, username, 'ban_failed', f"Ошибки: {len(errors)}")
                
                # Уведомляем пользователя о неудаче
                user_result = f"""❌ Автоматический бан не выполнен

👤 Цель: @{username}
📊 Групп проверено: {total_groups}
⏱️ Время: {duration:.1f} сек
❌ Причина: {errors[0] if errors else 'Неизвестная ошибка'}"""
            
            send_log_to_channel(result_log)
            
            # 8. Отправляем результат пользователю
            safe_send_message(message.chat.id, user_result)
            
            # 9. Показываем главное меню
            safe_send_message(
                message.chat.id,
                "MonoFreez - Добро пожаловать!\n\nВыбирай что делаем:",
                reply_markup=main_menu()
            )
            
            debug_log(f"Обработка @{username} завершена")
            
        except Exception as e:
            debug_log(f"💀 Ошибка в фоновой обработке: {e}")
            traceback.print_exc()
            
            error_log = f"""*💀 Критическая ошибка!*

🎯 *Цель:* @{username}
❌ *Ошибка:* {str(e)[:200]}
🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}"""
            
            send_log_to_channel(error_log)
            
            safe_send_message(
                message.chat.id,
                f"❌ Критическая ошибка!\n\nЦель: @{username}\nОшибка: {str(e)[:100]}\n\nВернитесь в меню /start"
            )
    
    # Запускаем в отдельном потоке
    thread = Thread(target=process_in_background)
    thread.start()
    debug_log("Фоновый поток запущен")

@bot.callback_query_handler(func=lambda call: call.data == 'profile')
def handle_profile(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    
    subscription = db.get_active_subscription(user_id)
    
    if subscription:
        expires_date = datetime.strptime(subscription['expires_at'], '%Y-%m-%d %H:%M:%S')
        expires_str = expires_date.strftime("%d.%m.%Y %H:%M")
        
        profile_text = f"""Ваш профиль

Ваш ID: {user_id}
Подписка: ✅ Активна
Действует до: {expires_str}"""
    else:
        profile_text = f"""Ваш профиль

Ваш ID: {user_id}
Подписка: ❌ Не активна"""
    
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("⏪ Назад", callback_data='back_to_main')
    markup.add(back_btn)
    
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=profile_text,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def handle_back_to_main(call):
    bot.answer_callback_query(call.id)
    safe_edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="MonoFreez - Добро пожаловать!\n\nВыбирай что делаем:",
        reply_markup=main_menu()
    )

# Запуск бота
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 Бот MonoFreez запускается...")
    print(f"👑 Админы: {ADMINS}")
    print(f"📢 Каналы для подписки: {len(CHANNELS)}")
    print(f"📊 Групп для бана: {len(GROUPS)}")
    print("=" * 50)
    
    bot_start_time = datetime.now()
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Запускаю polling...")
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
            
        except KeyboardInterrupt:
            print("\n⚠️ Бот остановлен пользователем")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            traceback.print_exc()
            print("Перезапуск через 10 секунд...")
            time.sleep(10)
