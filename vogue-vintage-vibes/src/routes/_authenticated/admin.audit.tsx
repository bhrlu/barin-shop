import { createFileRoute } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScrollText } from "lucide-react";
import { api, ApiError, type AuditLogEntry } from "@/lib/api";
import { formatFaDateTime, toFa } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/admin/audit")({
  head: () => ({
    meta: [
      { title: "گزارش فعالیت‌ها — ساندِه" },
      { name: "description", content: "ردپای تغییرات مدیریتی فروشگاه ساندِه." },
      { property: "og:title", content: "گزارش فعالیت‌ها — ساندِه" },
      { property: "og:description", content: "چه کسی، چه زمانی و از کجا چه چیزی را تغییر داد." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminAudit,
});

/** Rows per page. The endpoint has no total, so one extra row is requested to
 * learn whether a next page exists. */
const PAGE_SIZE = 25;

/** Mirrors `ACTIONS` in backend/app/services/audit.py. An action missing here
 * still renders (raw name); it just can't be picked from the filter. */
const ACTION_LABELS: Record<string, string> = {
  update_order_status: "تغییر وضعیت سفارش",
  update_order_payment_status: "تغییر وضعیت پرداخت",
  update_order_tracking_code: "ثبت کد رهگیری",
  cancel_order: "لغو سفارش",
  resolve_refund: "رسیدگی به بازپرداخت",
  create_product: "ایجاد محصول",
  update_product: "ویرایش محصول",
  delete_product: "حذف محصول",
  create_variant: "ایجاد تنوع",
  update_variant: "ویرایش تنوع",
  delete_variant: "حذف تنوع",
  create_coupon: "ایجاد کد تخفیف",
  update_coupon: "ویرایش کد تخفیف",
  delete_coupon: "حذف کد تخفیف",
  moderate_review: "بررسی نظر",
  delete_review: "حذف نظر",
  update_user_roles: "تغییر نقش کاربر",
};

/** Mirrors `_ENTITY_TYPES` in backend/app/services/audit.py. */
const ENTITY_LABELS: Record<string, string> = {
  order: "سفارش",
  product: "محصول",
  variant: "تنوع محصول",
  coupon: "کد تخفیف",
  review: "نظر",
  user: "کاربر",
};

const STAFF_ROLES = new Set(["admin", "super_admin", "order_manager", "support"]);

type Filters = { action: string; entity_type: string; entity_id: string; admin_id: string };

const EMPTY_FILTERS: Filters = { action: "", entity_type: "", entity_id: "", admin_id: "" };

function AdminAudit() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [entityIdDraft, setEntityIdDraft] = useState("");
  const [page, setPage] = useState(1);

  const logs = useQuery({
    queryKey: ["admin-audit-logs", filters, page],
    queryFn: () =>
      api.adminAuditLogs({
        ...filters,
        limit: PAGE_SIZE + 1,
        offset: (page - 1) * PAGE_SIZE,
      }),
    retry: false,
  });

  // staff accounts for the admin filter; /admin/users needs the same
  // admin/super_admin capability as the audit log itself
  const staff = useQuery({
    queryKey: ["admin-users", "all"],
    queryFn: () => api.adminUsers(),
    select: (data) =>
      (Array.isArray(data) ? data : data.items).filter((user) =>
        user.roles.some((role) => STAFF_ROLES.has(role)),
      ),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const update = (patch: Partial<Filters>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };

  const submitEntityId = (event: FormEvent) => {
    event.preventDefault();
    update({ entity_id: entityIdDraft.trim() });
  };

  const reset = () => {
    setFilters(EMPTY_FILTERS);
    setEntityIdDraft("");
    setPage(1);
  };

  const rows = (logs.data ?? []).slice(0, PAGE_SIZE);
  const hasNext = (logs.data?.length ?? 0) > PAGE_SIZE;
  const filtered = Object.values(filters).some(Boolean);

  const select =
    "h-10 rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-terracotta";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg">گزارش فعالیت‌ها</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          هر تغییر مدیریتی با نام کارمند، زمان، نشانی IP و مقدار قبل و بعد ثبت می‌شود.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-border/60 bg-card p-4">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          عملیات
          <select
            className={select}
            value={filters.action}
            onChange={(event) => update({ action: event.target.value })}
          >
            <option value="">همه</option>
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          موجودیت
          <select
            className={select}
            value={filters.entity_type}
            onChange={(event) => update({ entity_type: event.target.value })}
          >
            <option value="">همه</option>
            {Object.entries(ENTITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          کارمند
          <select
            className={select}
            value={filters.admin_id}
            onChange={(event) => update({ admin_id: event.target.value })}
            disabled={staff.isError}
          >
            <option value="">همه</option>
            {(staff.data ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name ?? user.email ?? user.id}
              </option>
            ))}
          </select>
        </label>
        <form
          onSubmit={submitEntityId}
          className="flex flex-col gap-1 text-xs text-muted-foreground"
        >
          <label htmlFor="audit-entity-id">شناسه موجودیت</label>
          <div className="flex gap-2">
            <input
              id="audit-entity-id"
              dir="ltr"
              value={entityIdDraft}
              onChange={(event) => setEntityIdDraft(event.target.value)}
              placeholder="UUID"
              className={`${select} w-56 font-mono`}
            />
            <button
              type="submit"
              className="h-10 rounded-xl border border-border px-3 text-xs text-foreground hover:bg-muted/60"
            >
              اعمال
            </button>
          </div>
        </form>
        {filtered ? (
          <button
            type="button"
            onClick={reset}
            className="h-10 px-2 text-xs text-terracotta underline-offset-4 hover:underline"
          >
            حذف فیلترها
          </button>
        ) : null}
      </div>

      {logs.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-2xl bg-muted/60" />
          ))}
        </div>
      ) : logs.isError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700">
          <p>
            {logs.error instanceof ApiError && logs.error.status === 403
              ? "نقش شما به گزارش فعالیت‌ها دسترسی ندارد."
              : "خواندن گزارش فعالیت‌ها انجام نشد."}
          </p>
          <button
            type="button"
            onClick={() => void logs.refetch()}
            className="mt-3 text-xs underline underline-offset-4"
          >
            تلاش دوباره
          </button>
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-12 text-center">
          <ScrollText className="mb-3 h-10 w-10 text-muted-foreground/50" aria-hidden />
          <p className="text-sm font-semibold">موردی یافت نشد</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {filtered
              ? "هیچ فعالیتی با این فیلترها ثبت نشده است."
              : "هنوز هیچ فعالیت مدیریتی ثبت نشده است."}
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {rows.map((entry) => (
            <AuditRow key={entry.id} entry={entry} />
          ))}
        </ul>
      )}

      {!logs.isError && (page > 1 || hasNext) ? (
        <nav className="flex items-center justify-center gap-3" aria-label="صفحه‌بندی">
          <button
            type="button"
            disabled={page <= 1 || logs.isFetching}
            onClick={() => setPage((current) => current - 1)}
            className="flex h-9 items-center gap-1 rounded-lg border px-3 text-sm transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" aria-hidden />
            جدیدتر
          </button>
          <span className="text-sm text-muted-foreground">صفحه {toFa(page)}</span>
          <button
            type="button"
            disabled={!hasNext || logs.isFetching}
            onClick={() => setPage((current) => current + 1)}
            className="flex h-9 items-center gap-1 rounded-lg border px-3 text-sm transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
          >
            قدیمی‌تر
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </button>
        </nav>
      ) : null}
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditLogEntry }) {
  const oldValues = entry.old_values ?? {};
  const newValues = entry.new_values ?? {};
  const keys = Array.from(new Set([...Object.keys(oldValues), ...Object.keys(newValues)])).sort();

  return (
    <li className="rounded-2xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm">
            <span className="font-semibold">{ACTION_LABELS[entry.action] ?? entry.action}</span>
            <span className="ms-2 rounded-full bg-sand px-2 py-0.5 text-[11px]">
              {ENTITY_LABELS[entry.entity_type] ?? entry.entity_type}
            </span>
          </p>
          <p className="font-mono text-[11px] tracking-wider text-muted-foreground" dir="ltr">
            {entry.entity_id}
          </p>
        </div>
        <div className="space-y-1 text-end text-xs text-muted-foreground">
          <p>
            <time dateTime={entry.created_at ?? undefined}>
              {formatFaDateTime(entry.created_at) || "—"}
            </time>
          </p>
          <p>
            {entry.admin_name ?? entry.admin_email ?? "کاربر حذف‌شده"}
            {" · "}
            <span className="font-mono tracking-wider" dir="ltr">
              {entry.ip_address ?? "IP نامشخص"}
            </span>
          </p>
        </div>
      </div>

      {keys.length > 0 ? (
        <details className="mt-3 group">
          <summary className="cursor-pointer text-xs text-terracotta select-none">
            جزئیات تغییر ({toFa(keys.length)} فیلد)
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-muted/30 text-muted-foreground">
                  <th className="p-2 text-start font-medium">فیلد</th>
                  <th className="p-2 text-start font-medium">مقدار قبلی</th>
                  <th className="p-2 text-start font-medium">مقدار جدید</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key} className="border-t border-border/60 align-top">
                    <td className="p-2 font-mono" dir="ltr">
                      {key}
                    </td>
                    <td className="p-2">
                      <AuditValue present={key in oldValues} value={oldValues[key]} />
                    </td>
                    <td className="p-2">
                      <AuditValue present={key in newValues} value={newValues[key]} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </li>
  );
}

/** Renders one JSON value verbatim (LTR, monospace); a key missing on one side
 * shows as «—», an explicit null as `null`. */
function AuditValue({ present, value }: { present: boolean; value: unknown }) {
  if (!present) return <span className="text-muted-foreground">—</span>;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 1);
  return (
    <pre className="max-w-xs whitespace-pre-wrap break-all font-mono text-[11px]" dir="ltr">
      {text}
    </pre>
  );
}
