import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/** How many products the comparison table accepts at once (backend allows 10). */
export const COMPARE_LIMIT = 4;

const STORAGE_KEY = "sandeh-compare-v1";

export type ToggleResult = "added" | "removed" | "full";

type CompareContextValue = {
  ids: string[];
  count: number;
  has: (id: string) => boolean;
  /** Adds/removes an id; returns what happened so callers can toast accurately. */
  toggle: (id: string) => ToggleResult;
  remove: (id: string) => void;
  clear: () => void;
};

const CompareContext = createContext<CompareContextValue | null>(null);

/** Product ids picked for comparison, persisted in localStorage like the cart. */
export function CompareProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const parsed: unknown = raw ? JSON.parse(raw) : null;
      if (Array.isArray(parsed)) {
        setIds(
          parsed
            .filter((value): value is string => typeof value === "string")
            .slice(0, COMPARE_LIMIT),
        );
      }
    } catch {
      /* ignore malformed storage */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  }, [ids, hydrated]);

  const toggle = useCallback(
    (id: string): ToggleResult => {
      if (ids.includes(id)) {
        setIds((current) => current.filter((value) => value !== id));
        return "removed";
      }
      if (ids.length >= COMPARE_LIMIT) return "full";
      setIds((current) => [...current, id]);
      return "added";
    },
    [ids],
  );

  const remove = useCallback((id: string) => {
    setIds((current) => current.filter((value) => value !== id));
  }, []);

  const clear = useCallback(() => setIds([]), []);

  const value = useMemo<CompareContextValue>(
    () => ({
      ids,
      count: ids.length,
      has: (id: string) => ids.includes(id),
      toggle,
      remove,
      clear,
    }),
    [ids, toggle, remove, clear],
  );

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare() {
  const context = useContext(CompareContext);
  if (!context) throw new Error("useCompare must be used inside CompareProvider");
  return context;
}
