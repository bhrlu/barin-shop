import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Eye, PackageCheck } from "lucide-react";
import { toast } from "sonner";
import { api, type Order } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { OrderDetailDrawer } from "@/components/admin/OrderDetailDrawer";

export const Route = createFileRoute("/_authenticated/admin/orders")({
  component: AdminOrders,
});

/** Shipment tracking input (F2.8): one field per order, saved via
 * `PATCH /orders/{id}` (`tracking_code`). Empty input clears the code. */
export function TrackingCodeInput({
  orderId,
  initial,
}: {
  orderId: string;
  initial: string | null;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(initial ?? "");

  const save = useMutation({
    mutationFn: (tracking_code: string | null) => api.patchOrder(orderId, { tracking_code }),
    onSuccess: (_, tracking_code) => {
      void queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
      toast.success(tracking_code ? "کد رهگیری ذخیره شد" : "کد رهگیری حذف شد");
    },
    onError: () => toast.error("ذخیره کد رهگیری ناموفق بود"),
  });

  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim() !== (initial ?? "")) save.mutate(value.trim() || null);
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="کد رهگیری پستی/تیپاکس"
        maxLength={60}
        className="h-9 w-56 rounded-md border border-input bg-background px-2 font-mono text-xs tracking-wider"
      />
      <button
        type="submit"
        disabled={save.isPending || value.trim() === (initial ?? "")}
        className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
      >
        <PackageCheck className="size-3.5" />
        {save.isPending ? "در حال ذخیره…" : "ذخیره"}
      </button>
      {initial ? (
        <button
          type="button"
          onClick={() => {
            setValue("");
            save.mutate(null);
          }}
          disabled={save.isPending}
          className="text-xs text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
        >
          حذف
        </button>
      ) : null}
    </form>
  );
}

function AdminOrders() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Order | null>(null);
  const { data } = useQuery({
    queryKey: ["admin-orders"],
    queryFn: () => api.adminOrders(),
  });

  const update = useMutation({
    mutationFn: async (input: {
      id: string;
      patch: { status?: string; payment_status?: string };
    }) => api.patchOrder(input.id, input.patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      queryClient.invalidateQueries({ queryKey: ["admin-kpis"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "kpis"] });
      toast.success("سفارش به‌روزرسانی شد");
    },
    onError: () => toast.error("به‌روزرسانی ناموفق بود"),
  });

  // keep the drawer's order object fresh after mutations invalidate the list
  const selectedFresh = selected ? (data?.find((order) => order.id === selected.id) ?? null) : null;

  const copyAddress = async (address: Record<string, string>) => {
    const text = [
      address["receiver"],
      address["phone"],
      [address["province"], address["city"]].filter(Boolean).join("، "),
      address["line"],
      address["postal_code"] ? `کد پستی: ${address["postal_code"]}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success("آدرس گیرنده کپی شد");
    } catch {
      toast.error("کپی انجام نشد");
    }
  };

  if (!data?.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        سفارشی ثبت نشده است.
      </div>
    );

  return (
    <>
      <ul className="space-y-4">
        {data.map((order) => {
          const address = order.shipping_address as Record<string, string> | null;
          return (
            <li key={order.id} className="rounded-3xl border border-border p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm">سفارش #{toFa(order.order_number)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {toFa(new Date(order.created_at).toLocaleDateString("fa-IR"))} ·{" "}
                    {formatToman(Number(order.total))} تومان
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <select
                    value={order.status}
                    onChange={(e) =>
                      update.mutate({ id: order.id, patch: { status: e.target.value } })
                    }
                    className="h-9 rounded-md border border-input bg-background px-2"
                  >
                    {Object.entries(ORDER_STATUS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={order.payment_status}
                    onChange={(e) =>
                      update.mutate({ id: order.id, patch: { payment_status: e.target.value } })
                    }
                    className="h-9 rounded-md border border-input bg-background px-2"
                  >
                    {Object.entries(PAYMENT_STATUS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setSelected(order)}
                    className="flex items-center gap-1.5 rounded-full bg-terracotta px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-terracotta/90"
                  >
                    <Eye className="size-3.5" />
                    مشاهده و پردازش
                  </button>
                </div>
              </div>

              {address && (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {address["receiver"]} · {address["phone"]} · {address["province"]}،{" "}
                    {address["city"]} — {address["line"]}
                  </p>
                  <button
                    type="button"
                    onClick={() => void copyAddress(address)}
                    title="کپی آدرس گیرنده"
                    className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Copy className="size-3.5" />
                    کپی آدرس
                  </button>
                </div>
              )}

              <div className="mt-3">
                <TrackingCodeInput orderId={order.id} initial={order.tracking_code} />
              </div>

              <ul className="mt-4 space-y-2 border-t border-border pt-4 text-sm">
                {order.items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3">
                    <span>
                      {item.name}{" "}
                      <span className="text-xs text-muted-foreground">
                        ({toFa(item.size ?? "-")} / {item.color} / ×{toFa(item.quantity)})
                      </span>
                    </span>
                    <span>{formatToman(item.price * item.quantity)} تومان</span>
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>

      <OrderDetailDrawer order={selectedFresh} onClose={() => setSelected(null)} />
    </>
  );
}
