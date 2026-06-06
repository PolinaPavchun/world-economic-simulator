// main.jsx — точка входа React-приложения
// Именно с этого файла браузер начинает загрузку всего интерфейса

import { StrictMode } from 'react'          // StrictMode — режим разработки: обнаруживает потенциальные проблемы
import { createRoot } from 'react-dom/client' // createRoot — современный способ монтировать React в DOM (React 18+)
import './index.css'                          // глобальные CSS-стили (сброс, шрифты, переменные)
import App from './App.jsx'                   // корневой компонент приложения

// document.getElementById('root') — находит <div id="root"> в index.html — туда React вставит всё приложение
// createRoot(...).render(...) — отрисовывает дерево компонентов внутри этого div
createRoot(document.getElementById('root')).render(
  // StrictMode оборачивает приложение — он не меняет визуальный результат,
  // но в режиме разработки дважды вызывает функции, чтобы найти ошибки
  <StrictMode>
    <App />
  </StrictMode>,
)
