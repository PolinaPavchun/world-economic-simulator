import sqlite3    # база данных в виде файла, без отдельного сервера
import threading  # каждый поток Flask получает своё соединение с БД
import json       # сериализация состояния игры в строку и обратно
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_BASE, "users.sqlite")

# у каждого потока своя переменная conn — SQLite не потокобезопасен
_local = threading.local()


def get_db():
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect(DB_FILE)
        cursor = _local.conn.cursor()
        # IF NOT EXISTS — безопасно вызывать при каждом запуске
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE,
            password_hash TEXT
        )
        """)
        # одно сохранение на пользователя, связано с таблицей users
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        # ? защищают от SQL-инъекций
        cursor.execute(
            "INSERT INTO users (nickname, password_hash) VALUES (?, ?)",
            (nickname, password_hash)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # UNIQUE нарушен — ник уже занят
        return False


def check_user(nickname, password_hash):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE nickname=? AND password_hash=?",
        (nickname, password_hash)
    )
    return cursor.fetchone() is not None


def nickname_exists(nickname):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE nickname=?", (nickname,))
    return cursor.fetchone() is not None


def save_game_state(nickname, game_state_dict):
    conn = get_db()
    cursor = conn.cursor()
    # INSERT OR REPLACE — перезаписывает если запись уже есть
    cursor.execute(
        "INSERT OR REPLACE INTO game_states (nickname, state_json) VALUES (?, ?)",
        (nickname, json.dumps(game_state_dict, ensure_ascii=False))
    )
    conn.commit()


def load_game_state(nickname):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT state_json FROM game_states WHERE nickname=?", (nickname,))
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return None
