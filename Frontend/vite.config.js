// vite.config.js — настройки сборщика Vite
// Vite компилирует JSX → JavaScript, объединяет файлы и запускает dev-сервер

import { defineConfig } from 'vite'         // defineConfig даёт подсказки типов при написании конфига
import react from '@vitejs/plugin-react'    // плагин, который учит Vite понимать JSX и React Fast Refresh

// https://vite.dev/config/
export default defineConfig({
  // plugins — список расширений Vite; react() добавляет поддержку JSX и горячей перезагрузки без потери состояния
  plugins: [react()],
})
