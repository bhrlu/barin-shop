import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, toPage } from "@/lib/api";
import { formatToman, toFa } from "@/lib/format";
import { Pager } from "@/components/Pager";

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

const PAGE_SIZE = 20;

function AdminUsers() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => toPage(api.adminUsers(page, PAGE_SIZE)),
  });
  const users = data?.items ?? [];

  if (isLoading)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        در حال بارگذاری…
      </div>
    );

  if (!users.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        کاربری ثبت نشده است.
      </div>
    );

  return (
    <>
      <ul className="divide-y divide-border rounded-3xl border border-border">
        {users.map((user) => (
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
      <Pager
        className="mt-6"
        page={data?.page ?? page}
        pages={data?.pages ?? 1}
        total={data?.total}
        onChange={setPage}
      />
    </>
  );
}
