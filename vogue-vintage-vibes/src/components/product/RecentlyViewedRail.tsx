import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toProducts } from "@/lib/catalog";
import { ProductRail } from "@/components/product/ProductRail";
import { guestHistoryProducts } from "@/lib/recently-viewed";

/**
 * «بازدیدهای اخیر» rail (F3.4b): signed-in visitors see the server history
 * (authoritative — the guest list was merged into it at sign-in, before
 * `user` was ever set); guests see their own `localStorage` history. The
 * `user?.id ?? "guest"` key keeps the two worlds apart. Disappears while the
 * list is empty (a new visitor has no history yet).
 */
export function RecentlyViewedRail({ limit = 8 }: { limit?: number }) {
  const { user } = useAuth();
  const recent = useQuery({
    queryKey: ["recently-viewed", limit, user?.id ?? "guest"],
    queryFn: async () =>
      toProducts(user ? await api.recentlyViewed(limit) : await guestHistoryProducts(limit)),
  });
  const products = recent.data ?? [];
  if (products.length === 0) return null;

  return <ProductRail title="بازدیدهای اخیر" eyebrow="ادامه‌ی گشت‌وگذار" products={products} />;
}
