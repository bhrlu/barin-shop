import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { api, type KpiRange } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/orders";

export const Route = createFileRoute("/_authenticated/admin/")({
  component: AdminDashboard,
});

const RANGES: { value: KpiRange; label: string }[] = [
  { value: "today", label: "امروز" },
  { value: "7d", label: "۷ روز" },
  { value: "30d", label: "۳۰ روز" },
  { value: "all", label: "همه" },
];

/** Spec B0.2 status semantics: green = good, amber = in progress, rose = bad,
 * neutral = cancelled. Kept as CSS vars so the charts stay token-driven. */
const STATUS_COLORS: Record<string, string> = {
  paid: "var(--sage-deep)",
  processing: "var(--gold)",
  shipped: "var(--sage)",
  delivered: "var(--sage-deep)",
  pending: "var(--terracotta)",
  cancelled: "var(--clay)",
};

function DeltaBadge({ value }: { value: number | null }) {
  if (value === null) return null;
  const up = value >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownLeft;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
      }`}
      dir="ltr"
    >
      <Icon className="size-3" />
      {toFa(Math.abs(value))}٪
    </span>
  );
}

function AdminDashboard() {
  const [range, setRange] = useState<KpiRange>("30d");

  const kpis = useQuery({
    queryKey: ["admin-kpis", range],
    queryFn: () => api.adminKpis(range),
  });

  const stats = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api.adminStats(),
  });

  const cards = [
    {
      label: "فروش خالص",
      value: `${formatToman(kpis.data?.netRevenue ?? 0)} تومان`,
      delta: kpis.data?.deltas.netRevenue ?? null,
    },
    {
      label: "سفارش‌های پرداخت‌شده",
      value: toFa(kpis.data?.paidOrders ?? 0),
      delta: kpis.data?.deltas.paidOrders ?? null,
    },
    {
      label: "میانگین سبد خرید",
      value: `${formatToman(kpis.data?.aov ?? 0)} تومان`,
      delta: kpis.data?.deltas.aov ?? null,
    },
    {
      label: "بازپرداخت‌های منتظر",
      value: toFa(kpis.data?.pendingRefunds ?? 0),
      delta: null,
    },
  ];

  const statusData = (kpis.data?.statusBreakdown ?? []).map((entry) => ({
    ...entry,
    label: ORDER_STATUS[entry.status] ?? entry.status,
    fill: STATUS_COLORS[entry.status] ?? "var(--clay)",
  }));

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg">نمای کلی</h2>
        <div className="flex gap-2">
          {RANGES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setRange(option.value)}
              aria-pressed={range === option.value}
              className={
                range === option.value
                  ? "rounded-full border border-terracotta bg-terracotta/10 px-4 py-2 text-xs text-terracotta"
                  : "rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {kpis.isError ? (
        <p className="text-sm text-terracotta">خواندن شاخص‌ها انجام نشد.</p>
      ) : (
        <>
          {/* KPI bento grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map((card) => (
              <div
                key={card.label}
                className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">{card.label}</p>
                  <DeltaBadge value={card.delta} />
                </div>
                {kpis.isLoading ? (
                  <div className="mt-3 h-8 w-24 animate-pulse rounded-lg bg-clay" />
                ) : (
                  <p className="mt-2 text-2xl text-terracotta">{card.value}</p>
                )}
              </div>
            ))}
          </div>

          {/* urgent actions (spec [FE-03] row 3) */}
          {(kpis.data?.pendingRefunds ?? 0) > 0 || (kpis.data?.lowStock ?? 0) > 0 ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
              <p className="font-medium">اقدامات فوری</p>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
                {(kpis.data?.pendingRefunds ?? 0) > 0 && (
                  <Link to="/admin/refunds" className="underline underline-offset-4">
                    {toFa(kpis.data?.pendingRefunds ?? 0)} درخواست بازپرداخت در انتظار بررسی
                  </Link>
                )}
                {(kpis.data?.lowStock ?? 0) > 0 && (
                  <Link to="/admin/inventory" className="underline underline-offset-4">
                    {toFa(kpis.data?.lowStock ?? 0)} محصول با موجودی کم
                  </Link>
                )}
              </div>
            </div>
          ) : null}

          {/* row 2: revenue trend + status donut */}
          <div className="grid gap-4 lg:grid-cols-5">
            <section className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm lg:col-span-3">
              <h3 className="text-sm">روند فروش</h3>
              {kpis.isLoading ? (
                <div className="mt-4 h-56 animate-pulse rounded-xl bg-clay" />
              ) : (
                <div className="mt-4 h-56" dir="ltr">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={kpis.data?.series ?? []}>
                      <defs>
                        <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="var(--terracotta)" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="var(--terracotta)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value: string) => value.slice(5)}
                        tickLine={false}
                        axisLine={false}
                        minTickGap={24}
                      />
                      <YAxis
                        tick={{ fontSize: 10 }}
                        tickFormatter={(value: number) => `${Math.round(value / 1000)}`}
                        tickLine={false}
                        axisLine={false}
                        width={36}
                      />
                      <Tooltip
                        formatter={(value: number) => [`${formatToman(value)} تومان`, "فروش"]}
                      />
                      <Area
                        type="monotone"
                        dataKey="revenue"
                        stroke="var(--terracotta)"
                        strokeWidth={2}
                        fill="url(#revenueFill)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm lg:col-span-2">
              <h3 className="text-sm">وضعیت سفارشات</h3>
              {kpis.isLoading ? (
                <div className="mt-4 h-56 animate-pulse rounded-xl bg-clay" />
              ) : statusData.length === 0 ? (
                <p className="mt-8 text-center text-sm text-muted-foreground">
                  سفارشی در این بازه ثبت نشده است.
                </p>
              ) : (
                <>
                  <div className="mt-2 h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={statusData}
                          dataKey="count"
                          nameKey="label"
                          innerRadius="58%"
                          outerRadius="85%"
                          paddingAngle={2}
                          strokeWidth={0}
                        >
                          {statusData.map((entry) => (
                            <Cell key={entry.status} fill={entry.fill} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value: number, name: string) => [toFa(value), name]} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {statusData.map((entry) => (
                      <li key={entry.status} className="flex items-center gap-1.5">
                        <span
                          aria-hidden
                          className="inline-block size-2.5 rounded-full"
                          style={{ background: entry.fill }}
                        />
                        {entry.label} ({toFa(entry.count)})
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          </div>
        </>
      )}

      <section>
        <h2 className="text-lg">آخرین سفارش‌ها</h2>
        <ul className="mt-4 divide-y divide-border rounded-3xl border border-border">
          {(stats.data?.latest ?? []).map((order) => (
            <li key={order.order_number} className="flex items-center justify-between p-4 text-sm">
              <span>سفارش #{toFa(order.order_number)}</span>
              <span className="text-muted-foreground">
                {ORDER_STATUS[order.status] ?? order.status}
              </span>
              <span>{formatToman(Number(order.total))} تومان</span>
            </li>
          ))}
          {!stats.data?.latest.length && (
            <li className="p-6 text-center text-sm text-muted-foreground">سفارشی ثبت نشده است.</li>
          )}
        </ul>
      </section>
    </div>
  );
}
