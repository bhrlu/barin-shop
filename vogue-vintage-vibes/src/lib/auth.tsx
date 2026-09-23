import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, getToken, setToken, type UserInfo } from "@/lib/api";

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

/** `/auth/me` answers that mean the stored token no longer names a session:
 * invalid or expired (401), refused (403), or the account is gone (404). Any other
 * failure — a network error, a request cut off by a page navigation, a 5xx — says
 * nothing about the token, so it is kept and the check is retried (F5.15). */
const SESSION_GONE = new Set([401, 403, 404]);
const RETRY_DELAYS_MS = [1_000, 3_000, 10_000];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const retry = useRef<{ attempt: number; timer: number | undefined }>({
    attempt: 0,
    timer: undefined,
  });

  const cancelRetry = useCallback(() => {
    window.clearTimeout(retry.current.timer);
    retry.current = { attempt: 0, timer: undefined };
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    window.clearTimeout(retry.current.timer);
    if (!getToken()) {
      retry.current.attempt = 0;
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
      retry.current.attempt = 0;
      setLoading(false);
    } catch (error) {
      if (error instanceof ApiError && SESSION_GONE.has(error.status)) {
        // the session is really over — drop the token and fall back to signed-out
        setToken(null);
        setUser(null);
        retry.current.attempt = 0;
        setLoading(false);
        return;
      }
      // transient: keep the token and whatever user we had, try again shortly;
      // stay "loading" meanwhile so the UI does not flash signed-out
      const delay = RETRY_DELAYS_MS[retry.current.attempt];
      if (delay === undefined) {
        retry.current.attempt = 0;
        setLoading(false);
        return;
      }
      retry.current.attempt += 1;
      retry.current.timer = window.setTimeout(() => void refresh(), delay);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => window.clearTimeout(retry.current.timer);
  }, [refresh]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const result = await api.signIn({ email, password });
      cancelRetry();
      setToken(result.access_token);
      setUser(result.user);
      setLoading(false);
    },
    [cancelRetry],
  );

  const signUp = useCallback(
    async (input: { email: string; password: string; full_name?: string; phone?: string }) => {
      const result = await api.signUp(input);
      cancelRetry();
      setToken(result.access_token);
      setUser(result.user);
      setLoading(false);
    },
    [cancelRetry],
  );

  const signOut = useCallback(() => {
    cancelRetry();
    setToken(null);
    setUser(null);
    setLoading(false);
  }, [cancelRetry]);

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
