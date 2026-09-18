import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { formatToman, toFa } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/account/payments")({
  component: PaymentsTab,
});

const statusLabel: Record<string, string> = {
  pending: "در انتظار",
  succeeded: "موفق",
  failed: "ناموفق",
};

function PaymentsTab() {
  const { data } = useQuery({
    queryKey: ["my-payments"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("payments")
        .select("*, orders(order_number)")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });

  if (!data?.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        پرداختی ثبت نشده است.
      </div>
    );

  return (
    <ul className="divide-y divide-border rounded-3xl border border-border">
      {data.map((payment) => (
        <li key={payment.id} className="flex flex-wrap items-center justify-between gap-3 p-5 text-sm">
          <div>
            <p dir="ltr">{payment.reference}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              سفارش #{toFa(payment.orders?.order_number ?? "-")} ·{" "}
              {toFa(new Date(payment.created_at).toLocaleDateString("fa-IR"))}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-sand px-3 py-1 text-xs">
              {payment.method === "online" ? "پرداخت آنلاین" : "پرداخت در محل"}
            </span>
            <span className="rounded-full bg-terracotta/10 px-3 py-1 text-xs text-terracotta">
              {statusLabel[payment.status] ?? payment.status}
            </span>
            <span>{formatToman(payment.amount)} تومان</span>
          </div>
        </li>
      ))}
    </ul>
  );
}