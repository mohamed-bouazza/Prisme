/**
 * Session de l'utilisateur, partagée par toute l'application (contexte React).
 *
 * Au chargement, on demande /api/auth/me : si le cookie de session est valide, on est connecté.
 * Le jeton lui-même n'est jamais manipulé en JavaScript (cookie httpOnly) : plus sûr qu'un localStorage.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext } from "react";

import { api, type User } from "@/lib/api";

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.me().then((r) => r.user).catch(() => null), // 401 = pas connecté, pas une erreur
    staleTime: Infinity,
  });

  const value: AuthState = {
    user: me.data ?? null,
    loading: me.isPending,
    login: async (email, password) => {
      const { user } = await api.login(email, password);
      qc.setQueryData(["me"], user);
    },
    register: async (email, username, password) => {
      const { user } = await api.register(email, username, password);
      qc.setQueryData(["me"], user);
    },
    logout: async () => {
      await api.logout().catch(() => undefined);
      qc.clear(); // on oublie toutes les données de l'utilisateur précédent
      qc.setQueryData(["me"], null);
    },
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}
