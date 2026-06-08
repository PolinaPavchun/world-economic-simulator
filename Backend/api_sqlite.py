# api_sqlite.py — Flask-сервер, точка входа для всех запросов с фронтенда.
# Обрабатывает регистрацию, вход, атаки, ежедневные обновления и квиз.

from flask import Flask, request, jsonify  # веб-фреймворк для создания API-маршрутов
from users_db_sqlite import add_user, check_user, nickname_exists, save_game_state, load_game_state  # работа с базой
import hashlib   # хеширование паролей
import os        # чтение переменных окружения и путей к файлам
from flask_cors import CORS  # разрешает запросы с фронтенда на другом домене
from game_core import GlobalEconomyGame as Game  # основная логика игры

app = Flask(__name__)
CORS(app)

_BASE = os.path.dirname(os.path.abspath(__file__))
BALANCE_FILE = os.path.join(_BASE, "balance.json")

active_games = {}  # игры в памяти — не читаем базу при каждом запросе


def hash_password(password):
    # Хеширует пароль через SHA-256 — необратимо, пароли в базе не хранятся в открытом виде.
    return hashlib.sha256(password.encode()).hexdigest()


def get_or_create_game(nickname):
    # Возвращает игру из памяти, иначе загружает из базы, иначе создаёт новую — в таком порядке.
    if nickname in active_games:
        return active_games[nickname]
    saved = load_game_state(nickname)
    game = Game.from_dict(saved) if saved else Game(BALANCE_FILE)
    active_games[nickname] = game
    return game


@app.route("/register", methods=["POST"])
def register():
    # Создаёт нового пользователя и сразу заводит для него свежую игру с начальными параметрами.
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")
    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400
    if nickname_exists(nickname):
        return jsonify({"error": "Никнейм уже занят"}), 400
    if add_user(nickname, hash_password(password)):
        new_game = Game(BALANCE_FILE)
        save_game_state(nickname, new_game.to_dict())
        return jsonify({"message": "Регистрация успешна"}), 201
    return jsonify({"error": "Не удалось зарегистрироваться"}), 500


@app.route("/login", methods=["POST"])
def login():
    # Проверяет пароль и подгружает игру в память, чтобы следующие запросы были быстрее.
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")
    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400
    if check_user(nickname, hash_password(password)):
        get_or_create_game(nickname)
        return jsonify({"message": "Вход успешен", "nickname": nickname}), 200
    return jsonify({"error": "Неверный никнейм или пароль"}), 400


@app.route("/game/state", methods=["GET"])
def game_state():
    # Возвращает текущее состояние игры для указанного пользователя.
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    return jsonify(game.get_state())


@app.route("/game/attack", methods=["POST"])
def game_attack():
    # Принимает атаку, применяет её к игре, сохраняет в базу и возвращает обновлённое состояние.
    data = request.json
    nickname = data.get("nickname")
    attack_name = data.get("attack_name")
    target_name = data.get("target_name")
    if not nickname or not attack_name or not target_name:
        return jsonify({"error": "Missing fields"}), 400
    game = get_or_create_game(nickname)
    success, message, details = game.apply_attack(attack_name, target_name)
    save_game_state(nickname, game.to_dict())
    return jsonify({"success": success, "message": message, "state": game.get_state(), "details": details})


@app.route("/game/daily", methods=["POST"])
def game_daily():
    # Продвигает игру на один день — вызывается фронтендом каждые 10 секунд.
    nickname = request.json.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    game.daily_update()
    save_game_state(nickname, game.to_dict())
    return jsonify(game.get_state())


@app.route("/game/quiz", methods=["GET"])
def get_quiz():
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    return jsonify(game.get_quiz_question())


@app.route("/game/quiz/answer", methods=["POST"])
def answer_quiz():
    data = request.json
    nickname = data.get("nickname")
    answer = data.get("answer", "")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    result = game.submit_quiz_answer(answer)
    result['ip'] = game.ip  # актуальный баланс для обновления шапки
    save_game_state(nickname, game.to_dict())
    return jsonify(result)


@app.route("/reset_game", methods=["POST"])
def reset_game():
    # Удаляет текущую игру из базы и создаёт новую с начальными параметрами из balance.json.
    data = request.json
    nickname = data.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    from users_db_sqlite import get_db
    conn = get_db()
    conn.cursor().execute("DELETE FROM game_states WHERE nickname = ?", (nickname,))
    conn.commit()
    new_game = Game(BALANCE_FILE)
    save_game_state(nickname, new_game.to_dict())
    active_games[nickname] = new_game
    return jsonify({"message": "Игра сброшена", "state": new_game.get_state()}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    app.run(debug=False, host="0.0.0.0", port=port)
