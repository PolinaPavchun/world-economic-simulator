import sqlite3    # встроенный модуль Python для работы с базой данных SQLite (файл на диске, не нужен отдельный сервер)
import threading  # позволяет безопасно работать в нескольких потоках одновременно — Flask обрабатывает запросы параллельно
import json       # нужен для превращения словаря Python (состояние игры) в строку и обратно — чтобы сохранить в базу
import os         # модуль для работы с файловой системой: узнать путь к файлу, склеить пути

# os.path.abspath(__file__) — абсолютный путь к ЭТОМУ файлу
# os.path.dirname(...)       — берёт только папку из этого пути (убирает имя файла)
_BASE = os.path.dirname(os.path.abspath(__file__))

# os.path.join соединяет путь к папке и имя файла в правильный путь под любой ОС
# Итог: путь к файлу базы данных рядом с этим скриптом
DB_FILE = os.path.join(_BASE, "users.sqlite")

# threading.local() создаёт "локальную переменную потока": у каждого потока сервера будет своё отдельное соединение с БД
# Это нужно, потому что одно SQLite-соединение нельзя использовать из нескольких потоков одновременно
_local = threading.local()


def get_db():
    """Возвращает соединение с базой данных для текущего потока.
    При первом вызове создаёт таблицы, если их ещё нет."""

    # hasattr проверяет, есть ли уже соединение у этого потока
    # Если нет — создаём новое (каждый поток делает это один раз)
    if not hasattr(_local, 'conn'):
        # sqlite3.connect открывает (или создаёт) файл базы данных
        _local.conn = sqlite3.connect(DB_FILE)
        cursor = _local.conn.cursor()  # cursor — объект для выполнения SQL-запросов

        # CREATE TABLE IF NOT EXISTS — создать таблицу только если она ещё не существует (безопасно запускать повторно)
        # INTEGER PRIMARY KEY AUTOINCREMENT — числовой ID, растёт автоматически при каждой новой записи
        # TEXT UNIQUE — строка, которая должна быть уникальной (два пользователя с одним ником — ошибка)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE,
            password_hash TEXT
        )
        """)

        # game_states хранит сохранения игры: у каждого игрока (nickname) ровно одно состояние
        # FOREIGN KEY(nickname) REFERENCES users(nickname) — связь с таблицей users: нельзя сохранить игру для несуществующего пользователя
        # DEFAULT CURRENT_TIMESTAMP — дата обновления проставляется автоматически при добавлении записи
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_states (
            nickname TEXT PRIMARY KEY,
            state_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(nickname) REFERENCES users(nickname)
        )
        """)

        # commit() — сохраняет изменения в файл; без него они существуют только в памяти
        _local.conn.commit()

    return _local.conn  # возвращаем соединение (только что созданное или уже существующее)


def add_user(nickname, password_hash):
    """Добавляет нового пользователя в базу. Возвращает True при успехе, False если ник уже занят."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        # ? — плейсхолдеры для параметров: защищают от SQL-инъекций (нельзя вставить вредоносный SQL через поле ввода)
        cursor.execute(
            "INSERT INTO users (nickname, password_hash) VALUES (?, ?)",
            (nickname, password_hash)
        )
        conn.commit()  # сохраняем нового пользователя в файл
        return True
    except sqlite3.IntegrityError:
        # IntegrityError возникает, когда нарушено ограничение UNIQUE — ник уже занят
        return False


def check_user(nickname, password_hash):
    """Проверяет логин: ищет запись с таким ником И хешем пароля. Возвращает True если совпадение найдено."""
    conn = get_db()
    cursor = conn.cursor()
    # Ищем строку, где оба поля совпадают — так проверяется и ник, и правильность пароля
    cursor.execute(
        "SELECT * FROM users WHERE nickname=? AND password_hash=?",
        (nickname, password_hash)
    )
    # fetchone() возвращает первую найденную строку или None, если ничего нет
    # "is not None" превращает это в True/False — функция возвращает булево значение
    return cursor.fetchone() is not None


def nickname_exists(nickname):
    """Проверяет, занят ли никнейм. Используется при регистрации, чтобы не допустить дублей."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE nickname=?", (nickname,))
    # (nickname,) — кортеж с одним элементом; запятая обязательна, иначе Python воспримет скобки как просто скобки
    return cursor.fetchone() is not None


def save_game_state(nickname, game_state_dict):
    """Сохраняет состояние игры в базу данных. Если запись уже есть — перезаписывает её (INSERT OR REPLACE)."""
    conn = get_db()
    cursor = conn.cursor()
    # INSERT OR REPLACE: если запись с таким nickname уже существует — заменяет её, иначе создаёт новую
    # json.dumps превращает Python-словарь в строку JSON, ensure_ascii=False — чтобы кириллица не кодировалась в \uXXXX
    cursor.execute(
        "INSERT OR REPLACE INTO game_states (nickname, state_json) VALUES (?, ?)",
        (nickname, json.dumps(game_state_dict, ensure_ascii=False))
    )
    conn.commit()


def load_game_state(nickname):
    """Загружает сохранённое состояние игры из базы. Возвращает словарь или None, если сохранения нет."""
    conn = get_db()
    cursor = conn.cursor()
    # SELECT конкретного поля state_json — не тянем лишние данные
    cursor.execute("SELECT state_json FROM game_states WHERE nickname=?", (nickname,))
    row = cursor.fetchone()  # одна строка таблицы или None
    if row:
        # row[0] — первый (и единственный) столбец из SELECT: строка JSON
        # json.loads превращает строку JSON обратно в словарь Python
        return json.loads(row[0])
    return None  # у игрока ещё нет сохранения — вернём None, сервер создаст новую игру
