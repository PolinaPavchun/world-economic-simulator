// api.js — единственная строка конфигурации для общения с бэкендом
//
// import.meta.env.VITE_API_URL — переменная окружения Vite:
//   - локально: задаётся в файле .env.local (VITE_API_URL=http://localhost:5003)
//   - на Vercel (продакшн): задаётся в настройках проекта как переменная окружения
// Если переменная не задана — используем localhost:5003 (дефолт для локальной разработки)
// Все файлы компонентов делают: import { API } from "./api" — и используют API как префикс URL
export const API = import.meta.env.VITE_API_URL || 'http://localhost:5003';
