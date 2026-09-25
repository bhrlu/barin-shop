import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart, MapPin, Package, ShieldCheck, ShoppingBag, Timer } from "lucide-react";
import { toast } from "sonner";
import { api, type AdminUser, type AdminCustomerProfile, type CustomerTier } from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { TIER_LABELS } from "@/lib/tiers";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const TIER_CLASSES: Record<CustomerTier, string> = {
  new: "bg-sand text-foreground border-border",
  vip: "bg-terracotta/10 text-terracotta border-terracotta/30",
  wholesale: "bg-sage/20 text-sage-deep border-sage/40",
};

function TierBadge({ tier }: { tier: CustomerTier }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TIER_CLASSES[tier]}`}
    >
      {TIER_LABELS[tier]}
    </span>
  );
}

/** Initials avatar (spec [FE-08]) — first letters of the name, fallback «م». */
function InitialsAvatar({ name, url }: { name: string | null; url: string | null }) {
  const initials =
    (name ?? "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("") || "م";
  return url ? (
    <img src={url} alt="" className="size-10 shrink-0 rounded-full object-cover" />
  ) : (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-sand text-sm font-semibold text-foreground">
      {initials}
    </span>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="mt-1.5 text-lg font-semibold">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

type TabKey = "orders" | "addresses" | "favorites";

const TABS: { key: TabKey; label: string }[] = [
  { key: "orders", label: "تاریخچه سفارشات" },
  { key: "addresses", label: "آدرس‌های ثبت‌شده" },
  { key: "favorites", label: "علاقه‌مندی‌ها" },
];

/**
 * Customer 360° drawer (AB-FE-06, spec [FE-08]): avatar + tier + registration
 * date, LTV / cadence stat cards, and the three customer-source tabs. The
 * role-management entry point reuses the users screen's existing `RolesDialog`
 * flow (open → the route-level `onEditRoles`), so there is exactly one role
 * UI. Tier assignment (D7b wholesale flag) lives here too, with a typed
 * confirm step because it changes what staff see about a customer.
 */
export function CustomerProfileDrawer({
  user,
  onClose,
  onEditRoles,
}: {
  user: AdminUser | null;
  onClose: () => void;
  onEditRoles: (user: AdminUser) => void;
}) {
  const [tab, setTab] = useState<TabKey>("orders");
  const [tierDraft, setTierDraft] = useState<string>("");
  const queryClient = useQueryClient();

  const profile = useQuery({
    queryKey: ["admin", "customer-profile", user?.id],
    queryFn: () => api.adminCustomerProfile(user!.id),
    enabled: Boolean(user),
  });

  const tierMutation = useMutation({
    mutationFn: (tier: "wholesale" | null) => api.adminSetUserTier(user!.id, tier),
    onSuccess: (result) => {
      toast.success(`سطح مشتری: ${TIER_LABELS[result.tier]}`);
      setTierDraft("");
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "customer-profile", user?.id] });
    },
    onError: () => toast.error("ثبت سطح ناموفق بود"),
  });

  if (!user) return null;
  const data = profile.data;

  return (
    <Sheet open={Boolean(user)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="left"
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-xl"
      >
        <SheetHeader className="border-b border-border px-6 pb-4 pt-6 text-right">
          <SheetTitle className="text-base">پروفایل ۳۶۰° مشتری</SheetTitle>
          <SheetDescription className="sr-only">
            نمای کلی مشتری، سفارش‌ها، آدرس‌ها و علاقه‌مندی‌ها
          </SheetDescription>
          <div className="mt-3 flex items-center gap-3">
            <InitialsAvatar name={user.full_name} url={data?.profile.avatar_url ?? null} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-sm font-semibold">{user.full_name ?? "بدون نام"}</p>
                <TierBadge tier={data?.tier ?? "new"} />
              </div>
              <p className="mt-0.5 truncate text-xs text-muted-foreground" dir="ltr">
                {user.email}
              </p>
              <p className="text-xs text-muted-foreground">
                عضویت: {formatFaDate(user.created_at)}
              </p>
            </div>
          </div>
        </SheetHeader>

        {profile.isLoading ? (
          <div className="space-y-3 p-6">
            <div className="grid grid-cols-2 gap-3">
              {[1, 2, 3, 4].map((n) => (
                <div key={n} className="h-20 animate-pulse rounded-xl bg-muted/60" />
              ))}
            </div>
            <div className="h-64 animate-pulse rounded-xl bg-muted/40" />
          </div>
        ) : profile.isError || !data ? (
          <div className="p-6 text-sm text-muted-foreground">
            خواندن پروفایل ناموفق بود.{" "}
            <button
              type="button"
              className="text-terracotta underline"
              onClick={() => void profile.refetch()}
            >
              تلاش دوباره
            </button>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            {/* ---- overview metrics ---- */}
            <div className="grid grid-cols-2 gap-3 px-6 pt-4">
              <StatCard
                icon={<ShoppingBag className="size-3.5" aria-hidden />}
                label="ارزش lifetime (LTV)"
                value={formatToman(data.stats.ltv)}
                hint="بدون سفارش‌های لغوشده"
              />
              <StatCard
                icon={<Timer className="size-3.5" aria-hidden />}
                label="میانگین فاصله خریدها"
                value={
                  data.stats.avg_days_between_purchases !== null
                    ? `${toFa(data.stats.avg_days_between_purchases)} روز`
                    : "—"
                }
              />
              <StatCard
                icon={<Package className="size-3.5" aria-hidden />}
                label="سفارش‌ها"
                value={toFa(data.stats.order_count)}
                hint={`${toFa(data.stats.delivered_count)} تحویل‌شده`}
              />
              <StatCard
                icon={<Heart className="size-3.5" aria-hidden />}
                label="علاقه‌مندی‌ها"
                value={toFa(data.stats.favorite_count)}
                hint={`${toFa(data.stats.address_count)} آدرس ثبت‌شده`}
              />
            </div>

            {/* ---- tier assignment (D7b: staff-assigned wholesale) ---- */}
            <div className="mx-6 mt-4 rounded-xl border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-medium">همکار (عمده‌فروشی)</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    دسته‌بندی مشتری است، نه نقش دسترسی — نقش‌ها از «نقش‌ها» جدا مدیریت می‌شوند.
                  </p>
                </div>
                {data.explicit_tier === "wholesale" ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={tierMutation.isPending}
                    onClick={() => tierMutation.mutate(null)}
                  >
                    لغو
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={tierMutation.isPending}
                    onClick={() => setTierDraft("wholesale")}
                  >
                    تایید همکاری
                  </Button>
                )}
              </div>
              {tierDraft === "wholesale" ? (
                <div className="mt-3 flex items-center gap-2">
                  <Input
                    autoFocus
                    value={tierDraft}
                    onChange={(event) => setTierDraft(event.target.value)}
                    aria-label="برای تایید بنویسید: همکار"
                    placeholder="برای تایید بنویسید: همکار"
                  />
                  <Button
                    size="sm"
                    disabled={tierMutation.isPending}
                    onClick={() => tierMutation.mutate("wholesale")}
                  >
                    ثبت
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setTierDraft("")}>
                    انصراف
                  </Button>
                </div>
              ) : null}
            </div>

            {/* ---- management entry points ([FE-08] role trigger lives in the row) ---- */}
            <div className="px-6 pt-4">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => {
                  onClose();
                  onEditRoles(user);
                }}
              >
                <ShieldCheck className="size-4" aria-hidden />
                مدیریت نقش‌ها
              </Button>
            </div>

            {/* ---- tabs: the customer's own sources ---- */}
            <div className="mt-4 flex gap-1 border-b border-border px-6" role="tablist">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  role="tab"
                  aria-selected={tab === item.key}
                  onClick={() => setTab(item.key)}
                  className={`-mb-px border-b-2 px-3 py-2 text-xs transition-colors ${
                    tab === item.key
                      ? "border-terracotta font-medium text-foreground"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
              {tab === "orders" ? (
                data.orders.length === 0 ? (
                  <p className="py-8 text-center text-xs text-muted-foreground">
                    سفارشی ثبت نشده است.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.orders.map((order) => (
                      <li key={order.id} className="rounded-xl border border-border p-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">#{toFa(order.order_number)}</span>
                          <span className="text-muted-foreground">
                            {formatFaDate(order.created_at)}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <StatusBadge status={order.status} />
                          <Badge variant="outline" className="text-[11px]">
                            {PAYMENT_STATUS[order.payment_status] ?? order.payment_status}
                          </Badge>
                          <span className="font-medium">{formatToman(order.total)} تومان</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )
              ) : tab === "addresses" ? (
                data.addresses.length === 0 ? (
                  <p className="py-8 text-center text-xs text-muted-foreground">
                    آدرسی ثبت نشده است.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.addresses.map((address) => (
                      <li key={address.id} className="rounded-xl border border-border p-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 font-medium">
                            <MapPin className="size-3.5" aria-hidden />
                            {address.title}
                            {address.is_default ? (
                              <Badge variant="outline" className="text-[11px]">
                                پیش‌فرض
                              </Badge>
                            ) : null}
                          </span>
                          <span className="text-muted-foreground">{address.phone}</span>
                        </div>
                        <p className="mt-1.5 leading-5 text-muted-foreground">
                          {address.province}، {address.city}، {address.line}
                        </p>
                      </li>
                    ))}
                  </ul>
                )
              ) : data.favorites.length === 0 ? (
                <p className="py-8 text-center text-xs text-muted-foreground">
                  محصولی به علاقه‌مندی‌ها اضافه نشده است.
                </p>
              ) : (
                <ul className="space-y-2 text-xs">
                  {data.favorites.map((favorite) => (
                    <li
                      key={favorite.product_id}
                      className="flex items-center justify-between rounded-xl border border-border p-3"
                    >
                      <span className="font-mono">{favorite.product_id}</span>
                      <span className="text-muted-foreground">
                        {formatFaDate(favorite.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
