import React, { useState } from "react";

function App() {
  // Никнейм и пароль, которые вводит пользователь
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");

  // Показываем пользователю сообщения об успехе или ошибке
  const [message, setMessage] = useState("");

  // Статус входа пользователя
  const [loggedIn, setLoggedIn] = useState(false);

  // Отправка данных для регистрации
  const handleRegister = async () => {
    try {
      const response = await fetch("http://localhost:5000/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password }),
      });

      const data = await response.json();

      if (response.ok) {
        // Пользователь зарегистрирован
        setMessage(data.message);
      } else {
        // Ник занят или другая ошибка
        setMessage(data.error);
      }
    } catch (error) {
      setMessage("Сервер недоступен");
    }
  };

  // Отправка данных для входа
  const handleLogin = async () => {
    try {
      const response = await fetch("http://localhost:5000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password }),
      });

      const data = await response.json();

      if (response.ok) {
        // Пользователь вошёл в игру
        setLoggedIn(true);
        setMessage(data.message);
      } else {
        // Неверный ник или пароль
        setMessage(data.error);
      }
    } catch (error) {
      setMessage("Сервер недоступен");
    }
  };

  // Интерфейс сайта
  return (
    <div style={{ padding: "20px", fontFamily: "Arial" }}>
      <h1>Моя игра</h1>

      {!loggedIn ? (
        <div>
          <input
            type="text"
            placeholder="Введите никнейм"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)} // Запоминаем ник
          />
          <br />
          <input
            type="password"
            placeholder="Введите пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)} // Запоминаем пароль
          />
          <br />
          <button onClick={handleRegister}>Зарегистрироваться</button>
          <button onClick={handleLogin}>Войти</button>
        </div>
      ) : (
        <div>
          <h2>Привет, {nickname}!</h2>
          <p>Здесь будет твой баланс и информация по игре</p>
        </div>
      )}

      // Показываем пользователю сообщение
      {message && <p>{message}</p>}
    </div>
  );
}

export default App;