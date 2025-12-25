import asyncio
import time
import random
import sqlite3
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import ChatBannedRights
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import InputReportReasonSpam
import config

class Config:
    API_ID = config.API_ID
    API_HASH = config.API_HASH
    SESSION_STRING = config.SESSION_STRING
    GROUPS = config.GROUPS
    CHECK_INTERVAL = 10
    LOG_CHANNEL_ID = config.LOG_CHANNEL_ID
    
    BAN_RIGHTS = ChatBannedRights(
        until_date=datetime.now().timestamp() + 3153600000,
        view_messages=True,
        send_messages=True,
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True,
    )

class WorkerDatabase:
    def __init__(self, db_name='worker.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_text TEXT,
            target_username TEXT,
            status TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            reports_sent INTEGER DEFAULT 0,
            bans_sent INTEGER DEFAULT 0,
            groups_used INTEGER DEFAULT 0,
            error_message TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_activity (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            reports_sent INTEGER DEFAULT 0,
            bans_sent INTEGER DEFAULT 0,
            last_activity TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        ''')
        conn.commit()
        conn.close()

class GLBanWorker:
    def __init__(self):
        self.config = Config()
        self.db = WorkerDatabase()
        session = StringSession(self.config.SESSION_STRING)
        self.client = TelegramClient(session, int(self.config.API_ID), self.config.API_HASH)
        print(f"🚀 Worker инициализирован, групп: {len(self.config.GROUPS)}")
    
    async def start(self):
        await self.client.start()
        me = await self.client.get_me()
        print(f"✅ Авторизован: @{me.username}")
        
        @self.client.on(events.NewMessage(outgoing=True))
        async def message_handler(event):
            if event.text and event.text.startswith('.glban2'):
                await self.process_command_live(event)
        
        print(f"\n🔍 Ожидаю команды .glban2...")
        await self.client.run_until_disconnected()
    
    async def process_command_live(self, event):
        try:
            parts = event.text.split()
            if len(parts) < 2:
                await event.edit("❌ Формат: .glban2 @username")
                return
            
            username = parts[1].replace('@', '')
            await event.edit(f"⚡ Начинаю GLBAN2 для @{username}...")
            
            try:
                target = await self.client.get_entity(username)
                user_id = target.id
                await event.edit(f"✅ Найден: @{username} (ID: {user_id})")
            except Exception as e:
                await event.edit(f"❌ Не найден: {e}")
                return
            
            results = await self.process_user(target)
            report = self.create_report(username, results)
            await event.edit(report)
            
        except Exception as e:
            await event.edit(f"💀 Ошибка: {str(e)[:200]}")
    
    async def process_user(self, target_user):
        results = {
            'groups_processed': 0,
            'reports_sent': 0,
            'bans_sent': 0,
            'errors': 0
        }
        
        for group_id in self.config.GROUPS:
            try:
                group_result = await self.process_group(group_id, target_user)
                results['groups_processed'] += 1
                results['reports_sent'] += group_result['report_sent']
                results['bans_sent'] += group_result['ban_sent']
                results['errors'] += group_result['error']
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                results['errors'] += 1
                print(f"❌ Ошибка в группе {group_id}: {e}")
        
        return results
    
    async def process_group(self, group_id, target_user):
        result = {'report_sent': 0, 'ban_sent': 0, 'error': 0}
        
        try:
            group = await self.client.get_entity(group_id)
            group_name = group.title if hasattr(group, 'title') else f"ID: {group_id}"
            
            try:
                await self.client(EditBannedRequest(
                    channel=group,
                    participant=target_user,
                    banned_rights=self.config.BAN_RIGHTS
                ))
                result['ban_sent'] = 1
                print(f"  ✅ Бан в {group_name}")
            except Exception as e:
                error_msg = str(e)
                if "USER_NOT_PARTICIPANT" not in error_msg:
                    result['error'] = 1
                    print(f"  ⚠️ Не удалось забанить в {group_name}: {error_msg[:40]}")
            
            try:
                await self.client(ReportRequest(
                    peer=group,
                    id=[target_user.id],
                    reason=InputReportReasonSpam(),
                    message=""
                ))
                result['report_sent'] = 1
                print(f"  📝 Жалоба в {group_name}")
            except Exception as e:
                if "USER_NOT_PARTICIPANT" not in str(e):
                    result['error'] += 1
                    print(f"  ⚠️ Не удалось отправить жалобу в {group_name}")
            
        except Exception as e:
            result['error'] += 1
            print(f"  ❌ Ошибка доступа к группе {group_id}: {e}")
        
        return result
    
    def create_report(self, username, results):
        return f"""✅ GLBAN2 завершен для @{username}

📊 Результаты:
├─ Групп обработано: {results['groups_processed']}/{len(self.config.GROUPS)}
├─ Банов выполнено: {results['bans_sent']}
├─ Жалоб отправлено: {results['reports_sent']}
├─ Ошибок: {results['errors']}
└─ Время: {datetime.now().strftime('%H:%M:%S')}"""

async def main():
    print("=" * 50)
    print("🚀 ЗАПУСК GLBAN WORKER")
    print("=" * 50)
    
    worker = GLBanWorker()
    await worker.start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Остановлено")
    except Exception as e:
        print(f"\n💀 Ошибка: {e}")