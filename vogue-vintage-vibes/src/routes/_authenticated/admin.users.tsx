import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";

/** Staff roles (B5.4) each have their own Persian label; an unknown role shows
 * its raw name rather than being mislabelled as a customer. */
const ROLE_LABELS: Record<string, string> = {
  super_admin: "مدیر ارشد",
  admin: "مدیر",
  order_manager: "مدیر سفارش‌ها",
  support: "پشتیبانی",
  customer: "مشتری",
};

export const Route = createFileRoute("/_authenticated/admin/users")({
  component: AdminUsers,
});

function AdminUsers() {
  const { data } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => api.adminUsers(),
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
                {ROLE_LABELS[role] ?? role}
              </span>
            ))}
            <span>{toFa(user.order_count)} سفارش</span>
            <span>{formatToman(user.spent)} تومان</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
