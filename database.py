import aiosqlite
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

DB_NAME = "database.db"

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                subscribed_until TEXT,
                is_active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица ожидающих платежей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                days INTEGER,
                amount REAL,
                created_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Таблица статистики
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                date TEXT PRIMARY KEY,
                actions INTEGER DEFAULT 0,
                payments INTEGER DEFAULT 0
            )
        ''')
        
        await db.commit()

async def check_subscription(user_id: int) -> bool:
    """Проверка активной подписки"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT subscribed_until FROM users WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if row:
                until = datetime.fromisoformat(row[0])
                return until > datetime.now()
            return False

async def add_subscription(user_id: int, days: int):
    """Добавление/продление подписки"""
    until = datetime.now() + timedelta(days=days)
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, subscribed_until, is_active) VALUES (?, ?, 1)",
            (user_id, until.isoformat())
        )
        await db.commit()

async def remove_subscription(user_id: int):
    """Удаление подписки"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()

async def add_pending_payment(invoice_id: str, user_id: int, days: int, amount: float):
    """Добавление ожидающего платежа"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO pending_payments (invoice_id, user_id, days, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, user_id, days, amount, datetime.now().isoformat())
        )
        await db.commit()

async def update_payment_status(invoice_id: str, status: str):
    """Обновление статуса платежа"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE pending_payments SET status = ? WHERE invoice_id = ?",
            (status, invoice_id)
        )
        await db.commit()

async def get_pending_payments():
    """Получение всех ожидающих платежей"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT invoice_id, user_id, days FROM pending_payments WHERE status = 'pending'"
        ) as cursor:
            return await cursor.fetchall()

async def get_user_stats():
    """Получение статистики"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Количество активных подписок
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cursor:
            active_users = (await cursor.fetchone())[0]
        
        # Общее количество действий
        async with db.execute("SELECT SUM(actions) FROM stats") as cursor:
            total_actions = (await cursor.fetchone())[0] or 0
        
        # Количество платежей сегодня
        today = datetime.now().strftime('%Y-%m-%d')
        async with db.execute("SELECT payments FROM stats WHERE date = ?", (today,)) as cursor:
            row = await cursor.fetchone()
            today_payments = row[0] if row else 0
        
        return {
            "active_users": active_users,
            "total_actions": total_actions,
            "today_payments": today_payments
        }