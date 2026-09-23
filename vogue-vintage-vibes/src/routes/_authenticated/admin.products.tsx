import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Layers, Pencil, Plus, Trash2 } from "lucide-react";
import { api, toPage, type Availability } from "@/lib/api";
import { toProducts, type AdminProduct } from "@/lib/catalog";
import { categories, categoryTitle, type CategoryId } from "@/data/products";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { ProductEditor } from "@/components/admin/ProductEditor";
import { VariantEditor } from "@/components/admin/VariantEditor";
import { AVAILABILITIES, BADGES } from "@/lib/product-form";
import { ProductsExportButtons } from "@/components/admin/ExportControls";
import { Pager } from "@/components/Pager";

/** Rows per page for the admin catalogue (AB-FE-05, same size as the other admin lists). */
const PAGE_SIZE = 20;

/** URL state (AB-FE-05): page + the server-side filters, so a refresh or a shared
 * link lands on the same slice. Invalid values become `undefined`. They must be
 * returned as explicit `undefined`, not just omitted: the router merges this
 * route's validated search over the parent's raw one, so an omitted key would
 * leak the raw `?page=abc` through. */
type ProductsSearch = {
  page?: number | undefined;
  category?: CategoryId | undefined;
  availability?: Availability | undefined;
};

/** Drops cleared keys so the URL never carries `?category=undefined`. */
function cleanSearch(next: ProductsSearch): ProductsSearch {
  return Object.fromEntries(
    Object.entries(next).filter(([, value]) => value !== undefined),
  ) as ProductsSearch;
}

const AVAILABILITY_VALUES: Availability[] = ["in_stock", "coming_soon", "preorder"];

export const Route = createFileRoute("/_authenticated/admin/products")({
  validateSearch: (search: Record<string, unknown>): ProductsSearch => {
    const page = Number(search["page"]);
    const category = search["category"];
    const availability = search["availability"];
    return {
      page: Number.isInteger(page) && page > 1 ? page : undefined,
      category: categories.some((c) => c.id === category) ? (category as CategoryId) : undefined,
      availability: AVAILABILITY_VALUES.includes(availability as Availability)
        ? (availability as Availability)
        : undefined,
    };
  },
  component: AdminProducts,
});

function AdminProducts() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();
  // the product being edited (`product: null` = a new one), or nothing open
  const [editing, setEditing] = useState<{ product: AdminProduct | null } | null>(null);
  const [variantsFor, setVariantsFor] = useState<string | null>(null);
  const page = search.page ?? 1;
  const filters = {
    ...(search.category ? { category: search.category } : {}),
    ...(search.availability ? { availability: search.availability } : {}),
  };
  const filtered = Boolean(search.category || search.availability);

  // One server page at a time (F2.5 envelope) instead of the whole catalogue;
  // include_inactive keeps deactivated products editable here.
  const products = useQuery({
    queryKey: ["admin-products", filters, page],
    queryFn: async () => {
      const result = toPage(
        await api.products({ ...filters, include_inactive: true, page, page_size: PAGE_SIZE }),
      );
      return { ...result, items: await toProducts(result.items) };
    },
    placeholderData: keepPreviousData,
  });
  const rows = products.data?.items ?? [];

  // a delete can leave the URL on a page past the end — step back to the last one
  const lastPage = products.data?.pages ?? 1;
  // (only on real data: while loading, `pages` is unknown, not 1)
  const outOfRange = products.isSuccess && !products.isPlaceholderData && page > lastPage;
  useEffect(() => {
    if (outOfRange)
      void navigate({
        search: (prev) => cleanSearch({ ...prev, page: lastPage > 1 ? lastPage : undefined }),
        replace: true,
      });
  }, [outOfRange, lastPage, navigate]);

  const setFilter = (patch: ProductsSearch) =>
    void navigate({ search: (prev) => cleanSearch({ ...prev, ...patch, page: undefined }) });

  // the admin list and the storefront catalogue both show these rows
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-products"] });
    void queryClient.invalidateQueries({ queryKey: ["catalog"] });
  };

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteProduct(id),
    onSuccess: () => {
      invalidate();
      toast.success("محصول حذف شد");
    },
    onError: () => toast.error("حذف انجام نشد (ممکن است در سفارش‌ها استفاده شده باشد)"),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg">
          فهرست محصولات {products.data ? `(${toFa(products.data.total)})` : ""}
        </h2>
        <div className="flex flex-wrap items-start gap-2">
          <ProductsExportButtons />
          <Button onClick={() => setEditing({ product: null })} className="gap-2">
            <Plus className="size-4" /> محصول جدید
          </Button>
        </div>
      </div>

      {editing && (
        <ProductEditor
          key={editing.product?.id ?? "new"}
          product={editing.product}
          onClose={() => setEditing(null)}
        />
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          دسته
          <select
            value={search.category ?? ""}
            onChange={(event) =>
              setFilter({ category: (event.target.value || undefined) as CategoryId | undefined })
            }
            className="h-10 rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-terracotta"
          >
            <option value="">همه</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.title}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          وضعیت عرضه
          <select
            value={search.availability ?? ""}
            onChange={(event) =>
              setFilter({
                availability: (event.target.value || undefined) as Availability | undefined,
              })
            }
            className="h-10 rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-terracotta"
          >
            <option value="">همه</option>
            {AVAILABILITIES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {filtered ? (
          <button
            type="button"
            onClick={() => setFilter({ category: undefined, availability: undefined })}
            className="h-10 px-2 text-xs text-terracotta underline-offset-4 hover:underline"
          >
            حذف فیلترها
          </button>
        ) : null}
      </div>

      {products.isLoading ? (
        <div className="space-y-2" aria-busy="true">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-2xl bg-muted/60" />
          ))}
        </div>
      ) : products.isError ? (
        <div className="rounded-3xl border border-destructive/30 bg-destructive/10 p-8 text-center text-sm text-destructive">
          <p>خواندن محصولات انجام نشد.</p>
          <button
            type="button"
            onClick={() => void products.refetch()}
            className="mt-3 text-xs underline underline-offset-4"
          >
            تلاش دوباره
          </button>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          {filtered ? "محصولی با این فیلترها پیدا نشد." : "هنوز محصولی ثبت نشده است."}
        </div>
      ) : (
        <ul
          aria-busy={products.isPlaceholderData}
          className={`divide-y divide-border rounded-3xl border border-border transition-opacity ${
            products.isPlaceholderData ? "opacity-60" : ""
          }`}
        >
          {rows.map((product) => {
            const lowStock = product.stock > 0 && product.stock <= product.lowStockThreshold;
            const availableAt = formatFaDate(product.availableAt);
            return (
              <li key={product.id} className="p-4 text-sm">
                <div className="flex flex-wrap items-center gap-4">
                  <img src={product.images[0]} alt="" className="size-14 rounded-xl object-cover" />
                  <div className="flex-1">
                    <p>{product.name}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>
                        {categoryTitle(product.category)} · موجودی {toFa(product.stock)}
                      </span>
                      {product.availability !== "in_stock" && (
                        <span className="rounded-full bg-sage/25 px-2 py-0.5 text-sage-deep">
                          {AVAILABILITIES.find((a) => a.value === product.availability)?.label}
                          {availableAt && ` · از ${availableAt}`}
                        </span>
                      )}
                      {product.badge && (
                        <span className="rounded-full bg-terracotta/10 px-2 py-0.5 text-terracotta">
                          {BADGES.find((b) => b.value === product.badge)?.label}
                        </span>
                      )}
                      {lowStock && <span className="text-terracotta">موجودی کم</span>}
                      {!product.active && <span>غیرفعال</span>}
                    </p>
                  </div>
                  <span>{formatToman(product.price)} تومان</span>
                  <button
                    type="button"
                    onClick={() => setVariantsFor(variantsFor === product.id ? null : product.id)}
                    aria-label="تنوع‌های سایز و رنگ"
                    aria-expanded={variantsFor === product.id}
                    className="text-muted-foreground hover:text-sage-deep"
                  >
                    <Layers className="size-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing({ product })}
                    aria-label="ویرایش"
                    className="text-muted-foreground hover:text-terracotta"
                  >
                    <Pencil className="size-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => remove.mutate(product.id)}
                    aria-label="حذف"
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
                {variantsFor === product.id && (
                  <div className="mt-4">
                    <VariantEditor product={product} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {rows.length > 0 ? (
        <Pager
          page={products.data?.page ?? page}
          pages={lastPage}
          total={products.data?.total}
          onChange={(next) =>
            void navigate({
              search: (prev) => cleanSearch({ ...prev, page: next > 1 ? next : undefined }),
            })
          }
        />
      ) : null}
    </div>
  );
}
