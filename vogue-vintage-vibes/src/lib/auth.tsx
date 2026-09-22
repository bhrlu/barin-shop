import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken, type UserInfo } from "@/lib/api";

type Profile = {
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
};

type AuthValue = {
  user: UserInfo | null;
  loading: boolean;
  isAdmin: boolean;
  profile: Profile | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: {
    email: string;
    password: string;
    full_name?: string;
    phone?: string;
  }) => Promise<void>;
  signOut: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthValue>({
  user: null,
  loading: true,
  isAdmin: false,
  profile: null,
  signIn: async () => {},
  signUp: async () => {},
  signOut: () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      // expired/invalid token — drop it and fall back to signed-out
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.signIn({ email, password });
    setToken(result.access_token);
    setUser(result.user);
  }, []);

  const signUp = useCallback(
    async (input: { email: string; password: string; full_name?: string; phone?: string }) => {
      const result = await api.signUp(input);
      setToken(result.access_token);
      setUser(result.user);
    },
    [],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user,
      loading,
      // B5.4: any staff role opens the admin shell (per-tab gating is F4.2)
      isAdmin: ["admin", "super_admin", "order_manager", "support"].includes(user?.role ?? ""),
      profile: user
        ? { full_name: user.full_name, phone: user.phone, avatar_url: user.avatar_url }
        : null,
      signIn,
      signUp,
      signOut,
      refresh,
    }),
    [user, loading, signIn, signUp, signOut, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function signOutEverywhere() {
  setToken(null);
}
