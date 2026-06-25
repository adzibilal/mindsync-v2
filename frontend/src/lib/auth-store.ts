import { create } from "zustand";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: typeof window !== "undefined" ? localStorage.getItem("mindsync_token") : null,
  isAuthenticated: typeof window !== "undefined" ? !!localStorage.getItem("mindsync_token") : false,
  login: (token: string) => {
    localStorage.setItem("mindsync_token", token);
    set({ token, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem("mindsync_token");
    set({ token: null, isAuthenticated: false });
  },
}));
