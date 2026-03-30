import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

interface AuthUser {
  id: number;
  username: string;
  role: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
  isAdmin: false,
});

const TOKEN_KEY = 'codex_token';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<AuthUser | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  // Restore session on mount
  useEffect(() => {
    if (!token) return;
    api.get('/auth/me')
      .then(r => setUser({ id: r.data.id, username: r.data.username, role: r.data.role }))
      .catch(() => logout());
  }, [token, logout]);

  const login = useCallback(async (username: string, password: string) => {
    const r = await api.post('/auth/login', { username, password });
    const { access_token, id, username: uname, role } = r.data;
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    setUser({ id, username: uname, role });
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
