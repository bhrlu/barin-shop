import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { AlertTriangle, History, PackageX } from "lucide-react";
import { api, type InventoryLogEntry, type InventoryReason } from "@/lib/api";
import { categoryTitle, type CategoryId } from "@/data/products";
import { formatFaDateTime, formatToman, toFa } from "@/lib/format";
import { AdminDataTable, CopyValue } from "@/components/admin/AdminDataTable";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Rows per page of the ledger (the endpoint's own default is 25). */
const PAGE_SIZE = 20;

/** Mirrors `REASONS` in backend/app/services/inventory_log.py. An unknown reason
 * still renders (raw name); it just can't be picked from the filter. */
const REASONS: { value: InventoryReason; label: string }[] = [
  { value: "purchase", label: "خرید مشتری" },
  { value: "restock", label: "ورود به انبار" },
  { value: "return", label: "بازگشت (لغو سفارش)" },
  { value: "manual_adjustment", label: "اصلاح دستی" },
];

const REASON_LABELS: Record<string, string> = Object.fromEntries(
  REASONS.map((reason) => [reason.value, reason.label]),
);

const REASON_VALUES = REASONS.map((reason) => reason.value);

/**
 * URL state (F5.19): page + the ledger's server-side filters, so a product /
 * variant history link is shareable and refresh-safe. Invalid values become
 * `undefined` — returned explicitly, never omitted, because the router merges
 * this route's validated search over the parent's raw one (see
 * `admin.products.tsx` / DESIGN_SYSTEM).
 */
type InventorySearch = {
  page?: number | undefined;
  reason?: InventoryReason | undefined;
  product_id?: string | undefined;
  variant_id?: string | undefined;
};

/** Drops cleared keys so the URL never carries `?product_id=undefined`. */
function cleanSearch(next: InventorySearch): InventorySearch {
  return Object.fromEntries(
    Object.entries(next).filter(([, value]) => value !== undefined),
  ) as InventorySearch;
}

export const Route = createFileRoute("/_authenticated/admin/inventory")({
  validateSearch: (search: Record<string, unknown>): InventorySearch => {
    const page = Number(search["page"]);
    const reason = search["reason"];
    const productId = search["product_id"];
    const variantId = search["variant_id"];
    return {
      page: Number.isInteger(page) && page > 1 ? page : undefined,
      reason: REASON_VALUES.includes(reason as InventoryReason)
        ? (reason as InventoryReason)
        : undefined,
      product_id: typeof productId === "string" && productId.trim() ? productId : undefined,
      variant_id: typeof variantId === "string" && variantId.trim() ? variantId : undefined,
    };
  },
  component: AdminInventory,
});

/**
 * Inventory health: aggregate counts from `GET /admin/inventory`, the low-stock
 * report from `GET /admin/inventory/low-stock` (the threshold input overrides each
 * product's own `low_stock_threshold` when filled) and the append-only stock
 * ledger from `GET /admin/inventory/logs`.
 */
function AdminInventory() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const [threshold, setThreshold] = useState("");

  const summary = useQuery({
    queryKey: ["admin-inventory"],
    queryFn: () => api.inventory(),
  });

  const parsedThreshold = threshold.trim() === "" ? undefined : Number(threshold);
  const lowStock = useQuery({
    queryKey: ["admin-low-stock", parsedThreshold ?? "default"],
    queryFn: () => api.lowStock(parsedThreshold),
  });

  const page = search.page ?? 1;
  const { reason, product_id: productId, variant_id: variantId } = search;
  const ledger = useQuery({
    queryKey: ["admin-inventory-logs", page, reason ?? null, productId ?? null, variantId ?? null],
    queryFn: () =>
      api.inventoryLogs({
        page,
        pageSize: PAGE_SIZE,
        ...(reason ? { reason } : {}),
        ...(productId ? { productId } : {}),
        ...(variantId ? { variantId } : {}),
      }),
    placeholderData: keepPreviousData,
  });
  const entries = ledger.data?.items ?? [];

  /** Any filter change starts from page 1; a patch that names a page (the pager) wins. */
  const setSearch = (patch: InventorySearch) =>
    void navigate({ search: (prev) => cleanSearch({ ...prev, page: undefined, ...patch }) });

  /** One product's (or variant's) history: the ledger is filtered by the URL. */
  const historySearch = (next: { product_id: string; variant_id?: string }): InventorySearch =>
    cleanSearch({
      ...search,
      product_id: next.product_id,
      variant_id: next.variant_id,
      page: undefined,
    });

  // the scope banner names the filter from the rows themselves — the ledger joins
  // the product / variant names, and falls back to the raw id if nothing matched
  const scopeRow = entries[0];
  const scopeLabel = !productId
    ? null
    : variantId
      ? scopeRow?.product_name
        ? `${scopeRow.product_name} · سایز ${toFa(scopeRow.size ?? "—")} · رنگ ${scopeRow.color ?? "—"}`
        : variantId
      : (scopeRow?.product_name ?? productId);

  const columns: ColumnDef<InventoryLogEntry>[] = [
    {
      id: "change",
      header: "تغییر",
      enableSorting: false,
      cell: ({ row }) => {
        const change = row.original.change_amount;
        return (
          <span
            dir="ltr"
            className={`font-mono whitespace-nowrap ${
              change < 0 ? "text-terracotta" : "text-sage-deep"
            }`}
          >
            {change < 0 ? "−" : "+"}
            {toFa(Math.abs(change))}
          </span>
        );
      },
    },
    {
      id: "reason",
      header: "دلیل",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="rounded-full bg-sand px-2.5 py-0.5 text-xs whitespace-nowrap">
          {REASON_LABELS[row.original.reason] ?? row.original.reason}
        </span>
      ),
    },
    {
      id: "item",
      header: "کالا",
      enableSorting: false,
      cell: ({ row }) => {
        const entry = row.original;
        return (
          <div className="min-w-44">
            <Link
              to="/admin/inventory"
              search={historySearch({ product_id: entry.product_id })}
              title="تاریخچهٔ این محصول"
              className="underline-offset-4 hover:text-terracotta hover:underline"
            >
              {entry.product_name ?? "محصول حذف‌شده"}
            </Link>
            <p className="mt-1 text-xs text-muted-foreground">
              {entry.variant_id
                ? `سایز ${toFa(entry.size ?? "—")} · رنگ ${entry.color ?? "—"}`
                : "موجودی کل محصول"}
            </p>
          </div>
        );
      },
    },
    {
      id: "order",
      header: "سفارش",
      enableSorting: false,
      cell: ({ row }) => <CopyValue value={row.original.order_number} label="شماره سفارش" />,
    },
    {
      id: "actor",
      header: "ثبت‌کننده",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground" dir="ltr">
          {row.original.created_by_email ?? "—"}
        </span>
      ),
    },
    {
      id: "created_at",
      header: "زمان",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="text-xs whitespace-nowrap">
          {formatFaDateTime(row.original.created_at) || "—"}
        </span>
      ),
    },
  ];

  const products = lowStock.data?.products ?? [];
  const variants = lowStock.data?.variants ?? [];

  const cards = [
    { label: "محصولات فعال", value: toFa(summary.data?.totalProducts ?? 0) },
    { label: "کل واحدها", value: toFa(summary.data?.totalUnits ?? 0) },
    { label: "ارزش انبار", value: `${formatToman(summary.data?.inventoryValue ?? 0)} تومان` },
    { label: "ناموجود", value: toFa(summary.data?.outOfStock ?? 0), danger: true },
    { label: "موجودی کم", value: toFa(summary.data?.lowStock ?? 0), danger: true },
    { label: "تنوع‌های فعال", value: toFa(summary.data?.totalVariants ?? 0) },
  ];

  return (
    <div className="space-y-10">
      {summary.isError ? (
        <p className="text-sm text-terracotta">خواندن وضعیت انبار انجام نشد.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card) => (
            <div key={card.label} className="rounded-3xl bg-sand p-6">
              <p className="text-xs text-muted-foreground">{card.label}</p>
              <p
                className={`mt-2 text-2xl ${card.danger && card.value !== toFa(0) ? "text-terracotta" : "text-sage-deep"}`}
              >
                {summary.isLoading ? "…" : card.value}
              </p>
            </div>
          ))}
        </div>
      )}

      <section>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-lg">هشدار موجودی کم</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              محصولات و تنوع‌های هم‌تراز یا کم‌تر از آستانه هر محصول.
            </p>
          </div>
          <div className="w-48">
            <Label htmlFor="threshold" className="text-xs">
              آستانه دلخواه (اختیاری)
            </Label>
            <Input
              id="threshold"
              dir="ltr"
              inputMode="numeric"
              placeholder="آستانه هر محصول"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="mt-2 h-9 bg-background"
            />
          </div>
        </div>

        {lowStock.isLoading ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-14 animate-pulse rounded-xl bg-clay" />
            ))}
          </div>
        ) : lowStock.isError ? (
          <p className="mt-6 text-sm text-terracotta">خواندن گزارش انجام نشد.</p>
        ) : (
          <div className="mt-6 grid gap-8 lg:grid-cols-2">
            <div>
              <h3 className="flex items-center gap-2 text-sm">
                <AlertTriangle className="size-4 text-terracotta" />
                محصولات ({toFa(products.length)})
              </h3>
              {products.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">هیچ محصولی زیر آستانه نیست.</p>
              ) : (
                <ul className="mt-3 divide-y divide-border rounded-3xl border border-border">
                  {products.map((product) => (
                    <li
                      key={product.id}
                      className="flex items-center justify-between gap-3 p-4 text-sm"
                    >
                      <div>
                        <p>{product.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {categoryTitle(product.category as CategoryId)} · آستانه{" "}
                          {toFa(product.low_stock_threshold)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Link
                          to="/admin/inventory"
                          search={historySearch({ product_id: product.id })}
                          title="تاریخچهٔ موجودی این محصول"
                          className="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta"
                        >
                          <History className="size-3.5" aria-hidden />
                          تاریخچه
                        </Link>
                        <span
                          className={
                            product.stock <= 0
                              ? "rounded-full bg-terracotta/10 px-3 py-1 text-xs text-terracotta"
                              : "rounded-full bg-sand px-3 py-1 text-xs"
                          }
                        >
                          {toFa(product.stock)} عدد
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="flex items-center gap-2 text-sm">
                <PackageX className="size-4 text-terracotta" />
                تنوع‌ها ({toFa(variants.length)})
              </h3>
              {variants.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">هیچ تنوعی زیر آستانه نیست.</p>
              ) : (
                <ul className="mt-3 divide-y divide-border rounded-3xl border border-border">
                  {variants.map((variant) => (
                    <li
                      key={variant.id}
                      className="flex items-center justify-between gap-3 p-4 text-sm"
                    >
                      <div>
                        <p>{variant.product_name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          سایز {toFa(variant.size)} · رنگ {variant.color}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Link
                          to="/admin/inventory"
                          search={historySearch({
                            product_id: variant.product_id,
                            variant_id: variant.id,
                          })}
                          title="تاریخچهٔ موجودی این تنوع"
                          className="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta"
                        >
                          <History className="size-3.5" aria-hidden />
                          تاریخچه
                        </Link>
                        <span
                          className={
                            variant.stock <= 0
                              ? "rounded-full bg-terracotta/10 px-3 py-1 text-xs text-terracotta"
                              : "rounded-full bg-sand px-3 py-1 text-xs"
                          }
                        >
                          {toFa(variant.stock)} عدد
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-lg">دفتر انبار</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              هر جابه‌جایی موجودی، از جدید به قدیم: خرید مشتری، ورود به انبار، بازگشت پس از لغو
              سفارش و اصلاح دستی کارکنان. این دفتر فقط افزودنی است.
            </p>
          </div>
          {scopeLabel ? (
            <p className="flex flex-wrap items-center gap-2 rounded-full bg-sand px-3 py-1 text-xs">
              <History className="size-3.5" aria-hidden />
              تاریخچهٔ «{scopeLabel}»
              <button
                type="button"
                onClick={() => setSearch({ product_id: undefined, variant_id: undefined })}
                className="underline underline-offset-4 hover:text-terracotta"
              >
                نمایش همه
              </button>
            </p>
          ) : null}
        </div>

        <div className="mt-6">
          <AdminDataTable
            caption="دفتر انبار"
            columns={columns}
            data={entries}
            getRowId={(entry) => entry.id}
            page={ledger.data?.page ?? page}
            pages={ledger.data?.pages ?? 1}
            total={ledger.data?.total}
            onPageChange={(next) => setSearch({ page: next > 1 ? next : undefined })}
            filters={[
              {
                id: "reason",
                label: "دلیل",
                multiple: false,
                options: REASONS,
                selected: reason ? [reason] : [],
                onChange: (next) => setSearch({ reason: next[0] as InventoryReason | undefined }),
              },
            ]}
            isLoading={ledger.isLoading}
            isFetching={ledger.isFetching}
            isError={ledger.isError}
            onRetry={() => void ledger.refetch()}
            emptyMessage={
              reason || productId || variantId
                ? "حرکتی با این فیلترها ثبت نشده است."
                : "هنوز حرکتی در دفتر انبار ثبت نشده است."
            }
          />
        </div>
      </section>
    </div>
  );
}
