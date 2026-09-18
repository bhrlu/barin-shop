import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { catalogQuery } from "@/lib/catalog";

export type CartLine = {
  productId: string;
  size: string;
  color: string;
  quantity: number;
};

type CartContextValue = {
  lines: CartLine[];
  count: number;
  subtotal: number;
  add: (line: CartLine) => void;
  setQuantity: (index: number, quantity: number) => void;
  remove: (index: number) => void;
  clear: () => void;
};

const STORAGE_KEY = "sandeh-cart-v1";

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const { data: catalog } = useQuery({ ...catalogQuery, staleTime: 60_000 });

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setLines(JSON.parse(raw) as CartLine[]);
    } catch {
      /* ignore malformed storage */
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  }, [lines, hydrated]);

  const add = useCallback((line: CartLine) => {
    setLines((current) => {
      const index = current.findIndex(
        (l) =>
          l.productId === line.productId && l.size === line.size && l.color === line.color,
      );
      if (index === -1) return [...current, line];
      return current.map((l, i) =>
        i === index ? { ...l, quantity: l.quantity + line.quantity } : l,
      );
    });
  }, []);

  const setQuantity = useCallback((index: number, quantity: number) => {
    setLines((current) =>
      current.map((line, i) =>
        i === index ? { ...line, quantity: Math.max(1, Math.min(20, quantity)) } : line,
      ),
    );
  }, []);

  const remove = useCallback((index: number) => {
    setLines((current) => current.filter((_, i) => i !== index));
  }, []);

  const clear = useCallback(() => setLines([]), []);

  const value = useMemo<CartContextValue>(() => {
    const subtotal = lines.reduce((sum, line) => {
      const product = catalog?.find((p) => p.id === line.productId);
      return product ? sum + product.price * line.quantity : sum;
    }, 0);
    return {
      lines,
      count: lines.reduce((sum, line) => sum + line.quantity, 0),
      subtotal,
      add,
      setQuantity,
      remove,
      clear,
    };
  }, [lines, catalog, add, setQuantity, remove, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}