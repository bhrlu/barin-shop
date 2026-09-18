import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ProductCard } from "@/components/ProductCard";
import { categories, type CategoryId } from "@/data/products";
import { useCatalog } from "@/lib/catalog";
import { formatToman, toFa } from "@/lib/format";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";

type ShopSearch = { category?: CategoryId };

export const Route = createFileRoute("/shop")({
  validateSearch: (search: Record<string, unknown>): ShopSearch => {
    const category = search["category"];
    const valid = categories.some((c) => c.id === category);
    return valid ? { category: category as CategoryId } : {};
  },
  head: () => ({
    meta: [
      { title: "فروشگاه پوشاک زنانه — ساندِه" },
      {
        name: "description",
        content:
          "همه‌ی محصولات ساندِه: تی‌شرت، کراپ‌تاپ، شورت، جوراب و ست، با فیلتر سایز، رنگ و قیمت.",
      },
      { property: "og:title", content: "فروشگاه پوشاک زنانه — ساندِه" },
      {
        property: "og:description",
        content: "خرید آنلاین تی‌شرت، کراپ‌تاپ، شورت، جوراب و ست زنانه.",
      },
    ],
  }),
  component: ShopPage,
});

type SortKey = "new" | "cheap" | "expensive";

function ShopPage() {
  const { category } = Route.useSearch();
  const {
    products,
    allSizes,
    allColors,
    priceBounds,
    isLoading,
  } = useCatalog();
  const [sizes, setSizes] = useState<string[]>([]);
  const [colors, setColors] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState<number | null>(null);
  const [sort, setSort] = useState<SortKey>("new");
  const priceCap = maxPrice ?? priceBounds.max;

  const toggle = (value: string, list: string[], set: (v: string[]) => void) =>
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  const visible = useMemo(() => {
    const filtered = products.filter((p) => {
      if (category && p.category !== category) return false;
      if (p.price > priceCap) return false;
      if (sizes.length && !p.sizes.some((s) => sizes.includes(s))) return false;
      if (colors.length && !p.colors.some((c) => colors.includes(c.name))) return false;
      return true;
    });
    const sorted = [...filtered];
    if (sort === "cheap") sorted.sort((a, b) => a.price - b.price);
    if (sort === "expensive") sorted.sort((a, b) => b.price - a.price);
    if (sort === "new") sorted.sort((a, b) => Number(!!b.isNew) - Number(!!a.isNew));
    return sorted;
  }, [products, category, priceCap, sizes, colors, sort]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">فروشگاه</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {isLoading ? "در حال بارگذاری…" : `${toFa(visible.length)} محصول در دسترس`}
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-2 border-b border-border pb-6">
        <Link
          to="/shop"
          search={{}}
          className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
            category ? "border-border text-muted-foreground" : "border-primary bg-primary text-primary-foreground"
          }`}
        >
          همه
        </Link>
        {categories.map((c) => (
          <Link
            key={c.id}
            to="/shop"
            search={{ category: c.id }}
            className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
              category === c.id
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {c.title}
          </Link>
        ))}
      </div>

      <div className="mt-10 grid gap-10 md:grid-cols-[220px_1fr]">
        <aside className="space-y-8">
          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">سایز</p>
            <div className="flex flex-wrap gap-2">
              {allSizes.map((size) => (
                <button
                  key={size}
                  type="button"
                  onClick={() => toggle(size, sizes, setSizes)}
                  className={`border px-3 py-1 text-xs transition-colors ${
                    sizes.includes(size)
                      ? "border-foreground bg-foreground text-background"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {toFa(size)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">رنگ</p>
            <div className="space-y-2">
              {allColors.map((color) => (
                <button
                  key={color.name}
                  type="button"
                  onClick={() => toggle(color.name, colors, setColors)}
                  className="flex w-full items-center gap-3 text-sm"
                >
                  <span
                    className={`size-4 rounded-full border ${
                      colors.includes(color.name) ? "ring-1 ring-foreground ring-offset-2" : ""
                    }`}
                    style={{ backgroundColor: color.hex }}
                  />
                  <span
                    className={
                      colors.includes(color.name) ? "text-foreground" : "text-muted-foreground"
                    }
                  >
                    {color.name}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">حداکثر قیمت</p>
            <Slider
              dir="rtl"
              min={priceBounds.min}
              max={priceBounds.max}
              step={10000}
              value={[priceCap]}
              onValueChange={(v) => setMaxPrice(v[0] ?? priceBounds.max)}
            />
            <p className="mt-3 text-sm">{formatToman(priceCap)} تومان</p>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">مرتب‌سازی</p>
            <div className="flex flex-col items-start gap-2 text-sm">
              {(
                [
                  ["new", "جدیدترین"],
                  ["cheap", "ارزان‌ترین"],
                  ["expensive", "گران‌ترین"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSort(key)}
                  className={
                    sort === key ? "text-foreground underline" : "text-muted-foreground"
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div>
          {isLoading ? (
            <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="aspect-[4/5] animate-pulse rounded-[1.25rem] bg-clay" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <div className="border border-dashed border-border p-12 text-center">
              <p className="text-muted-foreground">محصولی با این فیلترها پیدا نشد.</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => {
                  setSizes([]);
                  setColors([]);
                  setMaxPrice(null);
                }}
              >
                حذف فیلترها
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
              {visible.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}