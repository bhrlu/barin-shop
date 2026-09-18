import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { formatToman, toFa } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/admin/users")({
  component: AdminUsers,
});

function AdminUsers() {
  const { data } = useQuery({
    queryKey: ["admin-users"],
    queryFn: async () => {
      const [profiles, roles, orders] = await Promise.all([
        supabase.from("profiles").select("*").order("created_at", { ascending: false }),
        supabase.from("user_roles").select("user_id, role"),
        supabase.from("orders").select("user_id, total, status"),
      ]);
      if (profiles.error) throw profiles.error;
      const roleMap = new Map<string, string[]>();
      for (const row of roles.data ?? []) {
        roleMap.set(row.user_id, [...(roleMap.get(row.user_id) ?? []), row.role]);
      }
      return (profiles.data ?? []).map((profile) => {
        const userOrders = (orders.data ?? []).filter((o) => o.user_id === profile.id);
        return {
          ...profile,
          roles: roleMap.get(profile.id) ?? ["customer"],
          orderCount: userOrders.length,
          spent: userOrders
            .filter((o) => o.status !== "cancelled")
            .reduce((sum, o) => sum + Number(o.total), 0),
        };
      });
    },
  });

  if (!data?.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        کاربری ثبت نشده است.
      </div>
    );

  return (
    <ul className="divide-y divide-border rounded-3xl border border-border">
      {data.map((user) => (
        <li key={user.id} className="flex flex-wrap items-center justify-between gap-3 p-5 text-sm">
          <div>
            <p>{user.full_name ?? "بدون نام"}</p>
            <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
              {user.phone ?? "—"} · {toFa(new Date(user.created_at).toLocaleDateString("fa-IR"))}
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            {user.roles.map((role) => (
              <span key={role} className="rounded-full bg-sand px-3 py-1">
                {role === "admin" ? "مدیر" : "مشتری"}
              </span>
            ))}
            <span>{toFa(user.orderCount)} سفارش</span>
            <span>{formatToman(user.spent)} تومان</span>
          </div>
        </li>
      ))}
    </ul>
  );
}