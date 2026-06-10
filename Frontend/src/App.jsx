// App.jsx — экран входа и регистрации.
// После успешного входа показывает GamePage.

import React, { useState, useEffect } from "react";
import { API } from "./api";          // адрес бэкенда
import "./App.css";                   // стили экрана входа
import GamePage from "./GamePage";    // игровая страница после входа

async function hashPassword(password) {
  // Хеширует пароль через SHA-256 прямо в браузере, чтобы не отправлять его в открытом виде.
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

function App() {
  // Хранит данные формы и состояние сессии.
  const [nickname, setNickname] = useState(() => localStorage.getItem("wes_nickname") || "");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [showTutorial, setShowTutorial] = useState(false);

  // При загрузке страницы восстанавливаем сессию по сохранённому никнейму.
  useEffect(() => {
    const saved = localStorage.getItem("wes_nickname");
    if (!saved) return;
    fetch(`${API}/game/state?nickname=${encodeURIComponent(saved)}`)
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data?.ip !== undefined) setLoggedIn(true); })
      .catch(() => {});
  }, []);

  const handleRegister = async () => {
    // Отправляет никнейм и хэш пароля на сервер для создания аккаунта.
    const hashed = await hashPassword(password);
    try {
      const response = await fetch(`${API}/register`, {
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
    } catch {
      setMessage("Сервер недоступен");
    }
  };

  const handleLogin = async () => {
    // Проверяет учётные данные и открывает игру при успехе.
    const hashed = await hashPassword(password);
    try {
      const response = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password: hashed })
      });
      const data = await response.json();
      if (response.ok) {
        localStorage.setItem("wes_nickname", nickname);
        setLoggedIn(true);
        setShowTutorial(true);
        setMessage("");
      } else {
        setMessage(data.error);
      }
    } catch {
      setMessage("Сервер недоступен");
    }
  };

  const handleSubmit = (e) => {
    // Обрабатывает отправку формы — вход или регистрация в зависимости от режима.
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

              <div className="briefing-classified">Совершенно секретно. Только для агентов.</div>

              <div className="briefing-divider" />

              <div className="briefing-blocks">
                <div className="briefing-block">
                  <div className="bb-title">Цель</div>
                  <div className="bb-text">Обрушить среднее экономическое здоровье 16 стран ниже 30%. Следи за глобальным индексом в шапке, это твой ориентир.</div>
                </div>
                <div className="briefing-block">
                  <div className="bb-title">Как действовать</div>
                  <div className="bb-text">Выбери страну на карте. Открой Арсенал и выбери атаку под её слабость: высокий долг, энергозависимость, социальное напряжение. Читай объяснения после удара, каждая атака основана на реальном экономическом механизме.</div>
                </div>
                <div className="briefing-block">
                  <div className="bb-title">Очки влияния (IP)</div>
                  <div className="bb-text">Тратишь на атаки, получаешь обратно за успех. Кнопка «Разведка»: ответь на вопрос про экономику, заработай IP и снизь раскрытие.</div>
                </div>
                <div className="briefing-block">
                  <div className="bb-title">Кризис не останавливается</div>
                  <div className="bb-text">Удар по одной стране расходится волной на её торговых партнёров, кредиторов и союзников. Иногда один удар задевает пятерых.</div>
                </div>
                <div className="briefing-block briefing-block-danger">
                  <div className="bb-title">Опасность: раскрытие</div>
                  <div className="bb-text">Провалы и неточные атаки оставляют следы. Если раскрытие дойдёт до 100%, операция провалена. Жди, отвечай на вопросы, выбирай цели точнее.</div>
                </div>
              </div>

              <button className="tutorial-button" onClick={closeTutorial}>
                Начать операцию
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
          <button
            type="submit"
            className="auth-button"
            onClick={(e) => { e.preventDefault(); handleSubmit(e); }}
          >
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
