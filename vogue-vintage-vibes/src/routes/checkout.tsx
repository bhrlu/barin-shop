import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { api, ApiError, type StockIssue } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";
import { useCart, useCartQuote } from "@/lib/cart";
import { useAuth } from "@/lib/auth";
import { useCatalog } from "@/lib/catalog";
import { stockIssueLabel } from "@/lib/stock-issues";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/checkout")({
  head: () => ({
    meta: [
      { title: "تکمیل خرید — ساندِه" },
      { name: "description", content: "ثبت اطلاعات ارسال و نهایی کردن سفارش در ساندِه." },
      { property: "og:title", content: "تکمیل خرید — ساندِه" },
      { property: "og:description", content: "ثبت اطلاعات ارسال و نهایی کردن سفارش." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: CheckoutPage,
});

const SHIPPING = 89000;
const FREE_SHIPPING_FROM = 2000000;

function CheckoutPage() {
  const { lines, clear } = useCart();
  // F5.18: the server's quote (variant prices included), shared with the cart page
  const quote = useCartQuote();
  const subtotal = quote.data?.subtotal;
  const { user, loading } = useAuth();
  const { byId } = useCatalog();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const shipping = subtotal !== undefined && subtotal >= FREE_SHIPPING_FROM ? 0 : SHIPPING;
  const pending = (
    <span
      aria-label="در حال محاسبه"
      className="inline-block h-4 w-20 animate-pulse rounded bg-clay align-middle"
    />
  );
  const failedOrPending = quote.isError ? "—" : pending;

  // saved addresses pre-fill the form; the default one is picked automatically
  // and the customer can switch to another (or back to a blank form)
  const { data: savedAddresses } = useQuery({
    queryKey: ["addresses"],
    queryFn: () => api.addresses(),
    enabled: Boolean(user),
  });
  const [pickedId, setPickedId] = useState<string | null>(null);
  const saved = savedAddresses ?? [];
  const picked = pickedId
    ? (saved.find((address) => address.id === pickedId) ?? null)
    : (saved.find((address) => address.is_default) ?? null);
  const [pickedFirst, ...pickedRest] = (picked?.receiver ?? "").trim().split(/\s+/);

  if (lines.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
        <h1 className="text-3xl">سبد خرید خالی است</h1>
        <Link
          to="/shop"
          search={{}}
          className="mt-8 inline-flex border border-foreground px-8 py-3 text-sm tracking-widest"
        >
          رفتن به فروشگاه
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">تکمیل خرید</h1>

      <div className="mt-10 grid gap-12 md:grid-cols-[1fr_320px]">
        <form
          className="space-y-5"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!user) return;
            const data = new FormData(event.currentTarget as HTMLFormElement);
            setBusy(true);
            try {
              const couponCode = window.sessionStorage.getItem("sandeh-coupon");
              const order = await api.checkout({
                lines: lines.map((line) => ({
                  product_id: line.productId,
                  size: line.size,
                  color: line.color,
                  quantity: line.quantity,
                })),
                coupon_code: couponCode,
                address: {
                  full_name: `${data.get("firstName")} ${data.get("lastName")}`,
                  phone: String(data.get("phone") ?? ""),
                  province: String(data.get("province") ?? "") || null,
                  city: String(data.get("city") ?? ""),
                  line: String(data.get("address") ?? ""),
                  postal_code: String(data.get("postal") ?? ""),
                  note: String(data.get("note") ?? "") || null,
                },
              });
              window.sessionStorage.removeItem("sandeh-coupon");
              clear();
              navigate({ to: "/payment/$orderId", params: { orderId: order.order_id } });
            } catch (error) {
              const detail = error instanceof ApiError ? error.detail : null;
              const issues =
                detail &&
                typeof detail === "object" &&
                "code" in detail &&
                (detail as { code?: string }).code === "stock_conflict" &&
                "issues" in detail
                  ? ((detail as { issues?: StockIssue[] }).issues ?? [])
                  : [];
              if (issues.length) {
                // each reason has its own copy: a deactivated variant or an
                // unreleased product is not a stock count problem
                const message = issues
                  .map((issue) => {
                    const product = byId(issue.product_id);
                    const name = product?.name ?? issue.product_id;
                    return `${name} — ${stockIssueLabel(issue)}`;
                  })
                  .join("، ");
                toast.error(`برخی اقلام قابل سفارش نیستند: ${message}`);
              } else {
                toast.error(error instanceof Error ? error.message : "ثبت سفارش ناموفق بود");
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          {saved.length > 0 && (
            <div className="bg-sand p-4">
              <p className="text-xs text-muted-foreground">آدرس‌های ذخیره‌شده</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {saved.map((address) => (
                  <button
                    key={address.id}
                    type="button"
                    aria-pressed={picked?.id === address.id}
                    onClick={() => setPickedId(address.id)}
                    className={`border px-3 py-1.5 text-xs transition-colors ${
                      picked?.id === address.id
                        ? "border-terracotta bg-background"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {address.title}
                    {address.is_default ? " · پیش‌فرض" : ""}
                  </button>
                ))}
                <button
                  type="button"
                  aria-pressed={picked === null}
                  onClick={() => setPickedId("none")}
                  className={`border px-3 py-1.5 text-xs transition-colors ${
                    picked === null
                      ? "border-terracotta bg-background"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  آدرس جدید
                </button>
              </div>
            </div>
          )}
          {/* remount on switch so the uncontrolled fields take the new defaults */}
          <div key={picked?.id ?? "new"} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <Label htmlFor="firstName">نام</Label>
                <Input
                  id="firstName"
                  name="firstName"
                  required
                  defaultValue={pickedFirst ?? ""}
                  className="mt-2 rounded-none"
                />
              </div>
              <div>
                <Label htmlFor="lastName">نام خانوادگی</Label>
                <Input
                  id="lastName"
                  name="lastName"
                  required
                  defaultValue={pickedRest.join(" ")}
                  className="mt-2 rounded-none"
                />
              </div>
            </div>
            <div className="grid gap-5 sm:grid-cols-3">
              <div>
                <Label htmlFor="phone">شماره تماس</Label>
                <Input
                  id="phone"
                  name="phone"
                  required
                  inputMode="tel"
                  defaultValue={picked?.phone ?? ""}
                  className="mt-2 rounded-none"
                />
              </div>
              <div>
                <Label htmlFor="province">استان</Label>
                <Input
                  id="province"
                  name="province"
                  defaultValue={picked?.province ?? ""}
                  className="mt-2 rounded-none"
                />
              </div>
              <div>
                <Label htmlFor="city">شهر</Label>
                <Input
                  id="city"
                  name="city"
                  required
                  defaultValue={picked?.city ?? ""}
                  className="mt-2 rounded-none"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="address">نشانی کامل</Label>
              <Textarea
                id="address"
                name="address"
                required
                rows={3}
                defaultValue={picked?.line ?? ""}
                className="mt-2 rounded-none"
              />
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <Label htmlFor="postal">کد پستی</Label>
                <Input
                  id="postal"
                  name="postal"
                  required
                  inputMode="numeric"
                  defaultValue={picked?.postal_code ?? ""}
                  className="mt-2 rounded-none"
                />
              </div>
              <div>
                <Label htmlFor="note">یادداشت سفارش (اختیاری)</Label>
                <Input id="note" name="note" className="mt-2 rounded-none" />
              </div>
            </div>
          </div>
          {user ? (
            <Button
              type="submit"
              disabled={busy}
              className="h-11 w-full rounded-none text-sm tracking-widest"
            >
              {busy ? "در حال انتقال به درگاه…" : "ثبت سفارش و پرداخت"}
            </Button>
          ) : (
            <Link
              to="/auth"
              search={{ redirect: "/checkout" }}
              className="flex h-11 w-full items-center justify-center bg-primary text-sm tracking-widest text-primary-foreground"
            >
              {loading ? "..." : "برای ثبت سفارش وارد شوید"}
            </Link>
          )}
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-4 shrink-0 text-sage-deep" />
            پس از ثبت سفارش به درگاه پرداخت آزمایشی منتقل می‌شوید؛ نتیجه‌ی پرداخت روی سفارش ثبت و در
            حساب کاربری قابل پیگیری است.
          </p>
        </form>

        <aside className="h-fit bg-sand p-6">
          <h2 className="text-xl">سفارش شما</h2>
          <ul className="mt-5 space-y-4 text-sm">
            {lines.map((line) => {
              const product = byId(line.productId);
              if (!product) return null;
              const unitPrice = quote.data?.priceOf(line);
              return (
                <li
                  key={`${line.productId}-${line.size}-${line.color}`}
                  className="flex justify-between gap-3"
                >
                  <span className="text-muted-foreground">
                    {product.name} × {toFa(line.quantity)}
                    <br />
                    <span className="text-xs">
                      سایز {toFa(line.size)} · {line.color}
                    </span>
                  </span>
                  <span>
                    {unitPrice == null ? failedOrPending : formatToman(unitPrice * line.quantity)}
                  </span>
                </li>
              );
            })}
          </ul>
          <dl className="mt-6 space-y-3 border-t border-border pt-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">ارسال</dt>
              <dd>
                {subtotal === undefined
                  ? failedOrPending
                  : shipping === 0
                    ? "رایگان"
                    : `${formatToman(shipping)} تومان`}
              </dd>
            </div>
            <div className="flex justify-between text-base">
              <dt>مبلغ نهایی</dt>
              <dd>
                {subtotal === undefined
                  ? failedOrPending
                  : `${formatToman(subtotal + shipping)} تومان`}
              </dd>
            </div>
          </dl>
        </aside>
      </div>
    </div>
  );
}
