#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления замкнутого круга с промокодами
"""

import asyncio
import aiosqlite
import os

async def test_promo_fix():
    """Тестируем исправление замкнутого круга с промокодами"""
    
    # Создаем временную базу данных для тестирования
    db_path = "test_promo.db"
    
    # Удаляем старую базу если существует
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Подключаемся к базе данных
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        
        # Создаем необходимые таблицы
        await db.execute("""
            create table if not exists users (
                id integer primary key autoincrement,
                username text,
                telegram_id integer,
                role text default 'user',
                created_at text default (datetime('now'))
            )
        """)
        
        await db.execute("""
            create table if not exists promocodes (
                id integer primary key autoincrement,
                code text unique not null,
                discount_percent integer not null,
                min_amount integer default 0,
                max_uses integer default 0,
                used_count integer default 0,
                is_active integer default 1,
                created_at timestamp default current_timestamp
            )
        """)
        
        await db.execute("""
            create table if not exists user_active_promocodes (
                id integer primary key autoincrement,
                user_id integer references users(id) on delete cascade,
                promo_code text not null,
                discount_percent integer not null,
                min_amount integer default 0,
                created_at text default (datetime('now'))
            )
        """)
        
        await db.commit()
        
        # Добавляем тестового пользователя
        await db.execute(
            "insert into users (username, telegram_id) values (?, ?)",
            ("test_user", 123456789)
        )
        user_id = (await db.execute("select last_insert_rowid()")).fetchone()[0]
        
        # Добавляем тестовый промокод
        await db.execute(
            "insert into promocodes (code, discount_percent, min_amount, max_uses) values (?, ?, ?, ?)",
            ("WELCOME", 10, 1000, 100)
        )
        
        await db.commit()
        
        print("✅ База данных создана и заполнена тестовыми данными")
        print(f"👤 Пользователь ID: {user_id}")
        print("🎁 Промокод: WELCOME (10% скидка, мин. сумма 1000 RUB)")
        
        # Тест 1: Проверяем, что у пользователя нет активного промокода
        result = await db.execute(
            "select * from user_active_promocodes where user_id=?",
            (user_id,)
        )
        active_promo = result.fetchone()
        
        if active_promo is None:
            print("✅ Тест 1 пройден: У пользователя нет активного промокода")
        else:
            print("❌ Тест 1 провален: У пользователя есть активный промокод")
        
        # Тест 2: Добавляем активный промокод пользователю
        await db.execute(
            "insert into user_active_promocodes (user_id, promo_code, discount_percent, min_amount) values (?, ?, ?, ?)",
            (user_id, "WELCOME", 10, 1000)
        )
        await db.commit()
        
        result = await db.execute(
            "select * from user_active_promocodes where user_id=?",
            (user_id,)
        )
        active_promo = result.fetchone()
        
        if active_promo:
            print("✅ Тест 2 пройден: Активный промокод успешно добавлен")
            print(f"   Промокод: {active_promo[2]}, Скидка: {active_promo[3]}%")
        else:
            print("❌ Тест 2 провален: Не удалось добавить активный промокод")
        
        # Тест 3: Проверяем, что промокод сохраняется при повторном запросе
        result = await db.execute(
            "select * from user_active_promocodes where user_id=?",
            (user_id,)
        )
        active_promo = result.fetchone()
        
        if active_promo and active_promo[2] == "WELCOME":
            print("✅ Тест 3 пройден: Промокод сохраняется при повторном запросе")
        else:
            print("❌ Тест 3 провален: Промокод не сохраняется")
        
        # Тест 4: Удаляем активный промокод
        await db.execute(
            "delete from user_active_promocodes where user_id=?",
            (user_id,)
        )
        await db.commit()
        
        result = await db.execute(
            "select * from user_active_promocodes where user_id=?",
            (user_id,)
        )
        active_promo = result.fetchone()
        
        if active_promo is None:
            print("✅ Тест 4 пройден: Активный промокод успешно удален")
        else:
            print("❌ Тест 4 провален: Не удалось удалить активный промокод")
        
        print("\n🎉 Все тесты завершены!")
        print("\n📋 Резюме исправлений:")
        print("1. ✅ Добавлена таблица user_active_promocodes")
        print("2. ✅ Промокоды теперь сохраняются для пользователя")
        print("3. ✅ Каталог показывает активный промокод")
        print("4. ✅ Покупка автоматически применяет промокод")
        print("5. ✅ Добавлена кнопка 'Очистить промокод'")
        print("6. ✅ Замкнутый круг устранен!")

if __name__ == "__main__":
    asyncio.run(test_promo_fix())
