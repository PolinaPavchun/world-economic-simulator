// GamePage.jsx — основная игровая страница (карта, арсенал, аналитика)
// Получает nickname как prop от App.jsx и использует его во всех запросах к серверу

import React, { useState, useEffect, useRef } from "react";
// useState — хранит данные компонента (gameState, выбранная страна и т.д.)
// useEffect — выполняет код при монтировании/обновлении компонента (загрузка игры, таймер)
// useRef — хранит ссылку на объект между рендерами без перерисовки (intervalRef для таймера)
import "./GamePage.css";
import { WorldMap } from "react-svg-worldmap"; // SVG-карта мира с возможностью кастомизации стран
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ScatterChart, Scatter, ZAxis,
  ReferenceLine, Cell,
} from 'recharts'; // библиотека для графиков: линейный график и scatter-chart (пузырьковая диаграмма)
import { ConnectionGraph, ALLIANCE_COLORS } from "./ConnectionGraph"; // граф связей между странами
import { API } from "./api"; // базовый URL бэкенда


// Вычисляет условия применимости атаки к конкретной стране.
// Возвращает { canUse: bool, reason: string } — используется для цветовой подсветки в Арсенале
function computeAttackConditions(attack, country) {
  if (!country) return { canUse: true, reason: "" };

  if (attack.name === "Валютная атака") {
    const debt = Math.round(country.debt / country.gdp * 100);
    const res = Math.round(country.foreign_reserves);
    if (debt > 80 && res < 200) return { canUse: true, reason: `Долг ${debt}% + резервы $${res}млрд → ×2.2` };
    if (debt > 80) return { canUse: true, reason: `Долг ${debt}% ВВП → ×1.5` };
    if (res < 200) return { canUse: true, reason: `Резервы $${res}млрд → ×1.3` };
    return { canUse: false, reason: `Долг ${debt}%, резервы $${res}млрд — защита достаточна` };
  }
  if (attack.name === "Долговая спираль") {
    const debt = Math.round(country.debt / country.gdp * 100);
    if (debt > 100) return { canUse: true, reason: `Долг ${debt}% — критическая спираль → ×2.1` };
    if (debt > 80) return { canUse: true, reason: `Долг ${debt}% — давление на бюджет → ×1.4` };
    return { canUse: false, reason: `Долг ${debt}% — рынки считают долг устойчивым` };
  }
  if (attack.name === "Торговые санкции") {
    const dep = Math.round(Object.values(country.trade_partners || {}).reduce((a, b) => a + b, 0) * 100);
    const cnt = Object.keys(country.trade_partners || {}).length;
    if (dep > 50 && cnt <= 3) return { canUse: true, reason: `${dep}% зависимость, ${cnt} партнёра → ×2.7` };
    if (dep > 50) return { canUse: true, reason: `Зависимость ${dep}% → ×1.8` };
    if (cnt <= 3) return { canUse: true, reason: `Только ${cnt} партнёра → ×1.5` };
    return { canUse: false, reason: `${dep}% зависимость, ${cnt} партнёров — диверсифицировано` };
  }
  if (attack.name === "Энергетический шантаж") {
    const imp = Math.round(country.energy_import * 100);
    const exp = Math.round(country.energy_export * 100);
    if (exp > 40) return { canUse: false, reason: `Экспортирует ${exp}% энергии — неэффективно` };
    if (imp > 40) return { canUse: true, reason: `Импорт ${imp}% энергии → ×2.0` };
    return { canUse: false, reason: `Импорт ${imp}% — нет критической зависимости` };
  }
  if (attack.name === "Социальный взрыв") {
    const inf = country.inflation, unemp = country.unemployment, corr = country.corruption_perception_index;
    const hits = (inf > 8 ? 1 : 0) + (unemp > 10 ? 1 : 0) + (corr < 35 ? 1 : 0);
    if (hits >= 3) return { canUse: true, reason: `Инфляция + безработица + коррупция → ×2.5` };
    if (hits === 2) return { canUse: true, reason: `Два триггера → ×2.0` };
    if (hits === 1) return { canUse: true, reason: `Один триггер → ×1.5–1.9` };
    return { canUse: false, reason: `Инфляция ${inf}%, безработица ${unemp}% — стабильно` };
  }
  if (attack.name === "Кибератака") {
    const dig = country.digitalization;
    if (dig > 75) return { canUse: true, reason: `Цифровизация ${dig}% — парадокс уязвимости → ×1.9` };
    if (dig > 55) return { canUse: true, reason: `Цифровизация ${dig}% → ×1.0` };
    return { canUse: false, reason: `Цифровизация ${dig}% — не зависит от IT` };
  }
  return { canUse: true, reason: "" };
}

// Возвращает список экономических уязвимостей страны без прямых ссылок на атаки
function getVulnerabilities(country) {
  const v = [];
  const debtRatio = Math.round(country.debt / country.gdp * 100);
  if (debtRatio > 80) v.push(`Высокая долговая нагрузка (${debtRatio}% ВВП)`);
  if (country.foreign_reserves < 200) v.push(`Недостаточные резервы ($${Math.round(country.foreign_reserves)} млрд)`);
  const dep = Math.round(Object.values(country.trade_partners || {}).reduce((a, b) => a + b, 0) * 100);
  if (dep > 50) v.push(`Высокая торговая концентрация (${dep}%)`);
  if (country.energy_import > 0.4) v.push(`Критическая энергозависимость (${Math.round(country.energy_import * 100)}% импорт)`);
  if (country.inflation > 8) v.push(`Высокая инфляция (${country.inflation}%)`);
  if (country.unemployment > 10) v.push(`Высокая безработица (${country.unemployment}%)`);
  if (country.digitalization > 75) v.push(`Развитая цифровая инфраструктура (${country.digitalization}%)`);
  if (country.corruption_perception_index < 35) v.push(`Высокий уровень коррупции (ИКВ ${country.corruption_perception_index})`);
  if (v.length === 0) v.push("Нет явных уязвимостей");
  return v;
}

const REAL_CASES = {
  'Валютная атака': [
    {
      title: 'Великобритания, 1992 — «Чёрная среда»',
      text: 'Джордж Сорос заработал миллиард долларов, играя против британского фунта. Он взял в долг фунты, продал их за немецкие марки, а когда фунт обвалился — купил обратно за копейки и вернул долг. Банк Англии потратил 27 миллиардов резервов, защищая валюту, но проиграл. Британия была вынуждена выйти из Европейского механизма обмена валют.',
    },
    {
      title: 'Таиланд, 1997 — начало Азиатского кризиса',
      text: 'Таиланд взял слишком много долгов в долларах, а резервы были маленькими. Спекулянты атаковали бат, правительство сдалось и отпустило валюту. Бат упал вдвое, кризис перекинулся на Индонезию, Южную Корею и Россию. МВФ выдал кредиты, но с жёсткими условиями реформ.',
    },
  ],
  'Долговая спираль': [
    {
      title: 'Греция, 2010 — кризис еврозоны',
      text: 'Греция годами жила в долг, а когда выяснилось, что она скрывала реальную статистику, кредиторы потребовали до 25% годовых. Греция не могла платить — ЕС и МВФ спасали её тремя кредитами на 300 миллиардов евро. Взамен пришлось урезать пенсии и зарплаты. Безработица взлетела до 27%. Кризис показал: долг выше 100% ВВП — это катастрофа.',
    },
    {
      title: 'Аргентина, 2001 — крупнейший дефолт в истории',
      text: 'Аргентина объявила дефолт на 95 миллиардов долларов. Люди потеряли сбережения, начались погромы, за неделю сменилось пять президентов. Некоторые фонды скупили аргентинский долг за копейки и потом через суд отсудили миллиарды. Аргентина до сих пор расплачивается с последствиями.',
    },
  ],
  'Торговые санкции': [
    {
      title: 'Россия, 2022 — шок санкций',
      text: 'После вторжения в Украину Россию отрезали от SWIFT, заморозили $300 млрд резервов и закрыли рынки Европы и США. АвтоВАЗ остался без комплектующих, цены взлетели. Но Россия выжила, переориентировавшись на Китай, Индию и Турцию. Урок: диверсификация торговли спасает от санкций.',
    },
    {
      title: 'Иран, 2012 — долгая изоляция',
      text: 'США ввели санкции против иранской нефти и банков. Экспорт нефти рухнул с 2.5 до 0.5 млн баррелей в день, инфляция достигла 40%. Иран продержался 8 лет, пока не заключил ядерную сделку. Вывод: санкции работают, но медленно и больно — прежде всего для обычных людей.',
    },
  ],
  'Энергетический шантаж': [
    {
      title: 'Россия — Европа, 2022 — газовый кризис',
      text: 'Россия перекрыла «Северный поток» — цены на газ взлетели с $200 до $3000 за тысячу кубометров. Германия впала в рецессию, химические заводы встали. Европа экстренно искала СПГ из США и Катара. Урок: зависимость от одного поставщика энергии — смертельная уязвимость.',
    },
    {
      title: 'Украина, 2009 — отключение газа зимой',
      text: 'Россия отключила Украине газ в разгар зимы. Школы и больницы закрывались, заводы вставали. Европа получила сигнал оненадёжности российского газа и начала строить СПГ-терминалы. Через 15 лет это помогло пережить шок 2022 года.',
    },
  ],
  'Социальный взрыв': [
    {
      title: 'Франция, 2018 — «жёлтые жилеты»',
      text: 'Правительство подняло налог на бензин на 7 центов. Для многих это стало последней каплей после года застоя зарплат. Миллионы вышли на улицы, протесты длились полгода. Макрон отменил налог и раздал бонусы. Урок: даже мелкая проблема при высокой инфляции может взорвать страну.',
    },
    {
      title: 'Чили, 2019 — восстание из-за метро',
      text: 'Цена на проезд в метро выросла на 3 цента. Студенты начали прыгать через турникеты — полиция разогнала их. Через неделю миллион человек вышли на улицы. Два месяца протестов закончились сменой конституции. Дорогое метро — это была не проблема, а символ общего неравенства.',
    },
  ],
  'Кибератака': [
    {
      title: 'Colonial Pipeline, США, 2021',
      text: 'Хакеры взломали крупнейший трубопровод бензина на восточном побережье США. Вся сеть встала, цены на бензин взлетели, люди скупали топливо в канистры. Компания заплатила выкуп $4.4 млн в биткоинах. Урок: цифровая зависимость — новая уязвимость даже для физической инфраструктуры.',
    },
    {
      title: 'Эстония, 2007 — первая кибервойна',
      text: 'После переноса советского памятника на Эстонию обрушились массовые кибератаки. Рухнули сайты парламента, банков и телеканалов. НАТО создал специальный центр киберзащиты в Таллине. Эстония выжила, потому что её IT-инфраструктура была рассредоточена. Урок: если ты цифровая страна — готовься к атакам.',
    },
  ],
};

const ECONOMIC_GLOSSARY = {
  "Здоровье экономики": "Общее состояние экономики от 0 до 100%. Ниже 20% — коллапс.",
  "Долг/ВВП": "Насколько страна должна относительно того, что производит. Выше 90% — опасная зона.",
  "Инфляция": "Как быстро растут цены. Норма — 2–5%, выше 8% — уже проблема.",
  "Резервы": "Золото и валюта на счетах центробанка. Ниже $200 млрд — слабая защита от валютных атак.",
  "Торговая зависимость": "Какую долю экономики составляет торговля с другими странами.",
  "Коррупция (ИКВ)": "Индекс восприятия коррупции от 0 (очень высокая) до 100 (очень низкая). Ниже 35 — коррупция усиливает урон от ЛЮБОЙ атаки на ×1.2–1.5. Коррумпированные чиновники не могут эффективно противостоять кризису.",
  "ИЧР": "Индекс человеческого развития от 0 до 1: учитывает доходы, образование и продолжительность жизни. Выше 0.9 → страна восстанавливается на +50% быстрее: развитые институты и квалифицированные кадры быстро стабилизируют экономику.",
  "Энергоимпорт": "Доля потребляемой энергии, которую страна закупает за рубежом. Выше 40% — критическая уязвимость: Энергетический шантаж наносит урон ×2.0. Ниже 40% — страна относительно независима.",
};

const ALLIANCE_MAP_FILLS = {
  'НАТО': '#0d2a5a', 'ЕС': '#2a0d5a', 'G7': '#3a3000',
  'БРИКС': '#3a1500', 'ШОС': '#3a0000', 'Five Eyes': '#003a2a',
  'Союзник США': '#0d1f3a',
};

function getHealthColor(h) {
  if (h >= 75) return "#1a6e30";   // насыщенный зелёный — стабильно
  if (h >= 55) return "#3a7a20";   // оливковый — небольшое давление
  if (h >= 40) return "#8a6a10";   // янтарный — под угрозой
  if (h >= 25) return "#b84020";   // тёмно-оранжевый — опасно
  return "#991010";                // глубокий красный — коллапс
}

const ScatterTip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: '#0f141c', border: '1px solid #334', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ color: '#00d4ff', fontWeight: 700 }}>{d.name}</div>
      <div>Долг/ВВП: {d.x}%</div>
      <div style={{ color: getHealthColor(d.y) }}>Здоровье: {d.y}%</div>
    </div>
  );
};


// { nickname } — деструктуризация props: вместо props.nickname пишем просто nickname
function GamePage({ nickname }) {
  // null — начальное значение до загрузки данных с сервера
  const [gameState, setGameState] = useState(null);      // всё состояние игры (IP, страны, раскрытие)
  const [selectedCountry, setSelectedCountry] = useState(null);  // название выбранной страны-цели
  const [selectedAttack, setSelectedAttack] = useState(null);    // название выбранной атаки
  const [log, setLog] = useState([]);           // лог действий в нижней панели (последние 25 событий)
  const [activeTab, setActiveTab] = useState("map");  // активная вкладка: "map" | "graph" | "attacks" | "analytics"
  const [toast, setToast] = useState(null);     // всплывающее уведомление (toast) вверху экрана
  const [showTutorial, setShowTutorial] = useState(false);   // показывать ли инструкцию
  const [mapVersion, setMapVersion] = useState(0);           // инкремент заставляет карту перерисоваться
  const [showExplanation, setShowExplanation] = useState(null);  // модалка с результатом атаки
  const [showDebrief, setShowDebrief] = useState(null);      // модалка победы/поражения
  const [crisisSpread, setCrisisSpread] = useState([]);      // страны, куда докатилась волна кризиса
  const [healthHistory, setHealthHistory] = useState([]);    // история здоровья по дням для графика
  const [showGlossary, setShowGlossary] = useState(false);   // показывать ли глоссарий
  const [glossaryTerm, setGlossaryTerm] = useState("");      // какой термин открыт в глоссарии

  // Режим подсказок — показывает/скрывает уязвимости и эффективность атак
  // () => ... — ленивый инициализатор useState: выполняется один раз при монтировании
  // localStorage — браузерное хранилище, сохраняется между сессиями
  const [hintMode, setHintMode] = useState(() => localStorage.getItem("hintMode") !== "off");
  const toggleHintMode = () => setHintMode(prev => {
    const next = !prev; // инвертируем
    localStorage.setItem("hintMode", next ? "on" : "off"); // сохраняем в localStorage
    return next;
  });

  // Quiz state — quizMinimized позволяет скрыть модалку без потери вопроса
  const [quizData, setQuizData] = useState(null);       // данные текущего вопроса
  const [quizSelected, setQuizSelected] = useState(null); // выбранный игроком вариант
  const [quizResult, setQuizResult] = useState(null);   // результат проверки ответа
  const [quizMinimized, setQuizMinimized] = useState(false); // свёрнут ли квиз
  const [showCases, setShowCases] = useState(null); // название атаки для модалки реальных кейсов
  // useRef создаёт объект {current: null}, который живёт между рендерами и НЕ вызывает перерисовку
  // Нужен для хранения ID интервала, чтобы очистить его при размонтировании компонента
  const intervalRef = useRef(null);

  // useEffect с пустым массивом [] — выполняется ОДИН РАЗ при монтировании компонента
  // Показываем туториал если ещё не видели (ключ в localStorage отсутствует)
  useEffect(() => {
    if (!localStorage.getItem("tutorialShown")) setShowTutorial(true);
  }, []); // [] = зависимости пустые → эффект не повторяется при обновлении state

  const fetchGameState = async () => {
    try {
      // GET-запрос: nickname передаётся в строке запроса (?nickname=...)
      const res = await fetch(`${API}/game/state?nickname=${nickname}`);
      const data = await res.json();
      setGameState(data);
      // Добавляем новую точку в историю здоровья для графика
      // prev.slice(-30) — берём последние 30 дней (старые выбрасываем)
      // ...spread — разворачиваем массив
      // Object.fromEntries([["США", 85], ["Китай", 72], ...]) — создаём объект из массива пар [ключ, значение]
      setHealthHistory(prev => [...prev.slice(-30), {
        day: data.day,
        global: data.global_health,
        ...Object.fromEntries(data.countries.map(c => [c.name, c.economic_health]))
      }]);
    } catch { /* silent — не показываем ошибку, просто ждём следующего тика */ }
  };

  const resetGame = async () => {
    if (!window.confirm("Начать заново? Прогресс будет потерян.")) return;
    try {
      const res = await fetch(`${API}/reset_game`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname }),
      });
      const data = await res.json();
      if (res.ok) {
        setGameState(data.state); setSelectedCountry(null); setSelectedAttack(null);
        setMapVersion(v => v + 1); setHealthHistory([]); setCrisisSpread([]);
        addLog("Игра сброшена"); showToast("Новая игра", "success");
      }
    } catch { showToast("Ошибка соединения", "error"); }
  };

  const performAttack = async () => {
    if (!selectedCountry || !selectedAttack) { showToast("Выбери страну и атаку", "warning"); return; }
    try {
      const res = await fetch(`${API}/game/attack`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, attack_name: selectedAttack, target_name: selectedCountry }),
      });
      const data = await res.json();
      addLog(data.message);
      setGameState(data.state);
      setMapVersion(v => v + 1);
      if (data.state) {
        setHealthHistory(prev => [...prev.slice(-30), {
          day: data.state.day, global: data.state.global_health,
          ...Object.fromEntries(data.state.countries.map(c => [c.name, c.economic_health]))
        }]);
      }
      if (data.details) {
        setShowExplanation({ success: data.success, attack: selectedAttack, target: selectedCountry, ...data.details });
        if (data.details.affected_countries?.length) {
          setCrisisSpread(data.details.affected_countries);
          setTimeout(() => setCrisisSpread([]), 4000);
        }
      }
    } catch { showToast("Ошибка соединения", "error"); }
  };

  const openQuiz = async () => {
    // Если вопрос уже открыт (свёрнут) — просто разворачиваем, не тратим попытку
    if (quizData && !quizResult) {
      setQuizMinimized(false);
      return;
    }
    setQuizSelected(null); setQuizResult(null); setQuizMinimized(false);
    try {
      const res = await fetch(`${API}/game/quiz?nickname=${nickname}`);
      const data = await res.json();
      setQuizData(data);
    } catch { showToast("Ошибка загрузки вопроса", "error"); }
  };

  const submitQuizAnswer = async (answer) => {
    if (quizResult) return;
    setQuizSelected(answer);
    try {
      const res = await fetch(`${API}/game/quiz/answer`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, answer }),
      });
      const data = await res.json();
      setQuizResult(data);
      if (data.correct) {
        setGameState(prev => prev ? {
          ...prev,
          ip: data.ip,
          reveal: Math.max(0, (prev.reveal || 0) + (data.reveal_change || 0)),
          quiz_remaining: data.remaining ?? Math.max(0, (prev.quiz_remaining || 3) - 1),
        } : prev);
        showToast(`+${data.ip_gained} IP · давление ${data.reveal_change}`, "success");
      } else {
        setGameState(prev => prev ? {
          ...prev,
          quiz_remaining: data.remaining ?? Math.max(0, (prev.quiz_remaining || 3) - 1),
        } : prev);
      }
    } catch { showToast("Ошибка", "error"); }
  };

  // useEffect с [nickname] — запускается при монтировании и при смене nickname (перелогине)
  useEffect(() => {
    fetchGameState(); // загружаем начальное состояние сразу при входе
    // setInterval вызывает функцию каждые 10 000 мс (= 10 секунд) — это игровой тик
    // Сохраняем ID в intervalRef.current, чтобы потом остановить таймер
    intervalRef.current = setInterval(async () => {
      try {
        // POST-запрос к /game/daily: сервер обновляет состояние (восстановление, коллапс, события)
        const res = await fetch(`${API}/game/daily`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nickname }),
        });
        const s = await res.json();
        setGameState(s);
        setMapVersion(v => v + 1); // инкремент ключа карты → React перерисует карту с новыми цветами
        setHealthHistory(prev => [...prev.slice(-30), {
          day: s.day, global: s.global_health,
          ...Object.fromEntries(s.countries.map(c => [c.name, c.economic_health]))
        }]);
        if (s.game_over) {
          // Array.reduce с коллбэком сравнения: находит страну с наименьшим healthом
          const worst = s.countries.reduce((a, b) => a.economic_health < b.economic_health ? a : b);
          setShowDebrief({ winner: s.win, worst: worst.name, worstHealth: worst.economic_health });
        }
      } catch { /* silent */ }
    }, 10000);
    // Функция очистки: React вызывает её при размонтировании компонента
    // clearInterval останавливает таймер — без этого он продолжал бы работать после выхода
    return () => clearInterval(intervalRef.current);
  }, [nickname]);

  const addLog = msg => {
    // toLocaleTimeString с опциями форматирует время как "14:35"
    const t = new Date().toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });
    // prev — предыдущее значение лога; новое сообщение вставляем В НАЧАЛО (prepend)
    // slice(0, 25) — обрезаем до 25 сообщений, чтобы лог не рос бесконечно
    setLog(prev => [`${t} ${msg}`, ...prev].slice(0, 25));
  };
  const showToast = (msg, type = "info") => {
    // type = "info" — значение по умолчанию, если второй аргумент не передан
    setToast({ msg, type });
    // setTimeout убирает toast через 5 секунд: передаём null → React скрывает элемент
    setTimeout(() => setToast(null), 5000);
  };

  // Пока данные не загружены — показываем заглушку (gameState === null при первом рендере)
  if (!gameState) return <div className="loading">Загрузка...</div>;

  // Деструктуризация: вытаскиваем нужные поля из gameState одной строкой
  const { ip, reveal, reveal_level, quiz_remaining, day, game_over, win, global_health, countries, attacks } = gameState;

  // Таблица соответствия: русское название страны → двухбуквенный ISO-код для SVG-карты
  const countryCodeMap = {
    "США": "US", "Китай": "CN", "Россия": "RU", "Германия": "DE",
    "Франция": "FR", "Великобритания": "GB", "Япония": "JP", "Индия": "IN",
    "Бразилия": "BR", "Канада": "CA", "Австралия": "AU", "Мексика": "MX",
    "Турция": "TR", "ЮАР": "ZA", "Южная Корея": "KR", "Саудовская Аравия": "SA",
  };

  // Преобразуем массив стран в формат, который ожидает библиотека WorldMap
  // .filter(x => x.country) убирает страны без ISO-кода (не должно быть, но на всякий случай)
  const mapData = countries.map(c => ({ country: countryCodeMap[c.name], value: c.economic_health, name: c.name })).filter(x => x.country);

  // Функция стилизации для каждой страны на карте — вызывается библиотекой WorldMap
  const getStyle = ({ countryCode }) => {
    // Object.keys(...).find(...) — ищем русское название по ISO-коду (обратный поиск по словарю)
    const name = Object.keys(countryCodeMap).find(k => countryCodeMap[k] === countryCode);
    const country = countries.find(c => c.name === name);
    // Страна не в нашей игре (например, Антарктида) — рисуем нейтральным цветом
    if (!country) return { fill: '#0a1225', stroke: '#3a6a9a', strokeWidth: 1, cursor: 'default' };
    const isSelected = selectedCountry === name;   // выбрана как цель атаки
    const isAffected = crisisSpread.find(a => a.country === name); // затронута волной кризиса
    const isCollapsing = country.economic_health < 20; // ниже 20% — страна коллапсирует
    // Приоритет цвета: волна кризиса > цвет здоровья
    const fill = isAffected ? '#ff4444' : getHealthColor(country.economic_health);
    return {
      fill,
      // Тернарные операторы задают цвет границы страны в зависимости от состояния
      stroke: isSelected ? '#00ffff' : isCollapsing ? '#ff5533' : '#ffffff',
      strokeWidth: isSelected ? 3 : isCollapsing ? 2 : 1,
      cursor: 'pointer',
      // CSS filter drop-shadow создаёт свечение вокруг выбранной/коллапсирующей страны
      filter: isSelected
        ? 'drop-shadow(0 0 8px #00ffff)'
        : isCollapsing
          ? 'drop-shadow(0 0 6px #ff3311)'
          : 'none',
    };
  };

  const handleCountryClick = ({ countryCode }) => {
    if (game_over) return;
    const name = Object.keys(countryCodeMap).find(k => countryCodeMap[k] === countryCode);
    if (!name) return;
    setSelectedCountry(name);
    addLog(`Цель: ${name}`);
  };

  const getTooltipText = ({ countryName }) => {
    const c = countries.find(x => x.name === countryName);
    if (!c) return countryName;
    return `${countryName} | здоровье ${c.economic_health}% | долг ${Math.round(c.debt / c.gdp * 100)}%`;
  };

  const getAttackCost = attack => {
    const t = selectedCountry ? countries.find(c => c.name === selectedCountry) : null;
    return t ? Math.floor(attack.cost * (t.weight || 1)) : attack.cost;
  };

  const selectedCountryData = selectedCountry ? countries.find(c => c.name === selectedCountry) : null;
  // Данные для scatter chart: x = долг/ВВП%, y = здоровье%, z = размер пузырька (√ВВП)
  // Math.sqrt(c.gdp) * 8 — квадратный корень даёт визуально пропорциональные круги (площадь ∝ ВВП)
  const scatterData = countries.map(c => ({
    x: Math.round(c.debt / c.gdp * 100), y: c.economic_health,
    z: Math.sqrt(c.gdp) * 8, name: c.name,
  }));
  const TOP5 = ['США', 'Китай', 'Германия', 'Россия', 'Япония'];
  const CHART_COLORS = ['#ff6b6b', '#51cf66', '#ffd43b', '#ff922b', '#da77f2'];

  return (
    <div className="game-page">

      {/* Tutorial — mission briefing */}
      {showTutorial && (
        <div className="tutorial-overlay" onClick={() => { setShowTutorial(false); localStorage.setItem("tutorialShown", "true"); }}>
          <div className="tutorial-modal" onClick={e => e.stopPropagation()}>
            <button className="tutorial-close" onClick={() => { setShowTutorial(false); localStorage.setItem("tutorialShown", "true"); }}>✕</button>

            <div className="briefing-classified">Совершенно секретно. Только для агентов.</div>

            <p className="briefing-hook">
              Мировая экономика держится на доверии.<br />
              Доверие — это уязвимость.<br />
              Ты знаешь, как работают долги, санкции<br />
              и паника на биржах. Пора использовать это.
            </p>

            <div className="briefing-divider" />

            <div className="briefing-blocks">
              <div className="briefing-block">
                <div className="bb-title">Цель</div>
                <div className="bb-text">Обрушить среднее экономическое здоровье 16 стран ниже 30%. Следи за глобальным индексом в шапке — это твой ориентир.</div>
              </div>
              <div className="briefing-block">
                <div className="bb-title">Как действовать</div>
                <div className="bb-text">Выбери страну на карте. Открой Арсенал и выбери атаку под её слабость: высокий долг, энергозависимость, социальное напряжение. Читай объяснения после удара — каждая атака основана на реальном экономическом механизме.</div>
              </div>
              <div className="briefing-block">
                <div className="bb-title">Очки влияния (IP)</div>
                <div className="bb-text">Тратишь на атаки, получаешь обратно за успех. Кнопка «Разведка» — ответь на вопрос про экономику, заработай IP и снизь раскрытие.</div>
              </div>
              <div className="briefing-block">
                <div className="bb-title">Кризис не останавливается</div>
                <div className="bb-text">Удар по одной стране расходится волной на её торговых партнёров, кредиторов и союзников. Иногда один удар задевает пятерых.</div>
              </div>
              <div className="briefing-block briefing-block-danger">
                <div className="bb-title">Опасность — раскрытие</div>
                <div className="bb-text">Провалы и неточные атаки оставляют следы. Если раскрытие дойдёт до 100% — операция провалена. Жди, отвечай на вопросы, выбирай цели точнее.</div>
              </div>
            </div>

            <div className="briefing-tagline">16 стран. 6 инструментов. Один порог.</div>

            <button className="tutorial-button" onClick={() => { setShowTutorial(false); localStorage.setItem("tutorialShown", "true"); }}>
              Начать операцию
            </button>
          </div>
        </div>
      )}

      {toast && <div className={`toast ${toast.type}`}>{toast.msg}</div>}

      {/* Real cases modal */}
      {showCases && (
        <div className="cases-overlay" onClick={() => setShowCases(null)}>
          <div className="cases-modal" onClick={e => e.stopPropagation()}>
            <button className="cases-close" onClick={() => setShowCases(null)}>✕</button>
            <h3 className="cases-title">{showCases} — реальные случаи</h3>
            <div className="cases-list">
              {(REAL_CASES[showCases] || []).map((c, i) => (
                <div key={i} className="case-card">
                  <div className="case-card-title">{c.title}</div>
                  <p className="case-card-text">{c.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Attack result — chain format */}
      {showExplanation && (
        <div className="explanation-overlay" onClick={() => setShowExplanation(null)}>
          <div className="explanation-modal" onClick={e => e.stopPropagation()}>
            <button className="explanation-close" onClick={() => setShowExplanation(null)}>✕</button>
            <div className="exp-status">{showExplanation.success ? "Успех" : "Провал"}</div>

            {/* Cause chain */}
            <div className="exp-chain">
              <div className="exp-chain-item exp-target">{showExplanation.target}</div>
              <div className="exp-chain-arrow">↓</div>
              <div className="exp-chain-item exp-cause">{showExplanation.explanation || showExplanation.attack}</div>
              {showExplanation.damage > 0 && <>
                <div className="exp-chain-arrow">↓</div>
                <div className="exp-chain-item exp-damage">Урон −{showExplanation.damage}</div>
              </>}
              {(showExplanation.affected_countries || []).length > 0 && <>
                <div className="exp-chain-arrow">↓</div>
                <div className="exp-chain-item exp-spread">
                  Волна кризиса:&nbsp;
                  {showExplanation.affected_countries.slice(0, 4).map((a, i) => (
                    <span key={i} className="exp-spread-tag">{a.country} −{a.damage}</span>
                  ))}
                </div>
              </>}
            </div>

            {showExplanation.lesson && (
              <div className="exp-lesson">
                <span className="exp-lesson-label">Принцип</span>
                {showExplanation.lesson}
              </div>
            )}
            <button className="explanation-button" onClick={() => setShowExplanation(null)}>Понятно</button>
          </div>
        </div>
      )}

      {/* Debrief */}
      {showDebrief && (
        <div className="debrief-overlay" onClick={() => setShowDebrief(null)}>
          <div className="debrief-modal" onClick={e => e.stopPropagation()}>
            <button className="debrief-close" onClick={() => setShowDebrief(null)}>✕</button>
            <h2>{showDebrief.winner ? "Победа" : "Поражение"}</h2>
            <p>{showDebrief.winner ? "Мировая экономика рухнула." : "IP закончились."}</p>
            <p style={{ color: '#88aacc', marginTop: 8 }}>Наиболее пострадавшая: {showDebrief.worst} ({showDebrief.worstHealth}%)</p>
            <button className="debrief-button" onClick={() => { setShowDebrief(null); setActiveTab("analytics"); }}>Смотреть аналитику</button>
          </div>
        </div>
      )}

      {/* Glossary */}
      {showGlossary && (
        <div className="glossary-overlay" onClick={() => setShowGlossary(false)}>
          <div className="glossary-modal" onClick={e => e.stopPropagation()}>
            <button className="glossary-close" onClick={() => setShowGlossary(false)}>✕</button>
            <h3>Глоссарий</h3>
            <h4>{glossaryTerm}</h4>
            <p>{ECONOMIC_GLOSSARY[glossaryTerm]}</p>
            <div className="glossary-nav">
              {Object.keys(ECONOMIC_GLOSSARY).map(t => (
                <button key={t} className={`glossary-btn ${t === glossaryTerm ? 'active' : ''}`} onClick={() => setGlossaryTerm(t)}>{t}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Плавающий бейдж — показывается когда квиз свёрнут */}
      {quizData && !quizResult && quizMinimized && (
        <button className="quiz-minimized-badge" onClick={() => setQuizMinimized(false)}>
          Вернуться к вопросу ↗
        </button>
      )}

      {/* Quiz modal — не закрывается кликом снаружи, пока нет ответа */}
      {quizData && !quizMinimized && (
        <div className="quiz-overlay" onClick={() => { if (quizResult) { setQuizData(null); setQuizResult(null); setQuizSelected(null); } }}>
          <div className="quiz-modal" onClick={e => e.stopPropagation()}>
            {/* X закрывает полностью только после ответа; до ответа — сворачивает */}
            <button className="quiz-close" onClick={() => {
              if (quizResult) { setQuizData(null); setQuizResult(null); setQuizSelected(null); }
              else { setQuizMinimized(true); }
            }}>
              {quizResult ? '✕' : '↙ свернуть'}
            </button>
            <div className="quiz-reward-badge">+{quizData.reward} IP за правильный ответ</div>
            <h3 className="quiz-question">{quizData.question}</h3>
            {quizData.hint && <div className="quiz-hint">{quizData.hint}</div>}
            <div className="quiz-options">
              {(quizData.options || []).map((opt, i) => {
                let cls = 'quiz-option';
                if (quizResult) {
                  if (opt === quizSelected && quizResult.correct) cls += ' correct';
                  else if (opt === quizSelected && !quizResult.correct) cls += ' wrong';
                } else if (opt === quizSelected) {
                  cls += ' selected';
                }
                return (
                  <button key={i} className={cls} onClick={() => submitQuizAnswer(opt)} disabled={!!quizResult}>
                    {opt}
                  </button>
                );
              })}
            </div>
            {quizResult && (
              <div className={`quiz-result ${quizResult.correct ? 'correct' : 'wrong'}`}>
                <strong>
                  {quizResult.correct
                    ? `Верно! +${quizResult.ip_gained} IP · давление ${quizResult.reveal_change}`
                    : 'Неверно'}
                </strong>
                <p>{quizResult.explanation}</p>
                <button className="quiz-next-btn" onClick={() => { setQuizData(null); setQuizResult(null); setQuizSelected(null); }}>Закрыть</button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="game-header">
        <div className="header-content">
          <div className="logo-area">
            <h1>Мировой экономический симулятор</h1>
          </div>
          <div className="stats-bar">
            <div className="stat">IP: {ip}</div>
            <div className="stat">День: {day}</div>
            <div className="stat stat-health" style={{ color: getHealthColor(global_health) }}>Здоровье: {global_health}%</div>
            <div className={`stat stat-reveal stat-reveal-${reveal_level || 'low'}`}>
              {reveal_level === 'low' && `Раскрытие: ${reveal}%`}
              {reveal_level === 'medium' && `Раскрытие: ${reveal}% — заметны`}
              {reveal_level === 'high' && `Раскрытие: ${reveal}% — горячо`}
              {reveal_level === 'critical' && `Раскрытие: ${reveal}% — критично`}
            </div>
            <button
              className={`hint-mode-btn ${hintMode ? 'hint-on' : 'hint-off'}`}
              onClick={toggleHintMode}
              title={hintMode ? 'Подсказки включены — нажми чтобы выключить' : 'Подсказки выключены — нажми чтобы включить'}
            >
              {hintMode ? 'Подсказки вкл' : 'Подсказки выкл'}
            </button>
            <div className="user-badge">
              {nickname}
              <button className="reset-game-btn" onClick={resetGame} title="Новая игра">↺</button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="game-tabs">
        <button className={`tab-btn ${activeTab === "map" ? "active" : ""}`} onClick={() => setActiveTab("map")}>Карта</button>
        <button className={`tab-btn ${activeTab === "graph" ? "active" : ""}`} onClick={() => setActiveTab("graph")}>Граф связей</button>
        <button className={`tab-btn ${activeTab === "attacks" ? "active" : ""}`} onClick={() => setActiveTab("attacks")}>Арсенал</button>
        <button className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`} onClick={() => setActiveTab("analytics")}>Аналитика</button>
      </div>

      {/* MAP TAB */}
      {activeTab === "map" && (
        <div className="game-layout">
          <div className="map-container">
            <div className="world-map-wrapper">
              <WorldMap key={mapVersion} data={mapData} styleFunction={getStyle} onClickFunction={handleCountryClick} tooltipTextFunction={getTooltipText} />
            </div>
            <div className="crisis-legend">
              <div className="legend-item"><span className="color green" />Здорова &gt;60%</div>
              <div className="legend-item"><span className="color yellow" />Под угрозой 20–60%</div>
              <div className="legend-item"><span className="color red" />Коллапс &lt;20%</div>
              {crisisSpread.length > 0 && <div className="legend-item"><span className="color pulse" />Волна кризиса</div>}
            </div>
            {crisisSpread.length > 0 && selectedCountry && (
              <div className="crisis-ripple-panel">
                <div className="crp-title">Волна кризиса из {selectedCountry}</div>
                <div className="crp-items">
                  {crisisSpread.slice(0, 8).map((a, i) => {
                    const icon = a.connection_type === 'trade' ? 'торговля' : a.connection_type === 'debt' ? 'долг' : a.connection_type === 'energy' ? 'энергия' : a.connection_type === 'alliance' ? `альянс` : 'связь';
                    return (
                      <div key={i} className="crp-item" style={{ animationDelay: `${i * 100}ms` }}>
                        <span className="crp-country">{a.country}</span>
                        <span className="crp-type">{icon}</span>
                        <span className="crp-damage">−{a.damage}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="game-panel">
            {selectedCountryData ? (
              <div className="country-detail-card">
                <div className="cdc-header">
                  <span className="cdc-name">{selectedCountryData.name}</span>
                  <span className="cdc-health" style={{ background: getHealthColor(selectedCountryData.economic_health) }}>{selectedCountryData.economic_health}%</span>
                </div>
                <div className="cdc-bars">
                  {[
                    { label: 'Долг/ВВП', val: Math.round(selectedCountryData.debt / selectedCountryData.gdp * 100), max: 210, warn: 90, color: '#e74c3c', unit: '%', warnLabel: 'опасно >90%' },
                    { label: 'Инфляция', val: selectedCountryData.inflation, max: 30, warn: 8, color: '#f39c12', unit: '%', warnLabel: 'норма до 8%' },
                    { label: 'Безработица', val: selectedCountryData.unemployment, max: 35, warn: 10, color: '#e67e22', unit: '%', warnLabel: 'норма до 10%' },
                    { label: 'Резервы', val: selectedCountryData.foreign_reserves, max: 1500, warn: -1, color: '#2ecc71', unit: ' $млрд', warnLabel: '' },
                  ].map(({ label, val, max, warn, color, unit, warnLabel }) => {
                    const pct = Math.min(100, (val / max) * 100);
                    const hot = warn > 0 && val > warn;
                    const display = typeof val === 'number' ? (Number.isInteger(val) ? val : val.toFixed(1)) : val;
                    return (
                      <div key={label} className="cdc-bar-row">
                        <div className="cdc-bar-label">
                          <span>{label}</span>
                          <span style={{ color: hot ? '#ff6666' : '#e0eeff' }}>{display}{unit}</span>
                        </div>
                        <div className="cdc-bar-track" title={warnLabel ? `Черта: ${warnLabel}` : ''}>
                          <div className="cdc-bar-fill" style={{ width: `${pct}%`, background: hot ? '#e74c3c' : color }} />
                          {warn > 0 && (
                            <div className="cdc-bar-threshold" style={{ left: `${(warn / max) * 100}%` }} title={warnLabel} />
                          )}
                        </div>
                        {warnLabel && <div className="cdc-bar-warn-label">{hot ? '⚠ ' : ''}{warnLabel}</div>}
                      </div>
                    );
                  })}
                </div>
                <div className="cdc-alliances">
                  {(selectedCountryData.alliances || []).map((a, i) => { const n = a?.name || a; const col = ALLIANCE_COLORS[n] || '#888'; return <span key={i} className="alliance-badge" style={{ borderColor: col, color: col }}>{n}</span>; })}
                  {(selectedCountryData.trade_blocs || []).map((b, i) => <span key={i} className="trade-bloc-badge">{b}</span>)}
                </div>
                {hintMode && (
                  <div className="cdc-vulns">
                    {getVulnerabilities(selectedCountryData).map((v, i) => (
                      <div key={i} className={`cdc-vuln-item ${v.includes('нет') ? 'safe' : 'warn'}`}>{v}</div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="selected-info">Выбери страну на карте</div>
            )}

            <button className="attack-action" onClick={performAttack} disabled={game_over || !selectedCountry || !selectedAttack}>
              {selectedAttack ? `Атаковать: ${selectedAttack}` : selectedCountry ? "Выбери атаку в Арсенале" : "Выбери страну и атаку"}
            </button>

            <button
              className="quiz-trigger-btn"
              onClick={openQuiz}
              disabled={quiz_remaining === 0}
              title={quiz_remaining === 0 ? 'Лимит исчерпан — сбросится завтра' : ''}
            >
              {quiz_remaining > 0
                ? `Разведка — заработать IP (${quiz_remaining} из 3)`
                : 'Разведка недоступна до следующего дня'}
            </button>

          </div>
        </div>
      )}

      {/* GRAPH TAB */}
      {activeTab === "graph" && (
        <div className="graph-tab-container">
          <div className="graph-tab-header">
            <h3>Граф экономических связей</h3>
            <p className="graph-tab-intro">
              Выбери тип связей. Стрелка энергии указывает на импортёра — видно, кто от кого зависит. Кликни на страну, чтобы увидеть её конкретные связи.
            </p>
          </div>
          <ConnectionGraph countries={countries} selectedCountry={selectedCountry}
            onSelectCountry={name => { setSelectedCountry(name); if (name) addLog(`Цель: ${name}`); }} />
        </div>
      )}

      {/* ATTACKS TAB */}
      {activeTab === "attacks" && (
        <div className="attacks-tab">
          <h3>Арсенал</h3>
          <p className="attacks-intro">
            {selectedCountry
              ? hintMode
                ? `Выбрана цель: ${selectedCountry}. Зелёное — атака эффективна, серое — нет.`
                : `Выбрана цель: ${selectedCountry}.`
              : "Сначала выбери страну на карте или в Графе."}
          </p>
          <div className="attacks-grid">
            {attacks.map(a => {
              const cost = getAttackCost(a);
              const target = selectedCountry ? countries.find(c => c.name === selectedCountry) : null;
              const cond = target ? computeAttackConditions(a, target) : null;
              return (
                <div key={a.name}
                  className={`attack-card ${selectedAttack === a.name ? "active" : ""}`}
                  onClick={() => setSelectedAttack(a.name)}
                >
                  <div className="attack-name">{a.name}</div>
                  <div className="attack-stats">
                    <span>IP: {cost}</span>
                    <span>Урон: ~{a.damage}</span>
                  </div>
                  {a.tooltip && <div className="attack-tooltip-text">{a.tooltip}</div>}
                  {hintMode && cond && (
                    <div className={`attack-conditions ${cond.canUse ? 'success' : 'weak'}`}>
                      {cond.reason}
                    </div>
                  )}
                  <button
                    className="cases-trigger-btn"
                    onClick={e => { e.stopPropagation(); setShowCases(a.name); }}
                  >
                    Реальные кейсы
                  </button>
                </div>
              );
            })}
          </div>
          {selectedAttack && <div className="selected-attack-info">Выбрано: {selectedAttack}</div>}
        </div>
      )}

      {/* ANALYTICS TAB */}
      {activeTab === "analytics" && (
        <div className="analytics-tab">
          <h3>Аналитика</h3>

          {healthHistory.length > 1 && (
            <div className="analytics-chart-section">
              <h4>Динамика здоровья по дням</h4>
              <p className="chart-desc">Глобальное здоровье и 5 крупнейших экономик. Цель — опустить синюю линию ниже 30%.</p>
              <div style={{ width: '100%', height: 220 }}>
                <ResponsiveContainer>
                  <LineChart data={healthHistory}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2a3a" />
                    <XAxis dataKey="day" stroke="#88aacc" fontSize={11} />
                    <YAxis stroke="#88aacc" domain={[0, 100]} fontSize={11} />
                    <Tooltip contentStyle={{ background: '#0f141c', border: '1px solid #334', borderRadius: 8, fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="global" stroke="#00d4ff" name="Глобальное" strokeWidth={2.5} dot={false} />
                    {TOP5.map((name, i) => (
                      <Line key={name} type="monotone" dataKey={name} stroke={CHART_COLORS[i]} name={name} strokeWidth={1.5} dot={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="analytics-chart-section">
            <h4>Долг/ВВП vs Здоровье <span className="chart-badge">Рейнхарт–Рогофф</span></h4>
            <p className="chart-desc">
              Пунктирная линия — порог 90% ВВП. Страны правее неё, как правило, слабее.
              Это подтверждает: высокий долг замедляет экономический рост.
            </p>
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2a3a" />
                  <XAxis dataKey="x" name="Долг/ВВП" unit="%" stroke="#88aacc" fontSize={11} type="number" domain={[0, 'auto']} />
                  <YAxis dataKey="y" name="Здоровье" unit="%" stroke="#88aacc" domain={[0, 100]} fontSize={11} />
                  <ZAxis dataKey="z" range={[40, 200]} />
                  <Tooltip content={<ScatterTip />} />
                  <ReferenceLine x={90} stroke="#ff4444" strokeWidth={2} strokeDasharray="6,3"
                    label={{ value: "90% ВВП", fill: "#ff6666", fontSize: 11, position: "insideTopLeft" }} />
                  <Scatter data={scatterData}>
                    {scatterData.map((d, i) => <Cell key={i} fill={getHealthColor(d.y)} opacity={0.85} />)}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="analytics-table">
            <table>
              <thead>
                <tr>
                  <th>Страна</th>
                  <th onClick={() => { setGlossaryTerm("Здоровье экономики"); setShowGlossary(true); }} style={{ cursor: 'help' }}>Здоровье</th>
                  <th onClick={() => { setGlossaryTerm("Долг/ВВП"); setShowGlossary(true); }} style={{ cursor: 'help' }}>Долг/ВВП</th>
                  <th onClick={() => { setGlossaryTerm("Инфляция"); setShowGlossary(true); }} style={{ cursor: 'help' }}>Инфляция</th>
                  <th onClick={() => { setGlossaryTerm("Резервы"); setShowGlossary(true); }} style={{ cursor: 'help' }}>Резервы</th>
                  <th>Безработица</th>
                  <th>Цифровизация</th>
                  <th onClick={() => { setGlossaryTerm("Коррупция (ИКВ)"); setShowGlossary(true); }} style={{ cursor: 'help' }} title="Кликни — подробнее">Коррупция ИКВ</th>
                  <th onClick={() => { setGlossaryTerm("ИЧР"); setShowGlossary(true); }} style={{ cursor: 'help' }} title="Кликни — подробнее">ИЧР</th>
                  <th onClick={() => { setGlossaryTerm("Энергоимпорт"); setShowGlossary(true); }} style={{ cursor: 'help' }} title="Кликни — подробнее">Энергоимпорт</th>
                </tr>
              </thead>
              <tbody>
                {countries.map(c => {
                  return (
                    <tr key={c.name} className={selectedCountry === c.name ? "selected-row" : ""}
                      onClick={() => { setSelectedCountry(c.name); setActiveTab("map"); }}>
                      <td>
                        <strong>{c.name}</strong>
                        {(c.alliances || []).slice(0, 1).map((a, i) => {
                          const n = a?.name || a; const col = ALLIANCE_COLORS[n] || '#888';
                          return <span key={i} style={{ marginLeft: 6, fontSize: 10, color: col }}>({n})</span>;
                        })}
                      </td>
                      <td style={{ color: getHealthColor(c.economic_health), fontWeight: 600 }}>{c.economic_health}%</td>
                      <td style={{ color: c.debt / c.gdp > 0.9 ? '#ff8888' : '#cde' }}>{Math.round(c.debt / c.gdp * 100)}%</td>
                      <td style={{ color: c.inflation > 8 ? '#ffaa66' : '#cde' }}>{c.inflation}%</td>
                      <td style={{ color: c.foreign_reserves < 200 ? '#ff8888' : '#cde' }}>${Math.round(c.foreign_reserves)} млрд</td>
                      <td style={{ color: c.unemployment > 10 ? '#ffaa66' : '#cde' }}>{c.unemployment}%</td>
                      <td style={{ color: c.digitalization > 75 ? '#da77f2' : '#cde' }}>{c.digitalization}%</td>
                      <td
                        style={{ color: c.corruption_perception_index < 35 ? '#ff8888' : c.corruption_perception_index < 50 ? '#ffaa66' : '#cde' }}
                        title={c.corruption_perception_index < 35 ? 'Высокая коррупция → урон атак ×1.5' : c.corruption_perception_index < 50 ? 'Средняя коррупция → урон атак ×1.2' : 'Низкая коррупция — защита в норме'}
                      >{c.corruption_perception_index}</td>
                      <td
                        style={{ color: c.human_development_index > 0.9 ? '#51cf66' : c.human_development_index > 0.8 ? '#8bc34a' : '#cde' }}
                        title={c.human_development_index > 0.9 ? 'ИЧР >0.9 → восстановление +50%' : c.human_development_index > 0.8 ? 'ИЧР >0.8 → восстановление +20%' : 'Низкий ИЧР — медленное восстановление'}
                      >{c.human_development_index.toFixed(2)}</td>
                      <td
                        style={{ color: c.energy_import > 0.4 ? '#ff8888' : c.energy_import > 0.2 ? '#ffaa66' : '#cde' }}
                        title={c.energy_import > 0.4 ? `Критическая зависимость — Энергошантаж ×2.0` : c.energy_import > 0.2 ? 'Умеренный импорт — небольшая уязвимость' : 'Низкая энергозависимость — шантаж неэффективен'}
                      >{Math.round(c.energy_import * 100)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="analytics-hint">Кликни на строку — выбрать цель. Кликни на заголовок — определение.</div>
        </div>
      )}

      {game_over && (
        <div className="game-over-modal">
          <div className="modal-content">
            <h2>{win ? "Победа" : "Конец игры"}</h2>
            <p>{win ? "Мировая экономика рухнула." : "IP исчерпаны."}</p>
            <button onClick={resetGame}>Начать заново</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default GamePage;
