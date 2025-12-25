#!/usr/bin/env python3
import subprocess
import sys
import os

def install_requirements():
    """Установка зависимостей"""
    print("📦 Устанавливаю зависимости...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Зависимости установлены")

def check_env_file():
    """Проверка .env файла"""
    if not os.path.exists(".env"):
        print("❌ Файл .env не найден!")
        print("Создайте .env файл со следующим содержимым:")
        print("""
BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
API_ID=1234567
API_HASH=ваш_api_hash
CRYPTOPAY_TOKEN=ВАШ_ТОКЕН_ОТ_CRYPTOBOT
ADMIN_IDS=123456789
        """)
        return False
    return True

def main():
    """Основная функция запуска"""
    print("🚀 Запуск Фризер-бота...")
    
    # Проверяем .env
    if not check_env_file():
        return
    
    # Устанавливаем зависимости
    try:
        install_requirements()
    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        return
    
    # Запускаем бота
    print("🤖 Запускаю бота...")
    try:
        import asyncio
        from bot import main as run_bot
        asyncio.run(run_bot())
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Попробуйте установить зависимости вручную:")
        print("pip install python-telegram-bot[job-queue] telethon requests aiosqlite")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()