import { useState } from "react";
import "./App.css";

function App() {
  // здесь храним никнейм
  const [nickname, setNickname] = useState("");

  // здесь пароль
  const [password, setPassword] = useState("");

  // сюда будем выводить ответ сервера
  const [message, setMessage] = useState("");

  // регистрация
  const handleRegister = async () => {
    if (!nickname || !password) {
      setMessage("Введите никнейм и пароль");
      return;
    }

    try {
      const response = await fetch("http://127.0.0.1:5000/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ nickname, password })
      });

      const data = await response.json();
      setMessage(data.message || data.error);
    } catch {
      setMessage("Ошибка соединения с сервером");
    }
  };

  // вход
  const handleLogin = async () => {
    if (!nickname || !password) {
      setMessage("Введите никнейм и пароль");
      return;
    }

    try {
      const response = await fetch("http://127.0.0.1:5000/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ nickname, password })
      });

      const data = await response.json();
      setMessage(data.message || data.error);
    } catch {
      setMessage("Ошибка соединения с сервером");
    }
  };

  return (
    <div className="App">
      <h1>Игра</h1>

      <input
        type="text"
        placeholder="Никнейм"
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
      />

      <input
        type="password"
        placeholder="Пароль"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />

      <div>
        <button onClick={handleRegister}>Регистрация</button>
        <button onClick={handleLogin}>Вход</button>
      </div>

      {message && <p>{message}</p>}
    </div>
  );
}

export default App;