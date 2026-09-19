import { useQuery } from "@tanstack/react-query";
import { recentlyViewedQuery } from "@/lib/catalog";
import { useAuth } from "@/lib/auth";
import { ProductRail } from "@/components/product/ProductRail";

/**
 * «بازدیدهای اخیر» rail. `GET /recently-viewed` is per-customer, so it only
 * renders for a signed-in visitor and disappears while the list is empty
 * (a new customer has no history yet).
 */
export function RecentlyViewedRail({ limit = 8 }: { limit?: number }) {
  const { user } = useAuth();
  const recent = useQuery({ ...recentlyViewedQuery(limit), enabled: Boolean(user) });
  const products = recent.data ?? [];
  if (products.length === 0) return null;

  return <ProductRail title="بازدیدهای اخیر" eyebrow="ادامه‌ی گشت‌وگذار" products={products} />;
}
