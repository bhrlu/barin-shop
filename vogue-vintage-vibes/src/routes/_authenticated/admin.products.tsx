import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Layers, Pencil, Plus, Trash2 } from "lucide-react";
import { api, toPage, type Availability, type ProductBadge } from "@/lib/api";
import { toProducts, type AdminProduct } from "@/lib/catalog";
import { categories, categoryTitle, type CategoryId } from "@/data/products";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ProductImageManager } from "@/components/admin/ProductImageManager";
import { VariantEditor } from "@/components/admin/VariantEditor";
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

const BADGES: { value: ProductBadge | ""; label: string }[] = [
  { value: "", label: "بدون نشان" },
  { value: "sale", label: "حراج" },
  { value: "new", label: "جدید" },
  { value: "exclusive", label: "ویژه" },
  { value: "coming_soon", label: "به‌زودی" },
  { value: "preorder", label: "پیش‌خرید" },
];

const AVAILABILITIES: { value: Availability; label: string }[] = [
  { value: "in_stock", label: "موجود" },
  { value: "coming_soon", label: "به‌زودی" },
  { value: "preorder", label: "پیش‌خرید" },
];

type FormState = {
  id?: string;
  name: string;
  category: string;
  price: string;
  old_price: string;
  sizes: string;
  colors: string;
  images: string[];
  material: string;
  description: string;
  stock: string;
  is_new: boolean;
  active: boolean;
  tags: string;
  badge: ProductBadge | "";
  availability: Availability;
  available_at: string;
  low_stock_threshold: string;
};

const emptyForm: FormState = {
  name: "",
  category: "tshirt",
  price: "",
  old_price: "",
  sizes: "S, M, L",
  colors: "کرم #f0ebe3, تِراکوتا #b5654a",
  images: ["cat-tshirt"],
  material: "",
  description: "",
  stock: "25",
  is_new: true,
  active: true,
  tags: "",
  badge: "",
  availability: "in_stock",
  available_at: "",
  low_stock_threshold: "5",
};

/** `available_at` is a date input value (`YYYY-MM-DD`); the API takes ISO strings. */
function toDateInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function toForm(product: AdminProduct): FormState {
  return {
    id: product.id,
    name: product.name,
    category: product.category,
    price: String(product.price),
    old_price: product.oldPrice ? String(product.oldPrice) : "",
    sizes: product.sizes.join(", "),
    colors: product.colors.map((c) => `${c.name} ${c.hex}`).join(", "),
    images: product.rawImages,
    material: product.material,
    description: product.description,
    stock: String(product.stock),
    is_new: product.isNew ?? true,
    active: product.active ?? true,
    tags: product.tags.join(", "),
    badge: product.badge ?? "",
    availability: product.availability ?? "in_stock",
    available_at: toDateInput(product.availableAt),
    low_stock_threshold: String(product.lowStockThreshold ?? 5),
  };
}

function parsePayload(form: FormState) {
  return {
    name: form.name,
    category: form.category,
    price: Number(form.price),
    old_price: form.old_price ? Number(form.old_price) : null,
    sizes: form.sizes
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    colors: form.colors
      .split(",")
      .map((chunk) => chunk.trim())
      .filter(Boolean)
      .map((chunk) => {
        const parts = chunk.split(/\s+/);
        const hex = parts.pop() ?? "#cccccc";
        return { name: parts.join(" ") || "رنگ", hex };
      }),
    images: form.images,
    material: form.material,
    description: form.description,
    stock: Number(form.stock),
    is_new: form.is_new,
    active: form.active,
    tags: form.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    badge: form.badge === "" ? null : form.badge,
    availability: form.availability,
    // only meaningful for coming_soon / preorder; cleared otherwise
    available_at: form.availability === "in_stock" || !form.available_at ? null : form.available_at,
    low_stock_threshold: Number(form.low_stock_threshold) || 0,
  };
}

function AdminProducts() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);
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

  const save = useMutation({
    mutationFn: async (state: FormState) => {
      const payload = parsePayload(state);
      if (state.id) {
        await api.updateProduct(state.id, payload);
      } else {
        await api.createProduct(payload);
      }
    },
    onSuccess: () => {
      invalidate();
      setForm(null);
      toast.success("محصول ذخیره شد");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "ذخیره نشد"),
  });

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
          <Button onClick={() => setForm(emptyForm)} className="gap-2">
            <Plus className="size-4" /> محصول جدید
          </Button>
        </div>
      </div>

      {form && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(form);
          }}
          className="grid gap-4 rounded-3xl bg-sand p-6 md:grid-cols-2"
        >
          <div className="md:col-span-2 flex items-center justify-between">
            <h3 className="text-lg">{form.id ? "ویرایش محصول" : "افزودن محصول"}</h3>
            <button
              type="button"
              onClick={() => setForm(null)}
              className="text-xs text-muted-foreground"
            >
              بستن
            </button>
          </div>
          <div>
            <Label>نام</Label>
            <Input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>دسته‌بندی</Label>
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="mt-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>قیمت (تومان)</Label>
            <Input
              required
              dir="ltr"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>قیمت قبل از تخفیف</Label>
            <Input
              dir="ltr"
              value={form.old_price}
              onChange={(e) => setForm({ ...form, old_price: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>سایزها (با کاما)</Label>
            <Input
              value={form.sizes}
              onChange={(e) => setForm({ ...form, sizes: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>موجودی</Label>
            <Input
              dir="ltr"
              value={form.stock}
              onChange={(e) => setForm({ ...form, stock: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>رنگ‌ها (نام و کد رنگ، جدا شده با کاما)</Label>
            <Input
              value={form.colors}
              onChange={(e) => setForm({ ...form, colors: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>گالری تصاویر</Label>
            <div className="mt-3">
              <ProductImageManager
                value={form.images}
                onChange={(images) => setForm({ ...form, images })}
              />
            </div>
          </div>
          <div>
            <Label>برچسب‌ها (با کاما)</Label>
            <Input
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              placeholder="کتان, تابستانی"
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>نشان محصول</Label>
            <select
              value={form.badge}
              onChange={(e) => setForm({ ...form, badge: e.target.value as FormState["badge"] })}
              className="mt-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {BADGES.map((badge) => (
                <option key={badge.value} value={badge.value}>
                  {badge.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>وضعیت عرضه</Label>
            <select
              value={form.availability}
              onChange={(e) => setForm({ ...form, availability: e.target.value as Availability })}
              className="mt-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {AVAILABILITIES.map((availability) => (
                <option key={availability.value} value={availability.value}>
                  {availability.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>تاریخ عرضه (برای به‌زودی / پیش‌خرید)</Label>
            <Input
              type="date"
              dir="ltr"
              disabled={form.availability === "in_stock"}
              value={form.available_at}
              onChange={(e) => setForm({ ...form, available_at: e.target.value })}
              className="mt-2 bg-background disabled:opacity-50"
            />
          </div>
          <div>
            <Label>آستانه هشدار موجودی کم</Label>
            <Input
              dir="ltr"
              inputMode="numeric"
              value={form.low_stock_threshold}
              onChange={(e) => setForm({ ...form, low_stock_threshold: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>جنس</Label>
            <Input
              value={form.material}
              onChange={(e) => setForm({ ...form, material: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>توضیحات</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="flex items-center gap-6 md:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_new}
                onChange={(e) => setForm({ ...form, is_new: e.target.checked })}
              />
              محصول جدید
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm({ ...form, active: e.target.checked })}
              />
              نمایش در فروشگاه
            </label>
          </div>
          <Button type="submit" disabled={save.isPending} className="md:col-span-2">
            ذخیره محصول
          </Button>
        </form>
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
                    onClick={() => setForm(toForm(product))}
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
