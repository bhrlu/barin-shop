import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type CartLine = {
  productId: string;
  size: string;
  color: string;
  quantity: number;
};

type CartContextValue = {
  lines: CartLine[];
  count: number;
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
        (l) => l.productId === line.productId && l.size === line.size && l.color === line.color,
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

  const value = useMemo<CartContextValue>(
    () => ({
      lines,
      count: lines.reduce((sum, line) => sum + line.quantity, 0),
      add,
      setQuantity,
      remove,
      clear,
    }),
    [lines, add, setQuantity, remove, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}

/** Identity of a cart line (the cart merges lines with the same product, size and colour). */
const cartLineKey = (line: Pick<CartLine, "productId" | "size" | "color">) =>
  `${line.productId}|${line.size}|${line.color}`;

/**
 * The server's quote for the cart: `POST /stock/check` — authoritative, variant-aware
 * stock and prices (`subtotal`, and each line's unit price, variant `price_override`
 * included). The cart and checkout show these instead of multiplying catalogue prices
 * (F5.18; the backend prices every order, R11). Keyed on every line and quantity, so
 * an edit re-quotes; the previous quote stays on screen while the new one loads, and
 * `priceOf(line)` looks prices up by line, never by position.
 */
export function useCartQuote() {
  const { lines } = useCart();
  const key = lines
    .map((line) => `${line.productId}:${line.size}:${line.color}:${line.quantity}`)
    .join("|");
  return useQuery({
    queryKey: ["cart-stock", key],
    enabled: lines.length > 0,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const quote = await api.stockCheck(
        lines.map((line) => ({
          product_id: line.productId,
          size: line.size,
          color: line.color,
          quantity: line.quantity,
        })),
      );
      const prices = new Map<string, number | null>(
        lines.map((line, index) => [cartLineKey(line), quote.unit_prices[index] ?? null]),
      );
      /** the server's unit price for a cart line (null while unknown) */
      const priceOf = (line: CartLine) => prices.get(cartLineKey(line)) ?? null;
      return { ...quote, priceOf };
    },
  });
}
