import sqlite3

DB_FILE = "users.sqlite"

# Подключаемся к базе, файл создаётся автоматически, если его нет
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Создаём таблицу пользователей, если её ещё нет
cursor.execute("""
-- Таблица для пользователей
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- уникальный идентификатор
    nickname TEXT UNIQUE,                  -- никнейм, не может повторяться
    password_hash TEXT                     -- хэш пароля
)
""")
conn.commit()

def add_user(nickname, password_hash):
    # Добавляем нового пользователя, если никнейм свободен
    try:
        cursor.execute(
            "INSERT INTO users (nickname, password_hash) VALUES (?, ?)",
            (nickname, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Никнейм уже занят
        return False

def check_user(nickname, password_hash):
    # Проверяем, есть ли пользователь с таким никнеймом и паролем
    cursor.execute(
        "SELECT * FROM users WHERE nickname=? AND password_hash=?",
        (nickname, password_hash)
    )
    return cursor.fetchone() is not None

def nickname_exists(nickname):
    # Проверяем, существует ли такой никнейм
    cursor.execute("SELECT * FROM users WHERE nickname=?", (nickname,))
    return cursor.fetchone() is not None