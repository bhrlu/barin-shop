import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { completePayment, getPaymentSession } from "@/lib/payment.functions";
import { formatToman, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_authenticated/payment/$orderId")({
  head: () => ({
    meta: [
      { title: "درگاه پرداخت — ساندِه" },
      { name: "description", content: "پرداخت سفارش ساندِه در درگاه آزمایشی." },
      { property: "og:title", content: "درگاه پرداخت — ساندِه" },
      { property: "og:description", content: "پرداخت سفارش ساندِه در درگاه آزمایشی." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: PaymentPage,
});

function PaymentPage() {
  const { orderId } = Route.useParams();
  const navigate = useNavigate();
  const session = useServerFn(getPaymentSession);
  const complete = useServerFn(completePayment);
  const [busy, setBusy] = useState<"success" | "failure" | null>(null);
  const [result, setResult] = useState<{ ok: boolean; reference: string | null } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["payment-session", orderId],
    queryFn: () => session({ data: { orderId } }),
    retry: false,
  });

  async function pay(outcome: "success" | "failure") {
    setBusy(outcome);
    try {
      const res = await complete({ data: { orderId, outcome } });
      setResult({ ok: res.ok, reference: res.reference });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "خطا در ارتباط با درگاه");
    } finally {
      setBusy(null);
    }
  }

  if (isLoading)
    return (
      <div className="mx-auto flex max-w-md items-center justify-center px-4 py-32">
        <Loader2 className="size-6 animate-spin text-terracotta" />
      </div>
    );

  if (error || !data)
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="text-3xl">سفارش پیدا نشد</h1>
        <Link to="/account/orders" className="mt-6 inline-block text-terracotta underline">
          سفارش‌های من
        </Link>
      </div>
    );

  if (result)
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        {result.ok ? (
          <CheckCircle2 className="mx-auto size-12 text-terracotta" />
        ) : (
          <XCircle className="mx-auto size-12 text-destructive" />
        )}
        <h1 className="mt-6 text-3xl">{result.ok ? "پرداخت موفق" : "پرداخت ناموفق"}</h1>
        <p className="mt-3 text-sm leading-7 text-muted-foreground">
          شماره سفارش: {toFa(data.orderNumber)}
          {result.reference && (
            <>
              <br />
              کد پیگیری پرداخت: {toFa(result.reference)}
            </>
          )}
          <br />
          {result.ok
            ? "سفارش شما در حال پردازش است و از حساب کاربری قابل پیگیری است."
            : "مبلغی از حساب شما کسر نشد؛ می‌توانید پرداخت را دوباره انجام دهید."}
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            to="/account/orders"
            className="border border-foreground px-8 py-3 text-sm tracking-widest transition-colors hover:bg-foreground hover:text-background"
          >
            سفارش‌های من
          </Link>
          {!result.ok && (
            <Button
              onClick={() => setResult(null)}
              className="h-auto rounded-none px-8 py-3 text-sm tracking-widest"
            >
              تلاش دوباره
            </Button>
          )}
        </div>
      </div>
    );

  if (data.paymentStatus === "paid")
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <CheckCircle2 className="mx-auto size-12 text-terracotta" />
        <h1 className="mt-6 text-3xl">این سفارش قبلاً پرداخت شده</h1>
        <Link to="/account/orders" className="mt-6 inline-block text-terracotta underline">
          مشاهده سفارش‌ها
        </Link>
      </div>
    );

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <div className="rounded-3xl border border-border bg-card p-8 shadow-soft">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="size-4 text-sage-deep" />
          درگاه پرداخت آزمایشی ساندِه
        </div>
        <h1 className="mt-6 text-3xl">پرداخت سفارش</h1>
        <dl className="mt-6 space-y-3 border-y border-border py-5 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">شماره سفارش</dt>
            <dd>#{toFa(data.orderNumber)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">کد پیگیری</dt>
            <dd className="font-mono text-xs">{data.trackingCode}</dd>
          </div>
          <div className="flex justify-between text-base">
            <dt>مبلغ قابل پرداخت</dt>
            <dd>{formatToman(Number(data.total))} تومان</dd>
          </div>
        </dl>
        <div className="mt-6 space-y-3">
          <Button
            onClick={() => pay("success")}
            disabled={busy !== null}
            className="h-11 w-full rounded-none text-sm tracking-widest"
          >
            {busy === "success" ? "در حال پرداخت…" : "پرداخت موفق (آزمایشی)"}
          </Button>
          <Button
            variant="outline"
            onClick={() => pay("failure")}
            disabled={busy !== null}
            className="h-11 w-full rounded-none text-sm tracking-widest"
          >
            {busy === "failure" ? "…" : "انصراف / پرداخت ناموفق"}
          </Button>
          <button
            type="button"
            onClick={() => navigate({ to: "/cart" })}
            className="w-full text-xs text-muted-foreground underline"
          >
            بازگشت به سبد خرید
          </button>
        </div>
        <p className="mt-6 text-xs leading-6 text-muted-foreground">
          درگاه بانکی واقعی متصل نشده است؛ این صفحه رفتار درگاه را شبیه‌سازی می‌کند و نتیجه‌ی
          پرداخت روی سفارش شما ثبت می‌شود.
        </p>
      </div>
    </div>
  );
}
