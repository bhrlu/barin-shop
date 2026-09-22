import { Link } from "@tanstack/react-router";
import { Bell, BellOff } from "lucide-react";
import { useState } from "react";
import type { AppNotification } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatFaDateTime, toFa } from "@/lib/format";
import {
  useNotificationActions,
  useNotificationList,
  useUnreadNotifications,
} from "@/lib/notifications";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/** Items the dropdown shows; the full, paginated list is /account/notifications. */
const PREVIEW_SIZE = 6;

/** One notification: unread dot + bold title while unread. Opening it marks it
 * read; a notification about an order links to that order. */
export function NotificationRow({
  notification,
  onOpen,
  className,
}: {
  notification: AppNotification;
  onOpen: (notification: AppNotification) => void;
  className?: string;
}) {
  const unread = !notification.read_at;
  const orderId = notification.data?.order_id;
  const body = (
    <>
      <span
        aria-hidden
        className={cn(
          "mt-1.5 size-2 shrink-0 rounded-full",
          unread ? "bg-terracotta" : "bg-transparent",
        )}
      />
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            "block text-sm",
            unread ? "font-semibold text-foreground" : "text-foreground/80",
          )}
        >
          {notification.title}
          {unread ? <span className="sr-only"> (خوانده‌نشده)</span> : null}
        </span>
        <span className="mt-1 block text-xs leading-6 text-muted-foreground">
          {notification.message}
        </span>
        <span className="mt-1 block text-[11px] text-muted-foreground/80">
          {formatFaDateTime(notification.created_at)}
        </span>
      </span>
    </>
  );
  const rowClass = cn(
    "flex w-full items-start gap-3 px-4 py-3 text-start transition-colors hover:bg-muted/40",
    unread && "bg-terracotta/5",
    className,
  );
  if (orderId) {
    return (
      <Link
        to="/account/order/$orderId"
        params={{ orderId }}
        onClick={() => onOpen(notification)}
        className={rowClass}
      >
        {body}
      </Link>
    );
  }
  return (
    <button type="button" onClick={() => onOpen(notification)} className={rowClass}>
      {body}
    </button>
  );
}

/** Header bell (B2.1): unread count badge + a popover with the latest items,
 * mark-all-read and a link to the full list. Renders nothing for guests. */
export function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const unread = useUnreadNotifications();
  const list = useNotificationList({ page: 1, pageSize: PREVIEW_SIZE }, open);
  const { markRead, markAllRead } = useNotificationActions();

  if (!user) return null;

  const count = unread.data?.unread ?? 0;
  const items = list.data?.items ?? [];
  const openItem = (notification: AppNotification) => {
    if (!notification.read_at) markRead.mutate(notification.id);
    if (notification.data?.order_id) setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={count > 0 ? `اعلان‌ها، ${toFa(count)} خوانده‌نشده` : "اعلان‌ها"}
          className="relative text-foreground/70 transition-colors hover:text-foreground"
        >
          <Bell className="size-5" />
          {count > 0 && (
            <span className="absolute -top-2 -left-2 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-primary px-1 text-[10px] text-primary-foreground">
              {count > 99 ? `${toFa(99)}+` : toFa(count)}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        dir="rtl"
        className="w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border-border/80 p-0 shadow-lg"
      >
        <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
          <p className="text-sm font-semibold">اعلان‌ها</p>
          <button
            type="button"
            onClick={() => markAllRead.mutate()}
            disabled={count === 0 || markAllRead.isPending}
            className="text-xs text-terracotta transition-opacity hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:no-underline"
          >
            خواندن همه
          </button>
        </div>

        <div className="max-h-[min(24rem,60vh)] overflow-y-auto">
          {list.isLoading ? (
            <div className="space-y-3 p-4" aria-busy="true">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="h-14 animate-pulse rounded-xl bg-clay" />
              ))}
            </div>
          ) : list.isError ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <p>دریافت اعلان‌ها ممکن نشد.</p>
              <button
                type="button"
                onClick={() => void list.refetch()}
                className="mt-2 text-xs text-terracotta underline"
              >
                تلاش دوباره
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-8 text-center">
              <BellOff className="size-6 text-muted-foreground/60" aria-hidden />
              <p className="text-sm text-muted-foreground">اعلانی ندارید.</p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {items.map((notification) => (
                <li key={notification.id}>
                  <NotificationRow notification={notification} onOpen={openItem} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <Link
          to="/account/notifications"
          onClick={() => setOpen(false)}
          className="block border-t border-border/60 px-4 py-3 text-center text-xs text-terracotta hover:bg-muted/40"
        >
          مشاهده همه اعلان‌ها
        </Link>
      </PopoverContent>
    </Popover>
  );
}
