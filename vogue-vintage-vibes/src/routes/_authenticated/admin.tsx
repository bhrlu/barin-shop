import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Package,
  RotateCcw,
  ShoppingBag,
  SlidersHorizontal,
  Star,
  Store,
  Users,
} from "lucide-react";
import { api, type KpiRange } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toFa } from "@/lib/format";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

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

type TabKey =
  "dashboard" | "products" | "inventory" | "orders" | "refunds" | "messages" | "reviews" | "users";

type AdminTab = {
  key: TabKey;
  to: string;
  label: string;
  exact: boolean;
  icon: typeof LayoutDashboard;
  /** optional badge value from the KPI payload */
  badge?: "orders" | "refunds";
};

const ALL_TABS: AdminTab[] = [
  { key: "dashboard", to: "/admin", label: "داشبورد", exact: true, icon: LayoutDashboard },
  { key: "products", to: "/admin/products", label: "محصولات", exact: false, icon: Package },
  {
    key: "inventory",
    to: "/admin/inventory",
    label: "انبار",
    exact: false,
    icon: SlidersHorizontal,
  },
  {
    key: "orders",
    to: "/admin/orders",
    label: "سفارش‌ها",
    exact: false,
    icon: ShoppingBag,
    badge: "orders",
  },
  {
    key: "refunds",
    to: "/admin/refunds",
    label: "بازپرداخت‌ها",
    exact: false,
    icon: RotateCcw,
    badge: "refunds",
  },
  { key: "messages", to: "/admin/messages", label: "پیام‌ها", exact: false, icon: MessageSquare },
  { key: "reviews", to: "/admin/reviews", label: "نظرات", exact: false, icon: Star },
  { key: "users", to: "/admin/users", label: "کاربران", exact: false, icon: Users },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: "مدیر ارشد",
  admin: "مدیر",
  order_manager: "مدیر سفارش‌ها",
  support: "پشتیبانی",
  customer: "مشتری",
};

/** Staff role → allowed admin tabs (mirrors backend ROLE_CAPABILITIES, B5.4).
 * Anything a role can't act on via the API is hidden from its navigation. */
const ROLE_TAB_KEYS: Record<string, TabKey[]> = {
  super_admin: [
    "dashboard",
    "products",
    "inventory",
    "orders",
    "refunds",
    "messages",
    "reviews",
    "users",
  ],
  admin: [
    "dashboard",
    "products",
    "inventory",
    "orders",
    "refunds",
    "messages",
    "reviews",
    "users",
  ],
  order_manager: ["dashboard", "products", "inventory", "orders", "refunds", "messages"],
  support: ["dashboard", "messages", "reviews"],
};

const KPI_RANGE: KpiRange = "all";

function AdminLayout() {
  const { user, isAdmin, loading, signOut } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [quickSearch, setQuickSearch] = useState("");

  const role = user?.role ?? "customer";
  const roleLabel = ROLE_LABELS[role] ?? ROLE_LABELS["customer"];
  // unknown roles degrade to the read-mostly trio; legacy "admin" maps above
  const allowedKeys = new Set(ROLE_TAB_KEYS[role] ?? ROLE_TAB_KEYS["support"]);
  const tabs = ALL_TABS.filter((tab) => allowedKeys.has(tab.key));
  // Hiding a tab is not a guard: a staff member who types /admin/users still
  // rendered the page and only saw its empty state when the API answered 403.
  // Spec [FE-01].3 asks for an explicit Persian permission error instead.
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const currentTab = [...ALL_TABS]
    .sort((a, b) => b.to.length - a.to.length)
    .find((tab) => (tab.exact ? pathname === tab.to : pathname.startsWith(tab.to)));
  const tabAllowed = !currentTab || allowedKeys.has(currentTab.key);

  // badge counts (pending/processing orders, active refunds) — read endpoint
  // only; a 403 here just means no badges for this role
  const kpis = useQuery({
    queryKey: ["admin", "kpis", "shell"],
    queryFn: () => api.adminKpis(KPI_RANGE),
    enabled: isAdmin,
    refetchInterval: 60_000,
    retry: false,
  });
  const orderBadge = (kpis.data?.statusBreakdown ?? [])
    .filter((s) => s.status === "pending" || s.status === "processing")
    .reduce((sum, s) => sum + s.count, 0);
  const refundBadge = kpis.data?.pendingRefunds ?? 0;
  const badgeFor = (tab: AdminTab): number =>
    tab.badge === "orders" ? orderBadge : tab.badge === "refunds" ? refundBadge : 0;

  const submitQuickSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = quickSearch.trim();
    setQuickSearch("");
    setMobileOpen(false);
    if (q) navigate({ to: "/shop", search: { q } });
  };

  const nav = (
    <nav aria-label="ناوبری مدیریت" className="flex flex-col gap-1">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const count = badgeFor(tab);
        return (
          <Link
            key={tab.to}
            to={tab.to}
            activeOptions={{ exact: tab.exact }}
            onClick={() => setMobileOpen(false)}
            className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-terracotta/5 hover:text-foreground"
            activeProps={{ className: "bg-terracotta/10 font-semibold text-terracotta" }}
          >
            <span className="flex h-[18px] w-[18px] shrink-0 items-center justify-center">
              <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} aria-hidden />
            </span>
            <span className="flex-1">{tab.label}</span>
            {count > 0 ? (
              <span className="rounded-full bg-terracotta px-2 py-0.5 text-[11px] font-semibold text-white">
                {toFa(count)}
              </span>
            ) : null}
          </Link>
        );
      })}
      <div className="my-3 border-t border-border/70" role="separator" />
      <Link
        to="/"
        onClick={() => setMobileOpen(false)}
        className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-terracotta/5 hover:text-foreground"
      >
        <span className="flex h-[18px] w-[18px] shrink-0 items-center justify-center">
          <Store className="h-[18px] w-[18px]" strokeWidth={1.5} aria-hidden />
        </span>
        بازگشت به فروشگاه
      </Link>
    </nav>
  );

  const sidebarHeader = (
    <div className="px-4 py-6">
      <p className="text-lg font-semibold tracking-[0.18em] text-foreground">SÂNDÉ</p>
      <p className="mt-1 text-[11px] tracking-[0.25em] text-sage-deep">پنل مدیریت</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* top header bar — sticky, blur */}
      <header className="sticky top-0 z-30 h-16 border-b border-border/60 bg-background/95 backdrop-blur">
        <div className="flex h-full items-center gap-3 px-4 sm:px-6">
          {/* mobile hamburger + sheet trigger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                aria-label="باز کردن منوی مدیریت"
              >
                <Menu className="h-5 w-5" aria-hidden />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-64 p-0">
              {sidebarHeader}
              <div className="px-3">{nav}</div>
            </SheetContent>
          </Sheet>

          {/* global quick search (desktop) */}
          <form onSubmit={submitQuickSearch} className="hidden max-w-md flex-1 lg:block">
            <input
              type="search"
              value={quickSearch}
              onChange={(event) => setQuickSearch(event.target.value)}
              placeholder="جست‌وجوی سریع محصولات… (Ctrl+K)"
              aria-label="جست‌وجوی سریع"
              className="h-10 w-full rounded-full border border-border bg-card px-4 text-sm outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-terracotta"
            />
          </form>

          <div className="flex-1" />

          {/* role badge + logout */}
          <span className="rounded-full border border-sage-deep/40 px-3 py-1 text-[11px] text-sage-deep">
            {roleLabel}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              signOut();
              navigate({ to: "/" });
            }}
            aria-label="خروج از حساب"
            title="خروج"
          >
            <LogOut className="h-5 w-5" aria-hidden />
          </Button>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-8 px-4 py-8 sm:px-6">
        {/* desktop sidebar — RTL puts it on the right as the first flex child */}
        <aside className="sticky top-24 hidden h-fit w-64 shrink-0 rounded-3xl border border-border/70 bg-card p-3 lg:block">
          {sidebarHeader}
          <div className="mx-4 border-t border-border/70" />
          <div className="mt-3">{nav}</div>
        </aside>

        <main className="min-w-0 flex-1">
          {loading ? null : !isAdmin ? (
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
              <div className="mb-6 lg:hidden">
                <form onSubmit={submitQuickSearch}>
                  <input
                    type="search"
                    value={quickSearch}
                    onChange={(event) => setQuickSearch(event.target.value)}
                    placeholder="جست‌وجوی سریع محصولات…"
                    aria-label="جست‌وجوی سریع"
                    className="h-10 w-full rounded-full border border-border bg-card px-4 text-sm outline-none placeholder:text-muted-foreground/70 focus:border-terracotta"
                  />
                </form>
              </div>
              {tabAllowed ? (
                <Outlet />
              ) : (
                <div className="mt-10 rounded-3xl border border-dashed border-border p-12 text-center">
                  <p className="text-muted-foreground">
                    نقش «{roleLabel}» به این بخش دسترسی ندارد.
                  </p>
                  <Link to="/admin" className="mt-4 inline-block text-terracotta underline">
                    بازگشت به داشبورد
                  </Link>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
