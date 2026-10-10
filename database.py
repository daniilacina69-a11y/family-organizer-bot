import aiosqlite

DB_NAME = "family_bot.db"


async def init_db():
    """Создаем таблицы в базе данных при запуске бота"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                category TEXT NOT NULL,
                is_bought INTEGER DEFAULT 0
            )
        """)
        # Таблица заметок с поддержкой времени напоминания
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_text TEXT NOT NULL,
                remind_time TEXT DEFAULT NULL,
                user_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                congratulated INTEGER DEFAULT 0
            )
        """)
        await db.commit()

        default_cats = ["🥦 Продукты", "🧼 Бытовая химия"]
        for cat in default_cats:
            await db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        await db.commit()


async def get_all_categories():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM categories") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def add_category(cat_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat_name,))
        await db.commit()


async def delete_category(cat_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM categories WHERE name = ?", (cat_name,))
        await db.execute("DELETE FROM shopping WHERE category = ?", (cat_name,))
        await db.commit()


async def add_shopping_item(item: str, category: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO shopping (item, category, is_bought) VALUES (?, ?, 0)", (item, category))
        await db.commit()


async def get_shopping_list_by_category(category: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, item, is_bought FROM shopping WHERE category = ?", (category,)) as cursor:
            return await cursor.fetchall()


async def toggle_shopping_item(item_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT is_bought FROM shopping WHERE id = ?", (item_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_status = 0 if row[0] == 1 else 1
                await db.execute("UPDATE shopping SET is_bought = ? WHERE id = ?", (new_status, item_id))
                await db.commit()


async def delete_shopping_item(item_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM shopping WHERE id = ?", (item_id,))
        await db.commit()


async def clear_category_items(category: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM shopping WHERE category = ?", (category,))
        await db.commit()


# --- Функции для заметок ---
async def add_note(note_text: str, user_id: int, remind_time: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO notes (note_text, remind_time, user_id) VALUES (?, ?, ?)",
                         (note_text, remind_time, user_id))
        await db.commit()


async def get_notes():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, note_text, remind_time FROM notes") as cursor:
            return await cursor.fetchall()


async def delete_note(note_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()


async def check_congratulated(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT congratulated FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, congratulated) VALUES (?, 0)", (user_id,))
                await db.commit()
                return False
            return bool(row[0])


async def set_congratulated(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET congratulated = 1 WHERE user_id = ?", (user_id,))
        await db.commit()