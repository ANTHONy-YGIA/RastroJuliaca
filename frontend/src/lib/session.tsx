import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Category, Meta, User } from "./types";

interface SessionState {
  user: User | null;
  unread: number;
  loading: boolean;
  meta: Meta | null;
  categories: Category[];
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<User>;
  register: (data: { email: string; full_name: string; password: string; role: "DENUNCIANTE" | "COLABORADOR"; accept_terms: boolean }) => Promise<User>;
  logout: () => Promise<void>;
}

const Ctx = createContext<SessionState | null>(null);

interface MePayload {
  user: User;
  csrf_token: string;
  unread_notifications: number;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);

  const refresh = useCallback(async () => {
    try {
      const me = await api<MePayload>("/auth/me");
      setUser(me.user);
      setUnread(me.unread_notifications);
    } catch {
      setUser(null);
      setUnread(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    api<Meta>("/meta").then(setMeta).catch(() => undefined);
    api<Category[]>("/categories").then(setCategories).catch(() => undefined);
  }, [refresh]);

  // Actualiza el contador de notificaciones periódicamente mientras hay sesión
  useEffect(() => {
    if (!user) return;
    const t = setInterval(refresh, 30000);
    return () => clearInterval(t);
  }, [user, refresh]);

  const login = async (email: string, password: string) => {
    const me = await api<MePayload>("/auth/login", { body: { email, password } });
    setUser(me.user);
    setUnread(me.unread_notifications);
    return me.user;
  };
  const register: SessionState["register"] = async (data) => {
    const me = await api<MePayload>("/auth/register", { body: data });
    setUser(me.user);
    setUnread(0);
    return me.user;
  };
  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
    setUnread(0);
  };

  return <Ctx.Provider value={{ user, unread, loading, meta, categories, refresh, login, register, logout }}>{children}</Ctx.Provider>;
}

export function useSession(): SessionState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession fuera de SessionProvider");
  return v;
}

export function homeFor(user: User | null): string {
  if (!user) return "/";
  return { DENUNCIANTE: "/mis-expedientes", COLABORADOR: "/mis-aportaciones", REVISOR: "/revisor", ADMIN: "/admin" }[user.role];
}

export function flatCategories(cats: Category[]): Category[] {
  return cats.flatMap((c) => [c, ...(c.children ?? [])]);
}
