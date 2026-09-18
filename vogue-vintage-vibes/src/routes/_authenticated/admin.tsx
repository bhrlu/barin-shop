import { createFileRoute, Link, Outlet } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({
    meta: [
      { title: "پنل مدیریت — ساندِه" },
      { name: "description", content: "مدیریت محصولات، سفارش‌ها و کاربران فروشگاه ساندِه." },
      { property: "og:title", content: "پنل مدیریت — ساندِه" },
      { property: "og:description", content: "مدیریت محصولات، سفارش‌ها و کاربران." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminLayout,
});

const tabs = [
  { to: "/admin", label: "داشبورد", exact: true },
  { to: "/admin/products", label: "محصولات", exact: false },
  { to: "/admin/orders", label: "سفارش‌ها", exact: false },
  { to: "/admin/users", label: "کاربران", exact: false },
] as const;

function AdminLayout() {
  const { isAdmin, loading } = useAuth();

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <p className="text-[11px] tracking-[0.25em] text-sage-deep">پنل مدیریت</p>
      <h1 className="mt-2 text-3xl">مدیریت فروشگاه</h1>

      {!loading && !isAdmin ? (
        <div className="mt-10 rounded-3xl border border-dashed border-border p-12 text-center">
          <p className="text-muted-foreground">
            حساب شما دسترسی مدیریت ندارد. برای دریافت دسترسی با پشتیبانی تماس بگیرید.
          </p>
          <Link to="/account" className="mt-4 inline-block text-terracotta underline">
            بازگشت به حساب کاربری
          </Link>
        </div>
      ) : (
        <>
          <nav className="mt-8 flex flex-wrap gap-2 border-b border-border pb-4">
            {tabs.map((tab) => (
              <Link
                key={tab.to}
                to={tab.to}
                activeOptions={{ exact: tab.exact }}
                className="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
                activeProps={{ className: "border-terracotta bg-terracotta/10 text-terracotta" }}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
          <div className="mt-8">
            <Outlet />
          </div>
        </>
      )}
    </div>
  );
}