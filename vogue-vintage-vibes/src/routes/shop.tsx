import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { Availability, ProductBadge, ProductSort } from "@/lib/api";
import { api } from "@/lib/api";
import { ProductCard } from "@/components/ProductCard";
import { RecentlyViewedRail } from "@/components/product/RecentlyViewedRail";
import { categories, type CategoryId } from "@/data/products";
import { toPage } from "@/lib/api";
import { searchQuery, toProducts, useCatalog } from "@/lib/catalog";
import { Pager } from "@/components/Pager";
import { formatToman, toFa } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";

const BADGES: ProductBadge[] = ["sale", "new", "exclusive"];
const AVAILABILITIES: Availability[] = ["in_stock", "coming_soon", "preorder"];

const BADGE_LABELS: Record<ProductBadge, string> = {
  sale: "حراج",
  new: "جدید",
  exclusive: "ویژه",
  coming_soon: "به‌زودی",
  preorder: "پیش‌خرید",
};

const AVAILABILITY_LABELS: Record<Availability, string> = {
  in_stock: "موجود",
  coming_soon: "به‌زودی",
  preorder: "پیش‌خرید",
};

const SORTS: { key: ProductSort; label: string }[] = [
  { key: "new", label: "جدیدترین" },
  { key: "popular", label: "محبوب‌ترین" },
  { key: "rating", label: "بیشترین امتیاز" },
  { key: "price_asc", label: "ارزان‌ترین" },
  { key: "price_desc", label: "گران‌ترین" },
];

type ShopSearch = {
  category?: CategoryId;
  size?: string[];
  color?: string[];
  maxPrice?: number;
  sort?: ProductSort;
  tag?: string;
  badge?: ProductBadge;
  availability?: Availability;
  onSale?: boolean;
  q?: string;
  page?: number;
};

const str = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim() ? value.trim() : undefined;

/**
 * `?size=M&size=L` reaches the router as `["M","L"]` and `?size=M` as `"M"`;
 * both are normalised to a deduped list (undefined when nothing is selected).
 */
const list = (value: unknown): string[] | undefined => {
  const raw = Array.isArray(value) ? value : value == null ? [] : [value];
  const items = raw.map((item) => str(item)).filter((item): item is string => Boolean(item));
  return items.length ? Array.from(new Set(items)) : undefined;
};

/** Adds/removes one value in a multi-select facet. */
const toggle = (current: string[] | undefined, value: string): string[] | undefined => {
  const next = current?.includes(value)
    ? current.filter((item) => item !== value)
    : [...(current ?? []), value];
  return next.length ? next : undefined;
};

export const Route = createFileRoute("/shop")({
  validateSearch: (search: Record<string, unknown>): ShopSearch => {
    const category = search["category"];
    const sort = str(search["sort"]);
    const badge = str(search["badge"]);
    const availability = str(search["availability"]);
    const maxPrice = Number(search["maxPrice"]);
    const size = list(search["size"]);
    const color = list(search["color"]);
    return {
      ...(categories.some((c) => c.id === category) ? { category: category as CategoryId } : {}),
      ...(size ? { size } : {}),
      ...(color ? { color } : {}),
      ...(Number.isFinite(maxPrice) && maxPrice > 0 ? { maxPrice } : {}),
      ...(sort && SORTS.some((s) => s.key === sort) ? { sort: sort as ProductSort } : {}),
      ...(str(search["tag"]) ? { tag: str(search["tag"]) as string } : {}),
      ...(badge && BADGES.includes(badge as ProductBadge) ? { badge: badge as ProductBadge } : {}),
      ...(availability && AVAILABILITIES.includes(availability as Availability)
        ? { availability: availability as Availability }
        : {}),
      ...(search["onSale"] === true || search["onSale"] === "true" ? { onSale: true } : {}),
      ...(str(search["q"]) ? { q: str(search["q"]) as string } : {}),
      ...(search["page"] != null && Number(search["page"]) > 0
        ? { page: Number(search["page"]) }
        : {}),
    };
  },
  head: () => ({
    meta: [
      { title: "فروشگاه پوشاک زنانه — ساندِه" },
      {
        name: "description",
        content:
          "همه‌ی محصولات ساندِه: تی‌شرت، کراپ‌تاپ، شورت، جوراب و ست، با فیلتر سایز، رنگ، برچسب، موجودی و قیمت.",
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

function ShopPage() {
  const search = Route.useSearch();
  if (search.q) return <SearchResults query={search.q} />;
  return <CatalogPage search={search} />;
}

/** Server-side results for `GET /search` when the page is opened with `?q=`. */
function SearchResults({ query }: { query: string }) {
  const search = useQuery(searchQuery(query));
  const products = search.data?.products ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">نتایج جستجو</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {search.isLoading
          ? "در حال جستجو…"
          : `${toFa(search.data?.total ?? 0)} نتیجه برای «${query}»`}
      </p>

      <div className="mt-4 border-b border-border pb-6">
        <Link to="/shop" search={{}} className="text-sm text-terracotta hover:underline">
          حذف جستجو و دیدن همه‌ی محصولات
        </Link>
      </div>

      <div className="mt-10">
        {search.isLoading ? (
          <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-[4/5] animate-pulse rounded-[1.25rem] bg-clay" />
            ))}
          </div>
        ) : search.isError ? (
          <div className="border border-dashed border-border p-12 text-center">
            <p className="text-muted-foreground">جستجو انجام نشد. دوباره تلاش کنید.</p>
          </div>
        ) : products.length === 0 ? (
          <div className="border border-dashed border-border p-12 text-center">
            <p className="text-muted-foreground">نتیجه‌ای برای «{query}» پیدا نشد.</p>
            <Button variant="outline" className="mt-4" asChild>
              <Link to="/shop" search={{}}>
                دیدن همه‌ی محصولات
              </Link>
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** A patch where a key may be cleared with `undefined`. */
type ShopSearchPatch = { [K in keyof ShopSearch]?: ShopSearch[K] | undefined };

/** Removes empty values so links never carry `?size=undefined` or `?size=`. */
function clean(next: ShopSearchPatch): ShopSearch {
  return Object.fromEntries(
    Object.entries(next).filter(
      ([, value]) =>
        value !== undefined &&
        value !== false &&
        value !== "" &&
        !(Array.isArray(value) && value.length === 0),
    ),
  ) as ShopSearch;
}

function CatalogPage({ search }: { search: ShopSearch }) {
  const navigate = useNavigate();
  const { allSizes, allColors, priceBounds, all, isLoading: catalogLoading } = useCatalog();
  const [maxPriceDraft, setMaxPriceDraft] = useState<number | null>(search.maxPrice ?? null);
  const priceCap = search.maxPrice ?? priceBounds.max;

  const filters = {
    ...(search.category ? { category: search.category } : {}),
    ...(search.size ? { size: search.size } : {}),
    ...(search.color ? { color: search.color } : {}),
    ...(search.maxPrice != null ? { max_price: search.maxPrice } : {}),
    ...(search.tag ? { tag: search.tag } : {}),
    ...(search.badge ? { badge: search.badge } : {}),
    ...(search.availability ? { availability: search.availability } : {}),
    ...(search.onSale ? { on_sale: true } : {}),
    sort: search.sort ?? ("new" as ProductSort),
  };

  // Filtering, sorting, stock limits and pagination all happen in the backend.
  const products = useQuery({
    queryKey: ["products", filters, search.page ?? 1],
    queryFn: async () => {
      const page = toPage(await api.products({ ...filters, page: search.page ?? 1, page_size: 12 }));
      return { items: await toProducts(page.items), total: page.total, pages: page.pages };
    },
  });
  const visible = products.data?.items ?? [];

  const tags = Array.from(new Set(all.flatMap((product) => product.tags ?? []))).sort((a, b) =>
    a.localeCompare(b, "fa"),
  );
  const hasFilters = Boolean(
    search.category ||
    search.size?.length ||
    search.color?.length ||
    search.maxPrice != null ||
    search.tag ||
    search.badge ||
    search.availability ||
    search.onSale,
  );

  const chipBase = "rounded-full border px-3 py-1 text-xs transition-colors";
  const chipOn = "border-primary bg-primary text-primary-foreground";
  const chipOff = "border-border text-muted-foreground hover:text-foreground";

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">فروشگاه</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {products.isLoading
          ? "در حال بارگذاری…"
          : `${toFa(products.data?.total ?? visible.length)} محصول در دسترس`}
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-2 border-b border-border pb-6">
        <Link
          to="/shop"
          search={clean({ ...search, category: undefined })}
          className={cn(chipBase, search.category ? chipOff : chipOn)}
        >
          همه
        </Link>
        {categories.map((c) => (
          <Link
            key={c.id}
            to="/shop"
            search={clean({ ...search, category: c.id })}
            className={cn(chipBase, search.category === c.id ? chipOn : chipOff)}
          >
            {c.title}
          </Link>
        ))}
      </div>

      <div className="mt-10 grid gap-10 md:grid-cols-[220px_1fr]">
        <aside className="space-y-8">
          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">وضعیت</p>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/shop"
                search={clean({ ...search, availability: undefined })}
                className={cn(chipBase, search.availability ? chipOff : chipOn)}
              >
                همه
              </Link>
              {AVAILABILITIES.map((value) => (
                <Link
                  key={value}
                  to="/shop"
                  search={clean({ ...search, availability: value })}
                  className={cn(chipBase, search.availability === value ? chipOn : chipOff)}
                >
                  {AVAILABILITY_LABELS[value]}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">
              سایز <span className="tracking-normal">(چند انتخابی)</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {allSizes.map((size) => {
                const active = search.size?.includes(size) ?? false;
                return (
                  <Link
                    key={size}
                    to="/shop"
                    search={clean({ ...search, size: toggle(search.size, size) })}
                    aria-pressed={active}
                    className={cn(
                      "border px-3 py-1 text-xs transition-colors",
                      active
                        ? "border-foreground bg-foreground text-background"
                        : "border-border text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {toFa(size)}
                  </Link>
                );
              })}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">
              رنگ <span className="tracking-normal">(چند انتخابی)</span>
            </p>
            <div className="space-y-2">
              {allColors.map((color) => {
                const active = search.color?.includes(color.name) ?? false;
                return (
                  <Link
                    key={color.name}
                    to="/shop"
                    search={clean({ ...search, color: toggle(search.color, color.name) })}
                    aria-pressed={active}
                    className="flex w-full items-center gap-3 text-sm"
                  >
                    <span
                      className={cn(
                        "size-4 rounded-full border",
                        active ? "ring-1 ring-foreground ring-offset-2" : "",
                      )}
                      style={{ backgroundColor: color.hex }}
                    />
                    <span className={active ? "text-foreground" : "text-muted-foreground"}>
                      {color.name}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">حداکثر قیمت</p>
            <Slider
              dir="rtl"
              min={priceBounds.min}
              max={priceBounds.max}
              step={10000}
              value={[maxPriceDraft ?? priceCap]}
              onValueChange={(value) => setMaxPriceDraft(value[0] ?? priceBounds.max)}
              onValueCommit={(value) => {
                // the cap is applied to the server query once the handle is released
                const next = value[0] ?? priceBounds.max;
                setMaxPriceDraft(next);
                void navigate({
                  to: "/shop",
                  search: clean({
                    ...search,
                    maxPrice: next >= priceBounds.max ? undefined : next,
                  }),
                });
              }}
            />
            <p className="mt-3 text-sm">{formatToman(maxPriceDraft ?? priceCap)} تومان</p>
            {search.maxPrice != null && (
              <Link
                to="/shop"
                search={clean({ ...search, maxPrice: undefined })}
                className="mt-2 inline-block text-xs text-muted-foreground hover:text-foreground"
              >
                حذف سقف قیمت
              </Link>
            )}
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">برچسب‌ها</p>
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <Link
                  key={tag}
                  to="/shop"
                  search={clean({ ...search, tag: search.tag === tag ? undefined : tag })}
                  className={cn(chipBase, search.tag === tag ? chipOn : chipOff)}
                >
                  {tag}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">ویژه</p>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/shop"
                search={clean({
                  ...search,
                  onSale: search.onSale ? undefined : true,
                })}
                className={cn(chipBase, search.onSale ? chipOn : chipOff)}
              >
                فقط تخفیف‌دار
              </Link>
              {BADGES.map((value) => (
                <Link
                  key={value}
                  to="/shop"
                  search={clean({ ...search, badge: search.badge === value ? undefined : value })}
                  className={cn(chipBase, search.badge === value ? chipOn : chipOff)}
                >
                  {BADGE_LABELS[value]}
                </Link>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">مرتب‌سازی</p>
            <div className="flex flex-col items-start gap-2 text-sm">
              {SORTS.map(({ key, label }) => (
                <Link
                  key={key}
                  to="/shop"
                  search={clean({ ...search, sort: key })}
                  className={cn(
                    search.sort === key || (!search.sort && key === "new")
                      ? "text-foreground underline"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>

          {hasFilters && (
            <Button variant="outline" className="w-full rounded-none" asChild>
              <Link to="/shop" search={{}}>
                حذف فیلترها
              </Link>
            </Button>
          )}
        </aside>

        <div>
          {products.isLoading || catalogLoading ? (
            <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="aspect-[4/5] animate-pulse rounded-[1.25rem] bg-clay" />
              ))}
            </div>
          ) : products.isError ? (
            <div className="border border-dashed border-border p-12 text-center">
              <p className="text-muted-foreground">خواندن محصولات انجام نشد. دوباره تلاش کنید.</p>
            </div>
          ) : visible.length === 0 ? (
            <div className="border border-dashed border-border p-12 text-center">
              <p className="text-muted-foreground">محصولی با این فیلترها پیدا نشد.</p>
              <Button variant="outline" className="mt-4" asChild>
                <Link to="/shop" search={{}}>
                  حذف فیلترها
                </Link>
              </Button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
                {visible.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
              <Pager
                className="mt-12"
                page={search.page ?? 1}
                pages={products.data?.pages ?? 1}
                total={products.data?.total}
                onChange={(next) =>
                  navigate({
                    to: "/shop",
                    search: clean({ ...search, page: next > 1 ? next : undefined }),
                  })
                }
              />
            </>
          )}
        </div>
      </div>

      <RecentlyViewedRail />
    </div>
  );
}
