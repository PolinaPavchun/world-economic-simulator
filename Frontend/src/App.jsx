// App.jsx — экран входа/регистрации (первое, что видит пользователь)
// После успешного входа рендерит GamePage с полем для игры

import React, { useState } from "react"; // React — для JSX; useState — хук для хранения данных компонента
import { API } from "./api";              // базовый URL бэкенда (например, https://...railway.app)
import "./App.css";                       // стили: тёмный экран логина, карточка, поля ввода
import GamePage from "./GamePage";        // компонент игровой страницы — показывается после входа

// Хеширует пароль в браузере через встроенный Web Crypto API перед отправкой на сервер.
// async — функция асинхронная: crypto.subtle.digest возвращает Promise (обещание результата)
async function hashPassword(password) {
  const encoder = new TextEncoder();           // TextEncoder переводит строку в массив байт (Uint8Array)
  const data = encoder.encode(password);       // превращаем пароль в байты — SHA-256 работает с байтами
  // crypto.subtle.digest — встроенный браузерный SHA-256; await ждёт результата Promise
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  // Array.from превращает ArrayBuffer в обычный массив чисел
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  // Каждое число (0–255) переводим в двузначный hex: toString(16) → hex, padStart(2, "0") → всегда 2 символа
  // join("") склеивает всё в одну строку из 64 символов
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

function App() {
  // useState(начальное_значение) возвращает [текущее_значение, функция_обновления]
  const [nickname, setNickname] = useState("");     // текст в поле "никнейм"
  const [password, setPassword] = useState("");     // текст в поле "пароль"
  const [message, setMessage] = useState("");       // сообщение об ошибке/успехе под формой
  const [loggedIn, setLoggedIn] = useState(false);  // вошёл ли пользователь
  const [isLogin, setIsLogin] = useState(true);     // true = режим входа, false = режим регистрации
  const [showTutorial, setShowTutorial] = useState(false); // показывать ли инструкцию после входа

  const handleRegister = async () => {
    const hashed = await hashPassword(password); // хешируем до отправки — пароль никогда не улетит в открытом виде
    try {
      // fetch — браузерный API для HTTP-запросов; await ждёт ответа сервера
      const response = await fetch(`${API}/register`, {
        method: "POST",                                              // POST — отправляем данные
        headers: { "Content-Type": "application/json" },            // сообщаем серверу, что тело — JSON
        body: JSON.stringify({ nickname, password: hashed })         // JSON.stringify превращает объект в строку
      });
      const data = await response.json(); // response.json() читает тело ответа и парсит JSON
      if (response.ok) {                  // ok = true когда HTTP-статус 200–299
        setMessage(data.message);
        setIsLogin(true); // после регистрации переключаемся на форму входа
      } else {
        setMessage(data.error);
      }
    } catch (error) {
      // catch ловит сетевые ошибки (сервер недоступен, нет интернета)
      setMessage("Сервер недоступен");
    }
  };

  const handleLogin = async () => {
    const hashed = await hashPassword(password);
    try {
      const response = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password: hashed })
      });
      const data = await response.json();
      if (response.ok) {
        setLoggedIn(true);      // переключаем флаг — компонент перерисуется и покажет GamePage
        setShowTutorial(true);  // показываем инструкцию при первом входе
        setMessage("");
      } else {
        setMessage(data.error);
      }
    } catch (error) {
      setMessage("Сервер недоступен");
    }
  };

  // Единый обработчик формы: срабатывает при нажатии Enter или кнопки Submit
  const handleSubmit = (e) => {
    e.preventDefault(); // предотвращаем стандартное поведение браузера (перезагрузку страницы)
    if (isLogin) {
      handleLogin();
    } else {
      handleRegister();
    }
  };

  const closeTutorial = () => setShowTutorial(false);

  // Условный рендеринг: если вошли — показываем GamePage (и возможно туториал поверх)
  if (loggedIn) {
    return (
      <>
        {/* Фрагмент <> позволяет вернуть несколько элементов без лишнего div */}
        {showTutorial && (
          // onClick на overlay закрывает модалку при клике мимо неё
          <div className="tutorial-overlay" onClick={closeTutorial}>
            {/* e.stopPropagation() — останавливает всплытие события: клик внутри модалки не закрывает её */}
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
        {/* Передаём nickname как prop — GamePage использует его для всех API-запросов */}
        <GamePage nickname={nickname} />
      </>
    );
  }

  // Форма входа/регистрации (отображается пока loggedIn === false)
  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="logo-icon">🌍</div>
          <h1>WORLD ECONOMIC</h1>
          <h2>SIMULATOR</h2>
        </div>
        {/* onSubmit — событие отправки формы; срабатывает при Enter и при клике на кнопку type="submit" */}
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <div className="input-icon">👤</div>
            {/* value + onChange — "управляемый компонент": React контролирует значение поля */}
            {/* e.target.value — текущее значение поля ввода, которое пользователь набрал */}
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
              type="password"        // type="password" скрывает ввод точками
              placeholder="Ключ доступа"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {/* type="submit" — эта кнопка отправляет форму (вызывает onSubmit) */}
          <button type="submit" className="auth-button">
            {/* Тернарный оператор: если isLogin — "ВОЙТИ", иначе — "АКТИВИРОВАТЬ" */}
            {isLogin ? "ВОЙТИ В СИСТЕМУ" : "АКТИВИРОВАТЬ АГЕНТА"}
          </button>
          <div className="auth-switch">
            <p>
              {isLogin ? "Нет доступа? " : "Уже есть доступ? "}
              {/* type="button" важно: без него кнопка внутри формы отправляет форму */}
              <button
                type="button"
                className="switch-button"
                onClick={() => {
                  setIsLogin(!isLogin); // ! — инвертируем булево значение (вход ↔ регистрация)
                  setMessage("");       // убираем старое сообщение об ошибке при переключении
                }}
              >
                {isLogin ? "Запросить регистрацию" : "Авторизоваться"}
              </button>
            </p>
          </div>
          {/* {message && <div>...} — отображаем блок только если message не пустая строка */}
          {message && (
            // includes("успешн") — проверяем текст, чтобы выбрать CSS-класс success или error
            <div className={`message ${message.includes("успешн") ? "success" : "error"}`}>
              {message}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

export default App; // экспорт по умолчанию: main.jsx сделает import App from './App.jsx'
