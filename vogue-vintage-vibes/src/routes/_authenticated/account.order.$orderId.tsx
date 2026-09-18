import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, CreditCard, Package, Truck, ClipboardList } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { CancelOrderButton } from "@/components/CancelOrderButton";

export const Route = createFileRoute("/_authenticated/account/order/$orderId")({
  head: () => ({
    meta: [
      { title: "وضعیت سفارش — ساندِه" },
      { name: "description", content: "پیگیری مرحله‌به‌مرحله سفارش: ثبت، پردازش، پرداخت و ارسال." },
      { property: "og:title", content: "وضعیت سفارش — ساندِه" },
      { property: "og:description", content: "پیگیری مرحله‌به‌مرحله سفارش شما در ساندِه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: OrderStatusPage,
});

const STEPS = [
  { key: "placed", label: "ثبت سفارش", icon: ClipboardList },
  { key: "processing", label: "پردازش", icon: Package },
  { key: "payment", label: "پرداخت", icon: CreditCard },
  { key: "shipped", label: "ارسال", icon: Truck },
] as const;

function OrderStatusPage() {
  const { orderId } = Route.useParams();
  const { data, isLoading } = useQuery({
    queryKey: ["order-status", orderId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("orders")
        .select("*, order_items(*)")
        .eq("id", orderId)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">در حال بارگذاری…</p>;
  if (!data)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center">
        <p className="text-muted-foreground">سفارشی با این شناسه پیدا نشد.</p>
        <Link to="/account/orders" className="mt-4 inline-block text-terracotta underline">
          بازگشت به سفارش‌ها
        </Link>
      </div>
    );

  const paid = data.payment_status === "paid";
  const cancelled = data.status === "cancelled";
  const doneMap: Record<string, boolean> = {
    placed: true,
    processing: ["processing", "shipped", "delivered"].includes(data.status) || paid,
    payment: paid,
    shipped: ["shipped", "delivered"].includes(data.status),
  };
  const currentIndex = STEPS.findIndex((s) => !doneMap[s.key]);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl">سفارش #{toFa(data.order_number)}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {toFa(new Date(data.created_at).toLocaleDateString("fa-IR"))}
          </p>
        </div>
        <Link
          to="/account/orders"
          className="flex items-center gap-1 rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowRight className="size-3.5" /> همه سفارش‌ها
        </Link>
      </header>

      <section className="rounded-3xl border border-border bg-sand/40 p-6 sm:p-8">
        {cancelled ? (
          <p className="text-sm text-terracotta">این سفارش لغو شده است.</p>
        ) : null}
        <ol className="mt-2 grid gap-6 sm:grid-cols-4">
          {STEPS.map((step, index) => {
            const done = !cancelled && doneMap[step.key];
            const active = !cancelled && index === currentIndex;
            return (
              <li key={step.key} className="relative flex items-start gap-3 sm:flex-col sm:items-center sm:text-center">
                <span
                  className={`flex size-11 shrink-0 items-center justify-center rounded-full border transition-colors ${
                    done
                      ? "border-sage-deep bg-sage-deep text-background"
                      : active
                        ? "border-terracotta bg-terracotta/10 text-terracotta"
                        : "border-border bg-background text-muted-foreground"
                  }`}
                >
                  {done ? <Check className="size-5" /> : <step.icon className="size-5" />}
                </span>
                <span className="space-y-1">
                  <span className="block text-sm">{step.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {done ? "انجام شد" : active ? "در جریان" : "در انتظار"}
                  </span>
                </span>
                {index < STEPS.length - 1 && (
                  <span
                    aria-hidden
                    className={`absolute hidden h-px w-full sm:block sm:top-5 sm:-left-1/2 ${
                      done ? "bg-sage-deep" : "bg-border"
                    }`}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-3xl border border-border p-5 text-sm">
          <h3 className="text-base">وضعیت</h3>
          <p className="mt-3 text-muted-foreground">
            سفارش: <span className="text-foreground">{ORDER_STATUS[data.status] ?? data.status}</span>
          </p>
          <p className="mt-1 text-muted-foreground">
            پرداخت:{" "}
            <span className="text-foreground">
              {PAYMENT_STATUS[data.payment_status] ?? data.payment_status}
            </span>
          </p>
          <p className="mt-3">مبلغ نهایی: {formatToman(data.total)} تومان</p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {!paid && !cancelled && (
              <Link
                to="/payment/$orderId"
                params={{ orderId: data.id }}
                className="border border-foreground px-5 py-2 text-xs tracking-widest transition-colors hover:bg-foreground hover:text-background"
              >
                پرداخت سفارش
              </Link>
            )}
            {!["shipped", "delivered", "cancelled"].includes(data.status) && (
              <CancelOrderButton orderId={data.id} />
            )}
          </div>
        </div>
        <div className="rounded-3xl border border-border p-5 text-sm">
          <h3 className="text-base">اقلام</h3>
          <ul className="mt-3 space-y-3">
            {data.order_items.map((item) => (
              <li key={item.id} className="flex items-center gap-3">
                {item.image && <img src={item.image} alt="" className="size-14 rounded-xl object-cover" />}
                <span className="flex-1">
                  {item.name}
                  <span className="block text-xs text-muted-foreground">
                    سایز {toFa(item.size ?? "-")} · رنگ {item.color} · تعداد {toFa(item.quantity)}
                  </span>
                </span>
                <span>{formatToman(item.price * item.quantity)} تومان</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}