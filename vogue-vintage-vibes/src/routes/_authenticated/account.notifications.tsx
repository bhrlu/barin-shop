import { createFileRoute } from "@tanstack/react-router";
import { BellOff } from "lucide-react";
import { useEffect, useState } from "react";
import type { AppNotification } from "@/lib/api";
import { toFa } from "@/lib/format";
import {
  useNotificationActions,
  useNotificationList,
  useUnreadNotifications,
} from "@/lib/notifications";
import { cn } from "@/lib/utils";
import { NotificationRow } from "@/components/NotificationBell";
import { Pager } from "@/components/Pager";

export const Route = createFileRoute("/_authenticated/account/notifications")({
  head: () => ({
    meta: [
      { title: "اعلان‌ها — ساندِه" },
      { name: "description", content: "اعلان‌های سفارش، پرداخت و بازپرداخت شما در ساندِه." },
      { property: "og:title", content: "اعلان‌ها — ساندِه" },
      { property: "og:description", content: "اعلان‌های سفارش و بازپرداخت شما." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: NotificationsTab,
});

const PAGE_SIZE = 10;

type Filter = "all" | "unread";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "همه" },
  { key: "unread", label: "خوانده‌نشده" },
];

function NotificationsTab() {
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const list = useNotificationList({ page, pageSize: PAGE_SIZE, unread: filter === "unread" });
  const unread = useUnreadNotifications();
  const { markRead, markAllRead } = useNotificationActions();
  const unreadCount = unread.data?.unread ?? 0;

  // reading items under the «unread» filter shrinks the list: never sit on a
  // page that no longer exists
  const lastPage = list.data?.pages;
  useEffect(() => {
    if (lastPage && page > lastPage) setPage(lastPage);
  }, [page, lastPage]);

  const openItem = (notification: AppNotification) => {
    if (!notification.read_at) markRead.mutate(notification.id);
  };
  const choose = (next: Filter) => {
    setFilter(next);
    setPage(1);
  };

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2" role="group" aria-label="فیلتر اعلان‌ها">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={filter === item.key}
              onClick={() => choose(item.key)}
              className={cn(
                "rounded-full border px-4 py-1.5 text-xs transition-colors",
                filter === item.key
                  ? "border-terracotta bg-terracotta/10 text-terracotta"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {item.label}
              {item.key === "unread" && unreadCount > 0 ? ` (${toFa(unreadCount)})` : ""}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => markAllRead.mutate()}
          disabled={unreadCount === 0 || markAllRead.isPending}
          className="rounded-full border border-border px-4 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          علامت‌گذاری همه به‌عنوان خوانده‌شده
        </button>
      </div>

      {list.isLoading ? (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-2xl bg-clay" />
          ))}
        </div>
      ) : list.isError ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          <p>دریافت اعلان‌ها ممکن نشد.</p>
          <button
            type="button"
            onClick={() => void list.refetch()}
            className="mt-3 text-terracotta underline"
          >
            تلاش دوباره
          </button>
        </div>
      ) : !list.data?.items.length ? (
        <div className="flex flex-col items-center gap-3 rounded-3xl border border-dashed border-border p-12 text-center">
          <BellOff className="size-7 text-muted-foreground/60" aria-hidden />
          <p className="text-sm text-muted-foreground">
            {filter === "unread"
              ? "اعلان خوانده‌نشده‌ای ندارید."
              : "هنوز اعلانی برای شما ثبت نشده است."}
          </p>
        </div>
      ) : (
        <>
          <ul className="divide-y divide-border overflow-hidden rounded-3xl border border-border">
            {list.data.items.map((notification) => (
              <li
                key={notification.id}
                className="flex flex-wrap items-center gap-2 sm:flex-nowrap"
              >
                <NotificationRow
                  notification={notification}
                  onOpen={openItem}
                  className="flex-1 px-5 py-4"
                />
                {!notification.read_at ? (
                  <button
                    type="button"
                    onClick={() => markRead.mutate(notification.id)}
                    disabled={markRead.isPending}
                    className="mx-5 mb-3 shrink-0 text-xs text-terracotta hover:underline disabled:opacity-40 sm:mb-0"
                  >
                    خوانده شد
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          <Pager
            page={list.data.page}
            pages={list.data.pages}
            total={list.data.total}
            onChange={setPage}
          />
        </>
      )}
    </section>
  );
}
