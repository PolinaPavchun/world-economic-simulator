// URL бэкенда: берётся из переменной окружения, иначе localhost для локальной разработки
export const API = import.meta.env.VITE_API_URL || 'http://localhost:5003';
