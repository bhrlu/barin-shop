import { createFileRoute, Link } from "@tanstack/react-router";
import { ProductCard } from "@/components/ProductCard";
import { useCatalog } from "@/lib/catalog";
import { useFavorites } from "@/lib/favorites";

export const Route = createFileRoute("/_authenticated/account/favorites")({
  component: FavoritesTab,
});

function FavoritesTab() {
  const { ids } = useFavorites();
  const { byId } = useCatalog();
  const items = ids.map(byId).filter((p): p is NonNullable<typeof p> => !!p);

  if (!items.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center">
        <p className="text-muted-foreground">فهرست علاقه‌مندی‌های شما خالی است.</p>
        <Link to="/shop" search={{}} className="mt-4 inline-block text-terracotta underline">
          دیدن محصولات
        </Link>
      </div>
    );

  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
      {items.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}