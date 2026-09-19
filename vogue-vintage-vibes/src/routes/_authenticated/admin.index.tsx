import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/orders";

export const Route = createFileRoute("/_authenticated/admin/")({
  component: AdminDashboard,
});

function AdminDashboard() {
  const { data } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.adminStats(),
  });

  const cards = [
    { label: "درآمد کل", value: `${formatToman(data?.revenue ?? 0)} تومان` },
    { label: "سفارش‌ها", value: toFa(data?.orderCount ?? 0) },
    { label: "در انتظار تأیید", value: toFa(data?.pending ?? 0) },
    { label: "محصولات", value: toFa(data?.productCount ?? 0) },
    { label: "ناموجود", value: toFa(data?.outOfStock ?? 0) },
    { label: "کاربران", value: toFa(data?.userCount ?? 0) },
  ];

  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-3xl bg-sand p-6">
            <p className="text-xs text-muted-foreground">{card.label}</p>
            <p className="mt-2 text-2xl text-terracotta">{card.value}</p>
          </div>
        ))}
      </div>

      <section>
        <h2 className="text-lg">آخرین سفارش‌ها</h2>
        <ul className="mt-4 divide-y divide-border rounded-3xl border border-border">
          {(data?.latest ?? []).map((order) => (
            <li key={order.order_number} className="flex items-center justify-between p-4 text-sm">
              <span>سفارش #{toFa(order.order_number)}</span>
              <span className="text-muted-foreground">
                {ORDER_STATUS[order.status] ?? order.status}
              </span>
              <span>{formatToman(Number(order.total))} تومان</span>
            </li>
          ))}
          {!data?.latest.length && (
            <li className="p-6 text-center text-sm text-muted-foreground">سفارشی ثبت نشده است.</li>
          )}
        </ul>
      </section>
    </div>
  );
}
