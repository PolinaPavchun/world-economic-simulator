from flask import Flask, request, jsonify
from users_db_sqlite import add_user, check_user, nickname_exists, save_game_state, load_game_state
import hashlib
from flask_cors import CORS
from game_core import Game

app = Flask(__name__)
CORS(app)

# Кеш активных игр, чтобы не пересоздавать объект при каждом запросе
active_games = {}

def hash_password(password):
    """Создаём хэш пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_or_create_game(nickname):
    """Возвращаем объект Game для пользователя (из кеша или из БД)"""
    if nickname in active_games:
        return active_games[nickname]
    
    saved = load_game_state(nickname)
    if saved:
        game = Game.from_dict(saved)
    else:
        game = Game("balance.json")
    active_games[nickname] = game
    return game

@app.route("/register", methods=["POST"])
def register():
    """Регистрация нового пользователя"""
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")

    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400

    if nickname_exists(nickname):
        return jsonify({"error": "Никнейм уже занят"}), 400

    if add_user(nickname, hash_password(password)):
        # Сразу создаём новую игру и сохраняем
        new_game = Game("balance.json")
        save_game_state(nickname, new_game.to_dict())
        return jsonify({"message": "Регистрация успешна"}), 201
    else:
        return jsonify({"error": "Не удалось зарегистрироваться"}), 500

@app.route("/login", methods=["POST"])
def login():
    """Авторизация пользователя"""
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")

    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400

    if check_user(nickname, hash_password(password)):
        # Загружаем игру в кеш
        get_or_create_game(nickname)
        return jsonify({"message": "Вход успешен", "nickname": nickname}), 200
    else:
        return jsonify({"error": "Неверный никнейм или пароль"}), 400

@app.route("/game/state", methods=["GET"])
def game_state():
    """Возвращает текущее состояние игры для пользователя"""
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    return jsonify(game.get_state())

@app.route("/game/attack", methods=["POST"])
def game_attack():
    """Обрабатывает атаку на страну"""
    data = request.json
    nickname = data.get("nickname")
    attack_name = data.get("attack_name")
    target_name = data.get("target_name")
    if not nickname or not attack_name or not target_name:
        return jsonify({"error": "Missing fields"}), 400
    game = get_or_create_game(nickname)
    success, message = game.apply_attack(attack_name, target_name)
    state = game.get_state()
    save_game_state(nickname, game.to_dict())
    return jsonify({"success": success, "message": message, "state": state})

@app.route("/game/daily", methods=["POST"])
def game_daily():
    """Выполняет ежедневное обновление игры"""
    nickname = request.json.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    game.daily_update()
    state = game.get_state()
    save_game_state(nickname, game.to_dict())
    return jsonify(state)

if __name__ == "__main__":
    # Запускаем сервер
    app.run(debug=True, port=5003)