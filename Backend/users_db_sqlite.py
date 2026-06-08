# users_db_sqlite.py — работа с базой данных SQLite.
# Хранит пользователей и сохранения игр, предоставляет функции для регистрации, входа и сохранения.

import sqlite3    # база данных в виде файла, без отдельного сервера
import threading  # каждый поток Flask получает своё соединение
import json       # сериализация состояния игры в строку
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_BASE, "users.sqlite")

_local = threading.local()


def get_db():
    # Возвращает соединение с базой для текущего потока, при первом обращении создаёт таблицы.
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
    # Добавляет нового пользователя, возвращает False если никнейм уже занят.
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
    # Проверяет что никнейм и хеш пароля совпадают в базе, возвращает True или False.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE nickname=? AND password_hash=?",
        (nickname, password_hash)
    )
    return cursor.fetchone() is not None


def nickname_exists(nickname):
    # Возвращает True если никнейм уже зарегистрирован в базе.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE nickname=?", (nickname,))
    return cursor.fetchone() is not None


def save_game_state(nickname, game_state_dict):
    # Сохраняет состояние игры как JSON, перезаписывает предыдущее сохранение.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO game_states (nickname, state_json) VALUES (?, ?)",
        (nickname, json.dumps(game_state_dict, ensure_ascii=False))
    )
    conn.commit()


def load_game_state(nickname):
    # Возвращает состояние игры из базы или None если игры для этого пользователя ещё нет.
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT state_json FROM game_states WHERE nickname=?", (nickname,))
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return None
