import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Minus, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type StockIssue } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { formatToman, toFa } from "@/lib/format";
import { useCart, useCartSubtotal, type CartLine } from "@/lib/cart";
import { stockIssueMessage } from "@/lib/stock-issues";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/cart")({
  head: () => ({
    meta: [
      { title: "سبد خرید — ساندِه" },
      { name: "description", content: "مرور و ویرایش سبد خرید شما در فروشگاه ساندِه." },
      { property: "og:title", content: "سبد خرید — ساندِه" },
      { property: "og:description", content: "مرور و ویرایش سبد خرید." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: CartPage,
});

const SHIPPING = 89000;
const FREE_SHIPPING_FROM = 2000000;

/**
 * Attach each reported issue to a cart line.
 *
 * `StockIssue` carries the product id but not the size/colour, so when a product
 * occupies a single line the issue is attached there. When the same product is in
 * several lines the issue goes to the lines its `available` count cannot satisfy,
 * which keeps a valid size/colour from being flagged by a sibling's shortage.
 */
function issuesForLines(lines: CartLine[], issues: StockIssue[]): (StockIssue | undefined)[] {
  const byProduct = new Map<string, StockIssue[]>();
  for (const issue of issues) {
    byProduct.set(issue.product_id, [...(byProduct.get(issue.product_id) ?? []), issue]);
  }
  const lineCount = new Map<string, number>();
  for (const line of lines) {
    lineCount.set(line.productId, (lineCount.get(line.productId) ?? 0) + 1);
  }

  return lines.map((line) => {
    const candidates = byProduct.get(line.productId);
    if (!candidates?.length) return undefined;
    if (lineCount.get(line.productId) === 1) return candidates[0];
    return candidates.find(
      (issue) => issue.available == null || issue.available <= 0 || line.quantity > issue.available,
    );
  });
}

function CartPage() {
  const { lines, setQuantity, remove } = useCart();
  const subtotal = useCartSubtotal();
  const { byId } = useCatalog();
  const [code, setCode] = useState("");
  const [discount, setDiscount] = useState(0);

  // `POST /stock/check` — authoritative, variant-aware stock for the whole cart.
  // The query key includes every line and quantity, so any edit re-validates;
  // React Query keeps the previous result rendered while the new one is in flight.
  const stockKey = lines
    .map((line) => `${line.productId}:${line.size}:${line.color}:${line.quantity}`)
    .join("|");
  const stock = useQuery({
    queryKey: ["cart-stock", stockKey],
    enabled: lines.length > 0,
    queryFn: () =>
      api.stockCheck(
        lines.map((line) => ({
          product_id: line.productId,
          size: line.size,
          color: line.color,
          quantity: line.quantity,
        })),
      ),
  });
  const issues = issuesForLines(lines, stock.data?.issues ?? []);
  const blocked = stock.data ? !stock.data.ok : false;

  const shipping = subtotal === 0 || subtotal >= FREE_SHIPPING_FROM ? 0 : SHIPPING;
  const total = Math.max(0, subtotal - discount) + shipping;

  const applyCode = async () => {
    const trimmed = code.trim();
    if (!trimmed) return;
    try {
      const result = await api.validateCoupon(trimmed, subtotal);
      setDiscount(result.discount);
      // checkout sends the code (never the amount) so the discount is recomputed server-side
      window.sessionStorage.setItem("sandeh-coupon", result.code);
      toast.success("کد تخفیف اعمال شد");
    } catch (error) {
      setDiscount(0);
      window.sessionStorage.removeItem("sandeh-coupon");
      toast.error(error instanceof Error ? error.message : "کد تخفیف معتبر نیست");
    }
  };

  if (lines.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center sm:px-6">
        <h1 className="text-3xl">سبد خرید شما خالی است</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          از کالکشن جدید شروع کنید و تکه‌های مورد علاقه‌تان را اضافه کنید.
        </p>
        <Link
          to="/shop"
          search={{}}
          className="mt-8 inline-flex border border-foreground px-8 py-3 text-sm tracking-widest transition-colors hover:bg-foreground hover:text-background"
        >
          رفتن به فروشگاه
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">سبد خرید</h1>

      <div className="mt-10 grid gap-12 md:grid-cols-[1fr_320px]">
        <ul className="divide-y divide-border border-y border-border">
          {lines.map((line, index) => {
            const product = byId(line.productId);
            const issue = issues[index];
            const lineKey = `${line.productId}-${line.size}-${line.color}`;

            // A line whose product is gone from the active catalog used to
            // render nothing at all, leaving it impossible to remove.
            if (!product) {
              return (
                <li key={lineKey} className="flex items-center gap-4 py-6">
                  <div className="flex-1">
                    <h2 className="font-display text-lg">محصول حذف‌شده</h2>
                    <p className="mt-1 text-xs text-terracotta">
                      {issue ? stockIssueMessage(issue) : "این محصول دیگر در فروشگاه نیست."}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" /> حذف
                  </button>
                </li>
              );
            }
            return (
              <li key={lineKey} className="flex gap-4 py-6">
                <Link to="/product/$id" params={{ id: product.id }} className="w-24 shrink-0">
                  <img
                    src={product.images[0]}
                    alt={product.name}
                    loading="lazy"
                    className="h-32 w-full object-cover"
                  />
                </Link>
                <div className="flex-1">
                  <Link to="/product/$id" params={{ id: product.id }}>
                    <h2 className="font-display text-lg">{product.name}</h2>
                  </Link>
                  <p className="mt-1 text-xs text-muted-foreground">
                    سایز {toFa(line.size)} · رنگ {line.color}
                  </p>
                  {issue && (
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-terracotta">
                      <AlertTriangle className="size-3.5 shrink-0" />
                      {stockIssueMessage(issue, product)}
                    </p>
                  )}
                  <div className="mt-4 flex items-center gap-4">
                    <div className="flex items-center border border-border">
                      <button
                        type="button"
                        aria-label="کاهش"
                        onClick={() => setQuantity(index, line.quantity - 1)}
                        className="p-2"
                      >
                        <Minus className="size-3.5" />
                      </button>
                      <span className="w-8 text-center text-sm">{toFa(line.quantity)}</span>
                      <button
                        type="button"
                        aria-label="افزایش"
                        onClick={() => setQuantity(index, line.quantity + 1)}
                        className="p-2"
                      >
                        <Plus className="size-3.5" />
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => remove(index)}
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" /> حذف
                    </button>
                  </div>
                </div>
                <p className="shrink-0 text-sm">
                  {formatToman(product.price * line.quantity)} تومان
                </p>
              </li>
            );
          })}
        </ul>

        <aside className="h-fit bg-sand p-6">
          <h2 className="text-xl">خلاصه سفارش</h2>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">جمع کالاها</dt>
              <dd>{formatToman(subtotal)} تومان</dd>
            </div>
            {discount > 0 && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">تخفیف</dt>
                <dd>−{formatToman(discount)} تومان</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-muted-foreground">ارسال</dt>
              <dd>{shipping === 0 ? "رایگان" : `${formatToman(shipping)} تومان`}</dd>
            </div>
            <div className="flex justify-between border-t border-border pt-3 text-base">
              <dt>مبلغ نهایی</dt>
              <dd>{formatToman(total)} تومان</dd>
            </div>
          </dl>

          {stock.isFetching && (
            <p className="mt-3 text-[11px] text-muted-foreground">در حال بررسی موجودی…</p>
          )}
          {stock.isError && (
            <p className="mt-3 text-[11px] text-muted-foreground">
              بررسی موجودی انجام نشد؛ پیش از پرداخت دوباره تلاش می‌شود.
            </p>
          )}
          {blocked && (
            <div className="mt-4 flex items-start gap-2 border border-terracotta/40 bg-terracotta/5 p-3 text-xs text-terracotta">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>
                موجودی این اقلام تغییر کرده است. تعداد یا ترکیب‌های ناموجود را اصلاح کنید تا بتوانید
                سفارش را تکمیل کنید.
              </span>
            </div>
          )}

          <div className="mt-6 flex gap-2">
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="کد تخفیف"
              className="rounded-none bg-background"
            />
            <Button variant="outline" className="rounded-none" onClick={applyCode}>
              ثبت
            </Button>
          </div>

          {blocked ? (
            <span
              aria-disabled="true"
              className="mt-6 block cursor-not-allowed bg-foreground/35 py-3 text-center text-sm tracking-widest text-background"
            >
              تکمیل خرید
            </span>
          ) : (
            <Link
              to="/checkout"
              className="mt-6 block bg-foreground py-3 text-center text-sm tracking-widest text-background transition-opacity hover:opacity-90"
            >
              تکمیل خرید
            </Link>
          )}
        </aside>
      </div>
    </div>
  );
}
