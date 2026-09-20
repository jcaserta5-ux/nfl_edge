import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (token: string, username: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      isAuthenticated: false,
      login: (token, username) => {
        localStorage.setItem('access_token', token);
        set({ token, username, isAuthenticated: true });
      },
      logout: () => {
        localStorage.removeItem('access_token');
        set({ token: null, username: null, isAuthenticated: false });
      },
    }),
    { name: 'nfl-edge-auth' }
  )
);
