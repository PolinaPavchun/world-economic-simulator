from flask import Flask, request, jsonify
from users_db_sqlite import add_user, check_user, nickname_exists, save_game_state, load_game_state
import hashlib
import os
from flask_cors import CORS
from game_core import GlobalEconomyGame as Game

app = Flask(__name__)
CORS(app)

_BASE = os.path.dirname(os.path.abspath(__file__))
BALANCE_FILE = os.path.join(_BASE, "balance.json")

active_games = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_or_create_game(nickname):
    if nickname in active_games:
        return active_games[nickname]
    saved = load_game_state(nickname)
    if saved:
        game = Game.from_dict(saved)
    else:
        game = Game(BALANCE_FILE)
    active_games[nickname] = game
    return game

@app.route("/register", methods=["POST"])
def register():
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
    else:
        return jsonify({"error": "Не удалось зарегистрироваться"}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    nickname = data.get("nickname")
    password = data.get("password")
    if not nickname or not password:
        return jsonify({"error": "Введите никнейм и пароль"}), 400
    if check_user(nickname, hash_password(password)):
        get_or_create_game(nickname)
        return jsonify({"message": "Вход успешен", "nickname": nickname}), 200
    else:
        return jsonify({"error": "Неверный никнейм или пароль"}), 400

@app.route("/game/state", methods=["GET"])
def game_state():
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    return jsonify(game.get_state())

@app.route("/game/attack", methods=["POST"])
def game_attack():
    data = request.json
    nickname = data.get("nickname")
    attack_name = data.get("attack_name")
    target_name = data.get("target_name")
    if not nickname or not attack_name or not target_name:
        return jsonify({"error": "Missing fields"}), 400
    game = get_or_create_game(nickname)
    success, message, details = game.apply_attack(attack_name, target_name)
    state = game.get_state()
    save_game_state(nickname, game.to_dict())
    return jsonify({"success": success, "message": message, "state": state, "details": details})

@app.route("/game/daily", methods=["POST"])
def game_daily():
    nickname = request.json.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    game.daily_update()
    state = game.get_state()
    save_game_state(nickname, game.to_dict())
    return jsonify(state)

@app.route("/game/quiz", methods=["GET"])
def get_quiz():
    nickname = request.args.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    q = game.get_quiz_question()
    return jsonify(q)

@app.route("/game/quiz/answer", methods=["POST"])
def answer_quiz():
    data = request.json
    nickname = data.get("nickname")
    answer = data.get("answer", "")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    game = get_or_create_game(nickname)
    result = game.submit_quiz_answer(answer)
    result['ip'] = game.ip
    save_game_state(nickname, game.to_dict())
    return jsonify(result)

@app.route("/reset_game", methods=["POST"])
def reset_game():
    data = request.json
    nickname = data.get("nickname")
    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    from users_db_sqlite import get_db
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM game_states WHERE nickname = ?", (nickname,))
    conn.commit()
    new_game = Game(BALANCE_FILE)
    save_game_state(nickname, new_game.to_dict())
    active_games[nickname] = new_game
    return jsonify({"message": "Игра сброшена", "state": new_game.get_state()}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    app.run(debug=False, host="0.0.0.0", port=port)