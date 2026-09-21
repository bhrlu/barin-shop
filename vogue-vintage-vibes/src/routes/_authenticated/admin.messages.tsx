import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, MailCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type ContactMessageStatus } from "@/lib/api";
import { formatFaDate, toFa } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/admin/messages")({
  head: () => ({
    meta: [
      { title: "صندوق پیام‌ها — ساندِه" },
      { name: "description", content: "پیام‌های ثبت‌شده از فرم تماس فروشگاه ساندِه." },
      { property: "og:title", content: "صندوق پیام‌ها — ساندِه" },
      { property: "og:description", content: "خواندن و پاسخ‌دادن به پیام‌های فرم تماس." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminMessages,
});

const FILTERS = [
  { value: "", label: "همه" },
  { value: "new", label: "پاسخ‌داده‌نشده" },
  { value: "answered", label: "پاسخ‌داده‌شده" },
] as const;

type Filter = (typeof FILTERS)[number]["value"];

/**
 * Admin contact inbox (F2.1b): reads `GET /admin/contact-messages` and marks
 * messages answered via `PATCH /admin/contact-messages/{id}`. Answering itself
 * happens over email/phone — the sender's `contact` field is copy-to-clipboard
 * so support can reach them without leaving the page.
 */
function AdminMessages() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("");

  const messages = useQuery({
    queryKey: ["admin-contact-messages", filter],
    queryFn: () => api.adminContactMessages(filter === "" ? undefined : (filter as ContactMessageStatus)),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-contact-messages"] });
  };

  const mark = useMutation({
    mutationFn: (input: { id: string; status: ContactMessageStatus }) =>
      api.markContactMessage(input.id, input.status),
    onSuccess: (message) => {
      refresh();
      toast.success(message.status === "answered" ? "پیام پاسخ‌داده‌شده علامت خورد" : "پیام بازگشایی شد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "تغییر وضعیت انجام نشد"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteContactMessage(id),
    onSuccess: () => {
      refresh();
      toast.success("پیام حذف شد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "حذف انجام نشد"),
  });

  const copyContact = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success("در حافظه کپی شد");
    } catch {
      toast.error("کپی انجام نشد");
    }
  };

  const list = messages.data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-lg">
          پیام‌های مشتریان {list.length ? `(${toFa(list.length)})` : ""}
        </h2>
        <div className="flex gap-2">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setFilter(option.value)}
              aria-pressed={filter === option.value}
              className={
                filter === option.value
                  ? "rounded-full border border-terracotta bg-terracotta/10 px-4 py-2 text-xs text-terracotta"
                  : "rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {messages.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-3xl bg-clay" />
          ))}
        </div>
      ) : messages.isError ? (
        <p className="text-sm text-terracotta">خواندن پیام‌ها انجام نشد.</p>
      ) : list.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          پیامی با این وضعیت وجود ندارد.
        </div>
      ) : (
        <ul className="space-y-4">
          {list.map((message) => {
            const answered = message.status === "answered";
            return (
              <li key={message.id} className="rounded-3xl border border-border p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm">
                      {message.name}
                      <span
                        className={`ms-2 inline-block rounded-full px-2 py-0.5 text-[11px] ${
                          answered ? "bg-sand text-sage-deep" : "bg-terracotta/10 text-terracotta"
                        }`}
                      >
                        {answered ? "پاسخ‌داده‌شده" : "جدید"}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatFaDate(message.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => void copyContact(message.contact)}
                      title="کپی راه تماس"
                      className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <Copy className="size-3.5" />
                      <span className="font-mono tracking-wider">{message.contact}</span>
                    </button>
                  </div>
                </div>

                <p className="mt-3 rounded-2xl border-s-4 border-terracotta bg-muted/40 p-3 text-sm leading-7">
                  {message.message}
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => mark.mutate({ id: message.id, status: answered ? "new" : "answered" })}
                    disabled={mark.isPending}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                  >
                    <MailCheck className="size-3.5" />
                    {answered ? "علامت‌زدن به‌عنوان جدید" : "علامت‌زدن به‌عنوان پاسخ‌داده‌شده"}
                  </button>
                  <button
                    type="button"
                    onClick={() => remove.mutate(message.id)}
                    disabled={remove.isPending}
                    className="flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
                  >
                    <Trash2 className="size-3.5" />
                    حذف پیام
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
