// Base URL for the backend API.
// Set VITE_API_URL in your .env.local for local dev,
// or in Vercel environment variables for production.
export const API = import.meta.env.VITE_API_URL || 'http://localhost:5003';
