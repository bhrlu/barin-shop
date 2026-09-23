import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Mail, MessageSquareText, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type NotificationSettings } from "@/lib/api";
import { formatFaDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";

export const Route = createFileRoute("/_authenticated/admin/settings")({
  head: () => ({
    meta: [
      { title: "تنظیمات — ساندِه" },
      { name: "description", content: "تنظیمات اطلاع‌رسانی فروشگاه ساندِه." },
      { property: "og:title", content: "تنظیمات — ساندِه" },
      { property: "og:description", content: "روشن و خاموش کردن پیامک و ایمیل اطلاع‌رسانی." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminSettings,
});

const QUERY_KEY = ["admin-notification-settings"] as const;

/** DESIGN_SYSTEM §2.3 tone recipes (same as StatusBadge) — no raw palette classes. */
const TONE = {
  positive: "border-sage/40 bg-sage/20 text-sage-deep",
  progress: "border-gold/50 bg-gold/15 text-foreground",
  waiting: "border-border bg-sand text-foreground",
} as const;

type Channel = "sms" | "email";

const CHANNELS: {
  key: Channel;
  title: string;
  provider: string;
  icon: LucideIcon;
  credentials: string;
}[] = [
  {
    key: "sms",
    title: "پیامک",
    provider: "کاوه‌نگار",
    icon: MessageSquareText,
    credentials: "KAVENEGAR_API_KEY",
  },
  {
    key: "email",
    title: "ایمیل",
    provider: "SMTP",
    icon: Mail,
    credentials: "SMTP_HOST / SMTP_FROM",
  },
];

function Pill({ tone, children }: { tone: keyof typeof TONE; children: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        TONE[tone],
      )}
    >
      {children}
    </span>
  );
}

function channelSummary(enabled: boolean, configured: boolean, title: string): string {
  if (enabled && configured) return `${title}های اطلاع‌رسانی برای مشتریان ارسال می‌شوند.`;
  if (enabled)
    return `روشن است، اما تا وقتی اطلاعات سرویس روی سرور تنظیم نشود هیچ ${title}ی ارسال نمی‌شود.`;
  return `خاموش است؛ ${title}ی ارسال نمی‌شود. اعلان‌های داخل حساب کاربری همچنان ثبت می‌شوند.`;
}

function AdminSettings() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => api.adminNotificationSettings(),
    retry: false,
  });
  const update = useMutation({
    mutationFn: (patch: { sms_enabled?: boolean; email_enabled?: boolean }) =>
      api.adminUpdateNotificationSettings(patch),
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
      toast.success("تنظیمات اطلاع‌رسانی ذخیره شد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "ذخیره تنظیمات انجام نشد"),
  });

  return (
    <section className="space-y-6">
      <header>
        <p className="text-[11px] tracking-[0.25em] text-sage-deep">تنظیمات</p>
        <h1 className="mt-2 text-2xl">اطلاع‌رسانی به مشتریان</h1>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-muted-foreground">
          ثبت سفارش، تأیید پرداخت، ارسال، لغو و بازپرداخت همیشه در بخش «اعلان‌ها»ی حساب مشتری ثبت
          می‌شوند. پیامک و ایمیل کانال‌های اضافه‌اند و جدا از هم روشن یا خاموش می‌شوند.
        </p>
      </header>

      {settings.isLoading ? (
        <div className="space-y-4" aria-busy="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-2xl bg-clay" />
          ))}
        </div>
      ) : settings.isError ? (
        <div className="rounded-2xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          {settings.error instanceof ApiError && settings.error.status === 403 ? (
            <p>نقش شما به تنظیمات فروشگاه دسترسی ندارد.</p>
          ) : (
            <>
              <p>دریافت تنظیمات ممکن نشد.</p>
              <button
                type="button"
                onClick={() => void settings.refetch()}
                className="mt-3 text-terracotta underline"
              >
                تلاش دوباره
              </button>
            </>
          )}
        </div>
      ) : settings.data ? (
        <ChannelCards
          data={settings.data}
          pending={update.isPending}
          onToggle={(channel, value) => update.mutate({ [`${channel}_enabled`]: value })}
        />
      ) : null}
    </section>
  );
}

function ChannelCards({
  data,
  pending,
  onToggle,
}: {
  data: NotificationSettings;
  pending: boolean;
  onToggle: (channel: Channel, value: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <article className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <Bell className="mt-0.5 size-5 text-terracotta" aria-hidden />
            <div>
              <h2 id="internal-label" className="text-base font-semibold">
                اعلان‌های داخلی
              </h2>
              <p className="mt-1 text-sm leading-7 text-muted-foreground">
                زنگوله‌ی بالای صفحه و بخش «اعلان‌ها»ی حساب کاربری. همیشه فعال است و با خاموش کردن
                پیامک یا ایمیل از کار نمی‌افتد.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <Switch checked disabled aria-labelledby="internal-label" />
            <Pill tone="positive">همیشه فعال</Pill>
          </div>
        </div>
      </article>

      {CHANNELS.map((channel) => {
        const enabled = data[`${channel.key}_enabled`];
        const configured = data[`${channel.key}_configured`];
        const Icon = channel.icon;
        const labelId = `${channel.key}-label`;
        return (
          <article
            key={channel.key}
            className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <Icon className="mt-0.5 size-5 text-terracotta" aria-hidden />
                <div>
                  <h2 id={labelId} className="text-base font-semibold">
                    {channel.title} ({channel.provider})
                  </h2>
                  <p className="mt-1 text-sm leading-7 text-muted-foreground">
                    {channelSummary(enabled, configured, channel.title)}
                  </p>
                  {channel.key === "email" ? (
                    <p className="mt-1 text-xs leading-6 text-muted-foreground">
                      ایمیل بازیابی رمز عبور هم از همین کانال ارسال می‌شود؛ تا روشن و تنظیم نشود،
                      مشتری لینک بازیابی دریافت نمی‌کند.
                    </p>
                  ) : null}
                  {!configured ? (
                    <p className="mt-2 text-xs leading-6 text-muted-foreground">
                      اطلاعات سرویس فقط از متغیرهای محیطی سرور خوانده می‌شود (
                      <span dir="ltr" className="font-mono tracking-wider">
                        {channel.credentials}
                      </span>
                      ) و در پنل ذخیره نمی‌شود.
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <Switch
                  checked={enabled}
                  disabled={pending}
                  onCheckedChange={(value) => onToggle(channel.key, value)}
                  aria-labelledby={labelId}
                />
                <Pill tone={configured ? "positive" : "waiting"}>
                  {configured ? "سرویس تنظیم شده" : "سرویس تنظیم نشده"}
                </Pill>
                {enabled && configured ? <Pill tone="progress">در حال ارسال</Pill> : null}
              </div>
            </div>
          </article>
        );
      })}

      {data.updated_by && data.updated_at ? (
        <p className="text-xs text-muted-foreground">
          آخرین تغییر: {formatFaDateTime(data.updated_at)}
        </p>
      ) : null}
    </div>
  );
}
