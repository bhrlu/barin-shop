import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";
import {
  api,
  ApiError,
  exportRange,
  type DownloadedFile,
  type ExportFormat,
  type ExportRange,
} from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/orders";

/**
 * Admin export controls (AB-FE-02, spec [FE-02] toolbar export + [BE-08]).
 * Files come from `/admin/export/*` through `src/lib/api.ts` as authenticated
 * blob downloads — never a bare link, which would carry no bearer token. The
 * backend's `orders` capability is the guard; these controls only render on
 * pages whose tab the admin shell grants to that same role set.
 */

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: "csv", label: "CSV" },
  { format: "xlsx", label: "Excel" },
];

function saveFile({ blob, filename }: DownloadedFile, fallback: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  // Chromium's filename sanitiser turns the Persian zero-width non-joiner
  // (U+200C, «سفارش‌های») into "_"; a plain space keeps the name readable
  link.download = (filename ?? fallback).replace(/\u200c/g, " ");
  document.body.appendChild(link);
  link.click();
  link.remove();
  // give the browser time to start the download before releasing the blob
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

function exportErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "نشست شما منقضی شده است؛ دوباره وارد شوید.";
    if (error.status === 403) return "نقش شما اجازهٔ دریافت خروجی را ندارد.";
    if (error.status === 422) return "بازهٔ تاریخ نامعتبر است.";
  }
  return "دریافت فایل انجام نشد. دوباره تلاش کنید.";
}

/** CSV + Excel buttons for one export. One download at a time; the error of the
 * last attempt stays visible until the next one. */
function ExportButtons({
  fetchFile,
  fallbackName,
  disabled = false,
}: {
  fetchFile: (format: ExportFormat) => Promise<DownloadedFile>;
  fallbackName: string;
  disabled?: boolean;
}) {
  const download = useMutation({
    mutationFn: (format: ExportFormat) => fetchFile(format),
    onSuccess: (file, format) => {
      saveFile(file, `${fallbackName}.${format}`);
      toast.success("فایل خروجی آماده شد");
    },
  });

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-2">
        {FORMATS.map(({ format, label }) => {
          const running = download.isPending && download.variables === format;
          return (
            <button
              key={format}
              type="button"
              onClick={() => download.mutate(format)}
              disabled={disabled || download.isPending}
              className="flex h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-xs text-foreground transition-colors hover:border-terracotta hover:text-terracotta disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Download className="size-3.5" aria-hidden />
              {running ? "در حال آماده‌سازی…" : `خروجی ${label}`}
            </button>
          );
        })}
      </div>
      {download.isError ? (
        <p role="alert" className="text-xs text-destructive">
          {exportErrorMessage(download.error)}
        </p>
      ) : null}
    </div>
  );
}

/** `/admin/products`: full catalog export (the endpoint takes no filters). */
export function ProductsExportButtons() {
  return (
    <ExportButtons
      fetchFile={(format) => api.adminExportProducts(format)}
      fallbackName="sande-products"
    />
  );
}

function ymd(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Default window: the last 30 days, today included (matches the backend default). */
function defaultRange(): { from: string; to: string } {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29);
  return { from: ymd(start), to: ymd(today) };
}

/** `/admin/orders`: date range + status → CSV/Excel ledger, plus the sales
 * report for the same range. Dates are local calendar days, both inclusive. */
export function OrdersExportPanel({ className = "" }: { className?: string }) {
  const [dates, setDates] = useState(defaultRange);
  const [status, setStatus] = useState("");
  const [showReport, setShowReport] = useState(false);
  const today = ymd(new Date());

  const complete = Boolean(dates.from && dates.to);
  const invalid = complete && dates.from > dates.to;
  const range: ExportRange | null = complete && !invalid ? exportRange(dates.from, dates.to) : null;

  const field =
    "h-10 rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-terracotta";

  return (
    <section
      aria-label="خروجی سفارش‌ها"
      className={`space-y-3 rounded-2xl border border-border/60 bg-card p-4 shadow-sm ${className}`}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          از تاریخ
          <input
            type="date"
            value={dates.from}
            max={today}
            onChange={(event) => setDates((d) => ({ ...d, from: event.target.value }))}
            className={field}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          تا تاریخ
          <input
            type="date"
            value={dates.to}
            max={today}
            onChange={(event) => setDates((d) => ({ ...d, to: event.target.value }))}
            className={field}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          وضعیت سفارش
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className={field}
          >
            <option value="">همه</option>
            {Object.entries(ORDER_STATUS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <ExportButtons
          fetchFile={(format) => api.adminExportOrders(format, range ?? {}, status || undefined)}
          fallbackName="sande-orders"
          disabled={!range}
        />
      </div>

      {invalid ? (
        <p role="alert" className="text-xs text-destructive">
          «از تاریخ» نباید بعد از «تا تاریخ» باشد.
        </p>
      ) : !complete ? (
        <p role="alert" className="text-xs text-destructive">
          هر دو تاریخ را انتخاب کنید.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          بازه: {formatFaDate(`${dates.from}T12:00:00`)} تا {formatFaDate(`${dates.to}T12:00:00`)}{" "}
          (هر دو روز شامل)
        </p>
      )}

      <details
        className="group"
        onToggle={(event) => setShowReport((event.target as HTMLDetailsElement).open)}
      >
        <summary className="cursor-pointer text-xs text-terracotta select-none">
          گزارش فروش همین بازه
        </summary>
        {showReport ? <SalesReportView range={range} /> : null}
      </details>
    </section>
  );
}

function SalesReportView({ range }: { range: ExportRange | null }) {
  const report = useQuery({
    queryKey: ["admin-sales-report", range?.from, range?.to],
    queryFn: () => api.adminSalesReport(range ?? {}),
    enabled: range !== null,
    retry: false,
  });

  if (!range)
    return <p className="mt-3 text-xs text-muted-foreground">ابتدا بازهٔ معتبر انتخاب کنید.</p>;
  if (report.isLoading) return <div className="mt-3 h-32 animate-pulse rounded-xl bg-muted/60" />;
  if (report.isError)
    return (
      <p role="alert" className="mt-3 text-xs text-destructive">
        {exportErrorMessage(report.error)}
      </p>
    );

  const data = report.data;
  if (!data || data.daily.length === 0)
    return <p className="mt-3 text-xs text-muted-foreground">در این بازه سفارشی ثبت نشده است.</p>;

  const cell = "p-2 text-start";
  return (
    <div className="mt-3 grid gap-4 lg:grid-cols-2">
      <div className="overflow-x-auto">
        <p className="mb-1 text-xs font-semibold">پرفروش‌ترین‌ها (بدون سفارش‌های لغوشده)</p>
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/30 text-muted-foreground">
              <th className={cell}>محصول</th>
              <th className={cell}>تعداد</th>
              <th className={cell}>فروش (تومان)</th>
            </tr>
          </thead>
          <tbody>
            {data.bestSellers.map((item) => (
              <tr key={`${item.productId}-${item.name}`} className="border-t border-border/60">
                <td className={cell}>{item.name}</td>
                <td className={cell}>{toFa(item.units)}</td>
                <td className={cell}>{formatToman(item.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto">
        <p className="mb-1 text-xs font-semibold">فروش روزانه</p>
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-muted/30 text-muted-foreground">
              <th className={cell}>روز (UTC)</th>
              <th className={cell}>سفارش‌ها (همه)</th>
              <th className={cell}>فروش بدون لغوشده‌ها (تومان)</th>
            </tr>
          </thead>
          <tbody>
            {data.daily.map((row) => (
              <tr key={row.day} className="border-t border-border/60">
                <td className={cell}>{formatFaDate(`${row.day}T12:00:00Z`)}</td>
                <td className={cell}>{toFa(row.orders)}</td>
                <td className={cell}>{formatToman(row.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.monthly.length > 1 ? (
          <p className="mt-2 text-xs text-muted-foreground">
            ماه‌های میلادی:{" "}
            {data.monthly
              .map((row) => `${toFa(row.month)}: ${formatToman(row.revenue)} تومان`)
              .join(" · ")}
          </p>
        ) : null}
      </div>
    </div>
  );
}
