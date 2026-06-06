# =============================================================================
# api_sqlite.py — HTTP-сервер (бэкенд) World Economic Simulator
#
# Этот файл запускает веб-сервер на Flask. Он принимает HTTP-запросы от
# фронтенда (браузера) и отвечает JSON-данными: состояние игры, результаты
# атак, вопросы квиза и т.д.
# =============================================================================

from flask import Flask, request, jsonify  # Flask — веб-фреймворк; request — данные входящего запроса; jsonify — превращает dict в JSON-ответ
from users_db_sqlite import add_user, check_user, nickname_exists, save_game_state, load_game_state  # наши функции для работы с базой данных
import hashlib     # стандартный модуль Python для криптографических хеш-функций (SHA-256)
import os          # для чтения переменных окружения — например, PORT на сервере Railway
from flask_cors import CORS  # CORS (Cross-Origin Resource Sharing) — разрешает браузеру отправлять запросы на другой домен/порт
from game_core import GlobalEconomyGame as Game  # импортируем главный класс игры под псевдонимом Game

# Flask(__name__) создаёт приложение; __name__ — имя текущего модуля, Flask использует его, чтобы найти папку с файлами
app = Flask(__name__)

# CORS(app) разрешает запросы со ВСЕХ доменов (нужно, потому что фронтенд на Vercel, а сервер на Railway — разные домены)
CORS(app)

# os.path.abspath(__file__) — полный путь к этому файлу; dirname берёт только папку
_BASE = os.path.dirname(os.path.abspath(__file__))
# Полный путь к файлу balance.json с данными стран и атак
BALANCE_FILE = os.path.join(_BASE, "balance.json")

# Словарь активных игр в памяти сервера: ключ — никнейм, значение — объект Game
# Хранение в памяти ускоряет работу: не нужно каждый раз читать из базы данных
active_games = {}


def hash_password(password):
    """Превращает пароль в SHA-256 хеш — строку из 64 шестнадцатеричных символов.
    Хеш необратим: из него нельзя восстановить исходный пароль."""
    # password.encode() — переводит строку в байты (SHA-256 работает с байтами)
    # hashlib.sha256(...).hexdigest() — считает хеш и возвращает его как строку из букв/цифр
    return hashlib.sha256(password.encode()).hexdigest()


def get_or_create_game(nickname):
    """Возвращает объект игры для игрока. Сначала ищет в памяти, затем в базе, иначе создаёт новую."""
    if nickname in active_games:
        # Игра уже загружена в память — просто возвращаем её (быстро)
        return active_games[nickname]

    # Пытаемся загрузить сохранённое состояние из SQLite
    saved = load_game_state(nickname)
    if saved:
        # from_dict восстанавливает объект Game из словаря (сохранённых данных)
        game = Game.from_dict(saved)
    else:
        # Сохранения нет — создаём новую игру, загружая данные из balance.json
        game = Game(BALANCE_FILE)

    # Кешируем в памяти, чтобы следующий запрос не лез в базу
    active_games[nickname] = game
    return game


# @app.route — декоратор Flask, который "привязывает" функцию к конкретному URL и методу HTTP
# POST означает, что клиент отправляет данные (тело запроса); GET — только получает
@app.route("/register", methods=["POST"])
def register():
    """Регистрирует нового игрока: проверяет данные, хеширует пароль, создаёт запись в БД и первую игру."""
    data = request.json         # читаем JSON из тела запроса — это словарь с nickname и password
    nickname = data.get("nickname")  # data.get возвращает значение по ключу или None, если ключа нет
    password = data.get("password")

    # Проверка входных данных: оба поля обязательны
    if not nickname or not password:
        # jsonify({...}) — создаёт HTTP-ответ с JSON-телом; второй аргумент — HTTP-код состояния
        # 400 Bad Request — клиент прислал неверные данные
        return jsonify({"error": "Введите никнейм и пароль"}), 400

    # Проверяем уникальность ника (функция из users_db_sqlite.py)
    if nickname_exists(nickname):
        return jsonify({"error": "Никнейм уже занят"}), 400

    # add_user возвращает True при успехе; пароль передаём уже хешированным
    if add_user(nickname, hash_password(password)):
        # Сразу создаём начальное состояние игры для нового пользователя
        new_game = Game(BALANCE_FILE)
        # to_dict() сериализует объект Game в словарь для сохранения в базу
        save_game_state(nickname, new_game.to_dict())
        # 201 Created — стандартный код для успешного создания ресурса
        return jsonify({"message": "Регистрация успешна"}), 201
    else:
        # 500 Internal Server Error — что-то пошло не так на стороне сервера
        return jsonify({"error": "Не удалось зарегистрироваться"}), 500


@app.route("/login", methods=["POST"])
def login():
    """Проверяет логин и пароль. При успехе — загружает игру в память и возвращает никнейм."""
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")

    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400

    # check_user ищет в базе запись с таким ником И хешем пароля
    if check_user(nickname, hash_password(password)):
        # Загружаем (или создаём) игровой объект заранее — чтобы первый запрос состояния был быстрым
        get_or_create_game(nickname)
        # 200 OK — стандартный успешный ответ
        return jsonify({"message": "Вход успешен", "nickname": nickname}), 200
    else:
        # 400 (а не 401) — так сложилось исторически в этом проекте
        return jsonify({"error": "Неверный никнейм или пароль"}), 400


@app.route("/game/state", methods=["GET"])
def game_state():
    """Возвращает текущее состояние игры: здоровье стран, IP, раскрытие, атаки и т.д."""
    # GET-параметры читаются через request.args (они передаются в URL: /game/state?nickname=...)
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    # get_state() возвращает словарь со всеми данными для интерфейса
    return jsonify(game.get_state())


@app.route("/game/attack", methods=["POST"])
def game_attack():
    """Выполняет атаку: применяет урон к целевой стране, распространяет кризис и сохраняет состояние."""
    data = request.json
    nickname = data.get("nickname")
    attack_name = data.get("attack_name")   # название атаки, например "Валютная атака"
    target_name = data.get("target_name")   # название страны-цели, например "Германия"

    if not nickname or not attack_name or not target_name:
        return jsonify({"error": "Missing fields"}), 400

    game = get_or_create_game(nickname)
    # apply_attack возвращает тройку: (успех: bool, сообщение: str, детали: dict)
    success, message, details = game.apply_attack(attack_name, target_name)
    state = game.get_state()

    # Сохраняем изменённое состояние в базу после каждой атаки — прогресс не потеряется
    save_game_state(nickname, game.to_dict())

    # Отдаём клиенту всё необходимое: успех, текст, новое состояние, детали удара
    return jsonify({"success": success, "message": message, "state": state, "details": details})


@app.route("/game/daily", methods=["POST"])
def game_daily():
    """Тик игрового дня: восстановление, деградация, случайные события. Вызывается фронтендом каждые 10 секунд."""
    nickname = request.json.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    # daily_update() — один шаг симуляции: меняет здоровье стран, IP, раскрытие
    game.daily_update()
    state = game.get_state()
    save_game_state(nickname, game.to_dict())  # сохраняем после каждого тика
    return jsonify(state)


@app.route("/game/quiz", methods=["GET"])
def get_quiz():
    """Возвращает очередной вопрос экономического квиза. Лимит — 3 вопроса на каждые 4 игровых дня."""
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    # get_quiz_question() либо выбирает вопрос из пула, либо возвращает ошибку о лимите
    q = game.get_quiz_question()
    return jsonify(q)


@app.route("/game/quiz/answer", methods=["POST"])
def answer_quiz():
    """Принимает ответ на вопрос квиза. При правильном ответе начисляет IP и снижает раскрытие."""
    data = request.json
    nickname = data.get("nickname")
    answer = data.get("answer", "")  # вариант ответа, выбранный игроком; "" по умолчанию, если поле не пришло
    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    game = get_or_create_game(nickname)
    # submit_quiz_answer проверяет ответ и возвращает: correct, ip_gained, explanation, remaining
    result = game.submit_quiz_answer(answer)
    result['ip'] = game.ip  # добавляем актуальный баланс IP, чтобы фронтенд мог обновить шапку
    save_game_state(nickname, game.to_dict())
    return jsonify(result)


@app.route("/reset_game", methods=["POST"])
def reset_game():
    """Полностью сбрасывает игру: удаляет сохранение и создаёт новую стартовую позицию."""
    data = request.json
    nickname = data.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    # Импорт функции get_db внутри функции — это допустимо, чтобы не перегружать глобальное пространство
    from users_db_sqlite import get_db
    conn = get_db()
    cursor = conn.cursor()
    # DELETE удаляет строку с состоянием игры; параметр в кортеже защищает от SQL-инъекции
    cursor.execute("DELETE FROM game_states WHERE nickname = ?", (nickname,))
    conn.commit()

    # Создаём совершенно новую игру с начальными данными из balance.json
    new_game = Game(BALANCE_FILE)
    save_game_state(nickname, new_game.to_dict())
    # Обновляем кеш в памяти — старый объект игры больше не нужен
    active_games[nickname] = new_game
    return jsonify({"message": "Игра сброшена", "state": new_game.get_state()}), 200


# Блок запуска: выполняется только если этот файл запущен напрямую (python api_sqlite.py)
# При импорте модуля (например, при тестировании) этот блок НЕ выполняется
if __name__ == "__main__":
    # os.environ.get("PORT", 5003) — берём порт из переменной окружения (Railway задаёт PORT автоматически)
    # Если переменной нет — используем 5003 для локальной разработки
    port = int(os.environ.get("PORT", 5003))
    # debug=False — обязательно в продакшне; debug=True открывает уязвимости
    # host="0.0.0.0" — слушаем на ВСЕХ сетевых интерфейсах (нужно для Railway и Docker)
    app.run(debug=False, host="0.0.0.0", port=port)
