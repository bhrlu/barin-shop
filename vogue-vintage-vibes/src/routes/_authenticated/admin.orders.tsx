import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";

export const Route = createFileRoute("/_authenticated/admin/orders")({
  component: AdminOrders,
});

function AdminOrders() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin-orders"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("orders")
        .select("*, order_items(*)")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });

  const update = useMutation({
    mutationFn: async (input: { id: string; patch: Record<string, string> }) => {
      const { error } = await supabase.from("orders").update(input.patch as never).eq("id", input.id);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      toast.success("سفارش به‌روزرسانی شد");
    },
    onError: () => toast.error("به‌روزرسانی ناموفق بود"),
  });

  if (!data?.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        سفارشی ثبت نشده است.
      </div>
    );

  return (
    <ul className="space-y-4">
      {data.map((order) => {
        const address = order.shipping_address as Record<string, string> | null;
        return (
          <li key={order.id} className="rounded-3xl border border-border p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm">
                  سفارش #{toFa(order.order_number)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {toFa(new Date(order.created_at).toLocaleDateString("fa-IR"))} ·{" "}
                  {formatToman(Number(order.total))} تومان
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <select
                  value={order.status}
                  onChange={(e) => update.mutate({ id: order.id, patch: { status: e.target.value } })}
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
              </div>
            </div>

            {address && (
              <p className="mt-3 text-xs text-muted-foreground">
                {address["receiver"]} · {address["phone"]} · {address["province"]}، {address["city"]} —{" "}
                {address["line"]}
              </p>
            )}

            <ul className="mt-4 space-y-2 border-t border-border pt-4 text-sm">
              {order.order_items.map((item) => (
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
  );
}