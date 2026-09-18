import { createFileRoute, Link, Outlet, useNavigate } from "@tanstack/react-router";
import { Heart, LogOut, MapPin, Package, User, Wallet } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/_authenticated/account")({
  head: () => ({
    meta: [
      { title: "حساب کاربری — ساندِه" },
      { name: "description", content: "پروفایل، سفارش‌ها، آدرس‌ها، پرداخت‌ها و علاقه‌مندی‌های شما." },
      { property: "og:title", content: "حساب کاربری — ساندِه" },
      { property: "og:description", content: "مدیریت پروفایل و سفارش‌های شما در ساندِه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AccountLayout,
});

const tabs = [
  { to: "/account", label: "پروفایل", icon: User, exact: true },
  { to: "/account/orders", label: "سفارش‌ها", icon: Package, exact: false },
  { to: "/account/addresses", label: "آدرس‌ها", icon: MapPin, exact: false },
  { to: "/account/favorites", label: "علاقه‌مندی‌ها", icon: Heart, exact: false },
  { to: "/account/payments", label: "پرداخت‌ها", icon: Wallet, exact: false },
] as const;

function AccountLayout() {
  const { profile, user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const signOut = async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    navigate({ to: "/auth", replace: true });
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] tracking-[0.25em] text-sage-deep">حساب کاربری</p>
          <h1 className="mt-2 text-3xl">{profile?.full_name || user?.email}</h1>
        </div>
        <div className="flex items-center gap-3">
          {isAdmin && (
            <Link
              to="/admin"
              className="rounded-full border border-terracotta px-4 py-2 text-xs text-terracotta"
            >
              پنل مدیریت
            </Link>
          )}
          <button
            type="button"
            onClick={signOut}
            className="flex items-center gap-1 rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <LogOut className="size-3.5" /> خروج
          </button>
        </div>
      </header>

      <nav className="mt-8 flex flex-wrap gap-2 border-b border-border pb-4">
        {tabs.map((tab) => (
          <Link
            key={tab.to}
            to={tab.to}
            activeOptions={{ exact: tab.exact }}
            className="flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            activeProps={{ className: "border-terracotta bg-terracotta/10 text-terracotta" }}
          >
            <tab.icon className="size-4" />
            {tab.label}
          </Link>
        ))}
      </nav>

      <div className="mt-8">
        <Outlet />
      </div>
    </div>
  );
}