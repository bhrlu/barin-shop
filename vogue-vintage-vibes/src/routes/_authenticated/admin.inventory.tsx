import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, PackageX } from "lucide-react";
import { api } from "@/lib/api";
import { categoryTitle, type CategoryId } from "@/data/products";
import { formatToman, toFa } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/admin/inventory")({
  component: AdminInventory,
});

/**
 * Inventory health: aggregate counts from `GET /admin/inventory` and the
 * low-stock report from `GET /admin/inventory/low-stock`. The threshold input
 * overrides each product's own `low_stock_threshold` when filled.
 */
function AdminInventory() {
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

  const cards = [
    { label: "محصولات فعال", value: toFa(summary.data?.totalProducts ?? 0) },
    { label: "کل واحدها", value: toFa(summary.data?.totalUnits ?? 0) },
    { label: "ارزش انبار", value: `${formatToman(summary.data?.inventoryValue ?? 0)} تومان` },
    { label: "ناموجود", value: toFa(summary.data?.outOfStock ?? 0), danger: true },
    { label: "موجودی کم", value: toFa(summary.data?.lowStock ?? 0), danger: true },
    { label: "تنوع‌های فعال", value: toFa(summary.data?.totalVariants ?? 0) },
  ];

  const products = lowStock.data?.products ?? [];
  const variants = lowStock.data?.variants ?? [];

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
                      <span
                        className={
                          product.stock <= 0
                            ? "rounded-full bg-terracotta/10 px-3 py-1 text-xs text-terracotta"
                            : "rounded-full bg-sand px-3 py-1 text-xs"
                        }
                      >
                        {toFa(product.stock)} عدد
                      </span>
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
                      <span
                        className={
                          variant.stock <= 0
                            ? "rounded-full bg-terracotta/10 px-3 py-1 text-xs text-terracotta"
                            : "rounded-full bg-sand px-3 py-1 text-xs"
                        }
                      >
                        {toFa(variant.stock)} عدد
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
