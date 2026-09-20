import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ── API helpers ───────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  register: (email: string, username: string, password: string, invite_code: string) =>
    api.post('/auth/register', { email, username, password, invite_code }),
};

export const gamesApi = {
  list: (params?: { season?: number; week?: number }) => api.get('/games/', { params }),
  get: (id: number) => api.get(`/games/${id}`),
  oddsHistory: (id: number) => api.get(`/games/${id}/odds/history`),

  /**
   * Fetch all 32 teams sorted by FPI power rank for a given season/week.
   * Falls back to the nearest prior week automatically.
   */
  rankings: (season: number = 2026, week: number = 1) =>
    api.get('/games/rankings/current', { params: { season, week } }),

  /**
   * Fetch league-wide injury designations.
   * @param status  Optional filter — 'Out' | 'Doubtful' | 'Questionable' | 'Probable'
   */
  injuries: (status?: string) =>
    api.get('/games/injuries/current', { params: status ? { status } : {} }),
};
