import React, { useState } from "react";
import "./App.css";
import GamePage from "./GamePage";

// Хешируем пароль на клиенте, чтобы не передавать в открытом виде
async function hashPassword(password) {
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

function App() {
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [showTutorial, setShowTutorial] = useState(false);

  const handleRegister = async () => {
    const hashed = await hashPassword(password);
    try {
      const response = await fetch("http://localhost:5003/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password: hashed })
      });
      const data = await response.json();
      if (response.ok) {
        setMessage(data.message);
        setIsLogin(true);
      } else {
        setMessage(data.error);
      }
    } catch (error) {
      setMessage("Сервер недоступен");
    }
  };

  const handleLogin = async () => {
    const hashed = await hashPassword(password);
    try {
      const response = await fetch("http://localhost:5003/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password: hashed })
      });
      const data = await response.json();
      if (response.ok) {
        setLoggedIn(true);
        setShowTutorial(true);
        setMessage("");
      } else {
        setMessage(data.error);
      }
    } catch (error) {
      setMessage("Сервер недоступен");
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isLogin) {
      handleLogin();
    } else {
      handleRegister();
    }
  };

  const closeTutorial = () => setShowTutorial(false);

  if (loggedIn) {
    return (
      <>
        {showTutorial && (
          <div className="tutorial-overlay" onClick={closeTutorial}>
            <div className="tutorial-modal" onClick={(e) => e.stopPropagation()}>
              <button className="tutorial-close" onClick={closeTutorial}>✕</button>
              <div className="tutorial-icon">🌍</div>
              <h2>ГЛОБАЛЬНЫЙ ЭКОНОМИЧЕСКИЙ СИМУЛЯТОР</h2>
              <p className="tutorial-role">Твоя роль: Дестабилизатор мировой экономики</p>
              <div className="tutorial-section">
                <h3>🎯 ЦЕЛЬ</h3>
                <p>Обрушить среднее экономическое здоровье всех стран ниже 30%.</p>
              </div>
              <div className="tutorial-section">
                <h3>⚔️ КАК ИГРАТЬ</h3>
                <ul>
                  <li>Кликай на страны на карте, чтобы выбрать цель</li>
                  <li>Выбирай атаку во вкладке "Арсенал атак"</li>
                  <li>Следи за раскрываемостью — если 100%, ты проиграл</li>
                  <li>Урон от атаки распространяется на торговых партнёров</li>
                  <li>Время идёт автоматически (1 день = 10 секунд)</li>
                </ul>
              </div>
              <button className="tutorial-button" onClick={closeTutorial}>
                НАЧАТЬ ИГРУ
              </button>
            </div>
          </div>
        )}
        <GamePage nickname={nickname} />
      </>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="logo-icon">🌍</div>
          <h1>WORLD ECONOMIC</h1>
          <h2>SIMULATOR</h2>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <div className="input-icon">👤</div>
            <input
              type="text"
              placeholder="Оперативный псевдоним"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              required
            />
          </div>
          <div className="input-group">
            <div className="input-icon">🔒</div>
            <input
              type="password"
              placeholder="Ключ доступа"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="auth-button">
            {isLogin ? "ВОЙТИ В СИСТЕМУ" : "АКТИВИРОВАТЬ АГЕНТА"}
          </button>
          <div className="auth-switch">
            <p>
              {isLogin ? "Нет доступа? " : "Уже есть доступ? "}
              <button
                type="button"
                className="switch-button"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setMessage("");
                }}
              >
                {isLogin ? "Запросить регистрацию" : "Авторизоваться"}
              </button>
            </p>
          </div>
          {message && (
            <div className={`message ${message.includes("успешн") ? "success" : "error"}`}>
              {message}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

export default App;