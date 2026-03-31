from flask import Flask, request, jsonify
from users_db_sqlite import add_user, check_user, nickname_exists
import hashlib

app = Flask(__name__)

def hash_password(password):
    """Создаём хэш пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

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
        return jsonify({"message": "Вход успешен"}), 200
    else:
        return jsonify({"error": "Неверный никнейм или пароль"}), 400

if __name__ == "__main__":
    # Запускаем сервер, включаем режим отладки
    app.run(debug=True)