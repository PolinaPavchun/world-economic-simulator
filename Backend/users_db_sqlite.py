import sqlite3
import threading
import json

DB_FILE = "users.sqlite"
_local = threading.local()

def get_db():
    """Получаем соединение с БД для текущего потока"""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(DB_FILE)
        cursor = _local.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE,
            password_hash TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_states (
            nickname TEXT PRIMARY KEY,
            state_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(nickname) REFERENCES users(nickname)
        )
        """)
        _local.conn.commit()
    return _local.conn

def add_user(nickname, password_hash):
    """Добавляем нового пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (nickname, password_hash) VALUES (?, ?)",
            (nickname, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def check_user(nickname, password_hash):
    """Проверяем пользователя при входе"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE nickname=? AND password_hash=?",
        (nickname, password_hash)
    )
    return cursor.fetchone() is not None

def nickname_exists(nickname):
    """Проверяем, занят ли никнейм"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE nickname=?", (nickname,))
    return cursor.fetchone() is not None

def save_game_state(nickname, game_state_dict):
    """Сохраняем состояние игры в БД"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO game_states (nickname, state_json) VALUES (?, ?)",
        (nickname, json.dumps(game_state_dict, ensure_ascii=False))
    )
    conn.commit()

def load_game_state(nickname):
    """Загружаем состояние игры из БД, если есть"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT state_json FROM game_states WHERE nickname=?", (nickname,))
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return None