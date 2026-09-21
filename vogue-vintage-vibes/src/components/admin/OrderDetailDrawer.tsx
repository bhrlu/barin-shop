import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, PackageCheck, Printer, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, type Order } from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { resolveImageUrls } from "@/lib/catalog";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/** The four fulfilment steps shown in the stepper ([FE-05]). `cancelled` and
 * `delivered` are terminal states handled outside the linear flow. */
const STEPS: { key: string; label: string }[] = [
  { key: "pending", label: "ثبت سفارش" },
  { key: "processing", label: "در حال آماده‌سازی" },
  { key: "shipped", label: "تحویل به پست/پیک" },
  { key: "delivered", label: "تحویل به مشتری" },
];
const stepIndex = (status: string) => STEPS.findIndex((s) => s.key === status);

/** Next linear status; pending advances even when payment is still unpaid. */
const NEXT_STATUS: Record<string, string | undefined> = {
  pending: "processing",
  processing: "shipped",
  shipped: "delivered",
};

const METHOD_LABELS: Record<string, string> = {
  online: "پرداخت آنلاین",
  cod: "پرداخت در محل",
};

/** Shared pieces of the print layout. Screen styling (grid, tokens, scroll)
 * lives on wrappers *around* these so `@media print` can strip everything but
 * the invoice DOM. */
function InvoiceHeader() {
  return (
    <div className="print:mb-6">
      <div className="flex items-start justify-between gap-4 print:block">
        <div>
          <p className="text-xl font-bold tracking-[0.2em] print:text-2xl">SÂNDÉ</p>
          <p className="mt-1 text-[11px] tracking-[0.25em] text-sage-deep">فاکتور فروش</p>
        </div>
        <div className="text-left text-xs text-muted-foreground print:text-right">
          <p className="font-semibold text-foreground">فاکتور رسمی</p>
          <p className="mt-0.5">نگاه‌داری این فاکتور بابت گارانتی الزامی است.</p>
        </div>
      </div>
      <div className="mt-4 border-t border-border" />
    </div>
  );
}

/** Print invoice. Portalled into `#__se_invoice_root` on <body> so the global
 * `@media print` rules can hide the whole app and show only this. */
function OrderInvoice({ order }: { order: Order }) {
  const address = order.shipping_address ?? {};
  return (
    <div id="invoice-print-root">
      <InvoiceHeader />
      <div className="grid grid-cols-2 gap-3 text-xs print:text-sm">
        <div>
          <p>
            شماره سفارش: <span className="font-mono font-semibold">#{toFa(order.order_number)}</span>
          </p>
          <p className="mt-1">تاریخ ثبت: {formatFaDate(order.created_at)}</p>
          <p className="mt-1">
            وضعیت پرداخت:{" "}
            {PAYMENT_STATUS[order.payment_status] ?? PAYMENT_STATUS["unpaid"]}
          </p>
        </div>
        <div>
          <p>خریدار: {address["receiver"] ?? "—"}</p>
          <p className="mt-1">تلفن: {toFa(address["phone"] ?? "—")}</p>
          <p className="mt-1">
            نشانی:{" "}
            {[
              address["province"],
              address["city"],
              address["line"],
            ]
              .filter(Boolean)
              .join("، ")}
          </p>
        </div>
      </div>

      <table className="mt-6 w-full border-collapse text-xs print:text-sm">
        <thead>
          <tr className="border-b border-foreground/40 text-right">
            <th className="py-2 text-right font-semibold">کالا</th>
            <th className="py-2 text-right font-semibold">مشخصات</th>
            <th className="py-2 text-center font-semibold">تعداد</th>
            <th className="py-2 text-left font-semibold">مبلغ کل (تومان)</th>
          </tr>
        </thead>
        <tbody>
          {order.items.map((item) => (
            <tr key={item.id} className="border-b border-border/60">
              <td className="py-2 align-top">{item.name}</td>
              <td className="py-2 align-top text-muted-foreground">
                {item.color ?? "—"} / سایز {toFa(item.size ?? "—")}
              </td>
              <td className="py-2 text-center align-top">{toFa(item.quantity)}</td>
              <td className="py-2 text-left align-top">
                {formatToman(item.price * item.quantity)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3} className="pt-2 text-left">
              جمع کل:
            </td>
            <td className="pt-2 text-left font-semibold">{formatToman(Number(order.total))}</td>
          </tr>
        </tfoot>
      </table>

      <p className="mt-6 text-[10px] text-muted-foreground print:text-xs">
        این فاکتور به‌صورت الکترونیکی صادر شده است — فروشگاه ساندِه.
      </p>
    </div>
  );
}

/** Track whether an order drawer is open, and provide the body-level mount
 * point the global `@media print` rules use to hide the app. The portal node
 * exists only while a printable order is open, so Ctrl+P outside the drawer
 * prints normally. */
function useOrderPrintPortal(open: boolean): HTMLElement | null {
  const [host, setHost] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    document.body.dataset["orderPrintOpen"] = "true";
    const el = document.createElement("div");
    el.id = "__se_invoice_root";
    document.body.appendChild(el);
    setHost(el);
    return () => {
      delete document.body.dataset["orderPrintOpen"];
      el.remove();
    };
  }, [open]);
  return host;
}

export function OrderDetailDrawer({
  order,
  onClose,
}: {
  order: Order | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [resolvedImages, setResolvedImages] = useState<Record<string, string>>({});
  const [tracking, setTracking] = useState("");

  const printHost = useOrderPrintPortal(Boolean(order));

  useEffect(() => {
    setTracking(order?.tracking_code ?? "");
  }, [order?.id, order?.tracking_code]);

  // item thumbnails may be storage paths that need signing (B0.4 images rule)
  useEffect(() => {
    let alive = true;
    const refs = (order?.items ?? [])
      .map((item) => item.image)
      .filter((image): image is string => Boolean(image));
    if (refs.length === 0) {
      setResolvedImages({});
      return;
    }
    resolveImageUrls(refs)
      .then((urls) => {
        if (!alive) return;
        const map: Record<string, string> = {};
        refs.forEach((ref, index) => {
          map[ref] = urls[index] ?? "";
        });
        setResolvedImages(map);
      })
      .catch(() => {
        if (alive) setResolvedImages({});
      });
    return () => {
      alive = false;
    };
  }, [order?.items.map((i) => i.image ?? "").join("|")]);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-kpis"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "kpis"] });
  };

  const update = useMutation({
    mutationFn: async (patch: { status?: string; tracking_code?: string | null }) =>
      api.patchOrder(order!.id, patch),
    onSuccess: () => {
      invalidate();
      toast.success("سفارش به‌روزرسانی شد");
    },
    onError: () => toast.error("به‌روزرسانی ناموفق بود"),
  });

  const cancel = useMutation({
    mutationFn: async () => api.cancelOrder(order!.id),
    onSuccess: () => {
      invalidate();
      toast.success("سفارش لغو شد");
    },
    onError: () => toast.error("لغو سفارش ناموفق بود — شاید امکان‌پذیر نیست"),
  });

  if (!order) return null;

  const address = order.shipping_address ?? {};
  const status = order.status;
  const isCancelled = status === "cancelled";
  const isDelivered = status === "delivered";
  const nextStatus = NEXT_STATUS[status];
  const currentStep = stepIndex(status);

  const copyAddress = async () => {
    const text = [
      address["receiver"],
      address["phone"],
      [address["province"], address["city"]].filter(Boolean).join("، "),
      address["line"],
      address["postal_code"] ? `کد پستی: ${address["postal_code"]}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success("آدرس گیرنده کپی شد");
    } catch {
      toast.error("کپی انجام نشد");
    }
  };

  const printInvoice = () => window.print();

  return (
    <Sheet open={Boolean(order)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="left"
        className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-lg"
      >
        {/* ---- screen-only chrome ---- */}
        <SheetHeader className="border-b border-border px-6 pb-4 pt-6 text-right">
          <SheetTitle className="flex items-center justify-between gap-3 text-base">
            <span>سفارش #{toFa(order.order_number)}</span>
            <span className="text-xs font-normal text-muted-foreground">
              {formatFaDate(order.created_at)}
            </span>
          </SheetTitle>
          <SheetDescription className="sr-only">جزئیات و پردازش سفارش</SheetDescription>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-secondary px-2.5 py-1">
              {ORDER_STATUS[status] ?? status}
            </span>
            <span className="rounded-full bg-secondary px-2.5 py-1">
              {PAYMENT_STATUS[order.payment_status] ?? order.payment_status}
            </span>
            <span className="font-mono text-xs">
              {formatToman(Number(order.total))} تومان
            </span>
          </div>
        </SheetHeader>

        {/* ---- fulfilment stepper ([FE-05]) ---- */}
        <section className="border-b border-border px-6 py-5" aria-label="مراحل پردازش سفارش">
          <ol className="flex items-start justify-between gap-1">
            {STEPS.map((step, index) => {
              const done = currentStep > index;
              const active = currentStep === index;
              return (
                <li key={step.key} className="flex flex-1 flex-col items-center gap-1.5">
                  <div className="flex w-full items-center">
                    <span
                      className={`h-0.5 flex-1 ${
                        index === 0
                          ? "bg-transparent"
                          : done || active
                            ? "bg-terracotta"
                            : "bg-border"
                      }`}
                    />
                    <span
                      aria-current={active ? "step" : undefined}
                      className={`flex size-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold ${
                        done
                          ? "border-terracotta bg-terracotta text-white"
                          : active
                            ? "border-terracotta bg-terracotta/10 text-terracotta"
                            : "border-border bg-background text-muted-foreground"
                      }`}
                    >
                      {toFa(index + 1)}
                    </span>
                    <span
                      className={`h-0.5 flex-1 ${
                        index === STEPS.length - 1
                          ? "bg-transparent"
                          : done
                            ? "bg-terracotta"
                            : "bg-border"
                      }`}
                    />
                  </div>
                  <span
                    className={`text-center text-[11px] leading-tight ${
                      done || active ? "text-foreground" : "text-muted-foreground"
                    }`}
                  >
                    {step.label}
                  </span>
                </li>
              );
            })}
          </ol>
          {isCancelled ? (
            <p className="mt-3 rounded-xl bg-destructive/10 px-3 py-2 text-xs text-destructive">
              این سفارش لغو شده است.
            </p>
          ) : nextStatus ? (
            <Button
              onClick={() => update.mutate({ status: nextStatus })}
              disabled={update.isPending}
              className="mt-4 w-full bg-terracotta text-white hover:bg-terracotta/90"
            >
              {update.isPending
                ? "در حال ثبت…"
                : `تغییر وضعیت به ${ORDER_STATUS[nextStatus] ?? nextStatus}`}
            </Button>
          ) : (
            <p className="mt-4 flex items-center justify-center gap-1.5 text-xs text-sage-deep">
              <ShieldCheck className="size-4" />
              سفارش تحویل داده شده است.
            </p>
          )}
        </section>

        {/* ---- customer shipping box ---- */}
        <section className="border-b border-border px-6 py-5" aria-label="نشانی گیرنده">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">گیرنده</h3>
            <button
              type="button"
              onClick={() => void copyAddress()}
              className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground print:hidden"
            >
              <Copy className="size-3.5" />
              کپی آدرس گیرنده
            </button>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <dt className="text-muted-foreground">نام</dt>
              <dd className="mt-0.5">{address["receiver"] ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">تلفن</dt>
              <dd className="mt-0.5 font-mono" dir="ltr">
                {toFa(address["phone"] ?? "—")}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-muted-foreground">نشانی</dt>
              <dd className="mt-0.5 leading-relaxed">
                {[
                  address["province"],
                  address["city"],
                  address["line"],
                ]
                  .filter(Boolean)
                  .join("، ") || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">کد پستی</dt>
              <dd className="mt-0.5 font-mono" dir="ltr">
                {toFa(address["postal_code"] ?? "—")}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">روش پرداخت</dt>
              <dd className="mt-0.5">
                {METHOD_LABELS[order.payment_method] ?? order.payment_method}
              </dd>
            </div>
          </dl>
        </section>

        {/* ---- itemised breakdown ---- */}
        <section className="border-b border-border px-6 py-5" aria-label="اقلام سفارش">
          <h3 className="text-sm font-semibold">اقلام</h3>
          <ul className="mt-3 space-y-3">
            {order.items.map((item) => {
              const thumb = item.image ? resolvedImages[item.image] : undefined;
              return (
                <li key={item.id} className="flex items-start gap-3">
                  {thumb ? (
                    <img
                      src={thumb}
                      alt=""
                      className="size-12 shrink-0 rounded-lg border border-border object-cover"
                    />
                  ) : (
                    <div className="size-12 shrink-0 rounded-lg border border-border bg-secondary" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{item.name}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {item.color ?? "—"} / سایز {toFa(item.size ?? "—")} · ×{toFa(item.quantity)}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm">
                    {formatToman(item.price * item.quantity)} تومان
                  </span>
                </li>
              );
            })}
          </ul>
          <dl className="mt-4 space-y-1.5 border-t border-border pt-3 text-xs">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">جمع کالاها</dt>
              <dd>{formatToman(Number(order.subtotal))} تومان</dd>
            </div>
            {Number(order.discount) > 0 ? (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">تخفیف</dt>
                <dd className="text-destructive">−{formatToman(Number(order.discount))} تومان</dd>
              </div>
            ) : null}
            <div className="flex justify-between">
              <dt className="text-muted-foreground">هزینه ارسال</dt>
              <dd>{formatToman(Number(order.shipping))} تومان</dd>
            </div>
            <div className="flex justify-between border-t border-border pt-1.5 text-sm font-semibold">
              <dt>مبلغ کل</dt>
              <dd>{formatToman(Number(order.total))} تومان</dd>
            </div>
          </dl>
        </section>

        {/* ---- postal tracking (F2.8) ---- */}
        <section className="border-b border-border px-6 py-5" aria-label="کد رهگیری مرسوله">
          <h3 className="text-sm font-semibold">کد رهگیری مرسوله</h3>
          <form
            className="mt-3 flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              const next = tracking.trim();
              if (next !== (order.tracking_code ?? "")) {
                update.mutate({ tracking_code: next || null });
              }
            }}
          >
            <input
              value={tracking}
              onChange={(event) => setTracking(event.target.value)}
              placeholder="کد ۲۴ رقمی پست / کد تیپاکس"
              maxLength={60}
              dir="ltr"
              className="h-9 flex-1 rounded-md border border-input bg-background px-2 font-mono text-xs tracking-wider"
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={update.isPending || tracking.trim() === (order.tracking_code ?? "")}
            >
              <PackageCheck className="size-3.5" />
              ذخیره
            </Button>
          </form>
        </section>

        {/* ---- actions ---- */}
        <div className="mt-auto flex flex-wrap items-center gap-2 px-6 py-5 print:hidden">
          <Button
            variant="outline"
            size="sm"
            onClick={printInvoice}
            className="print:hidden"
          >
            <Printer className="size-4" />
            چاپ فاکتور رسمی
          </Button>
          {!isCancelled && !isDelivered ? (
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
            >
              لغو سفارش
            </Button>
          ) : null}
        </div>
      </SheetContent>

      {/* ---- printable invoice: portalled to <body> so the global `@media
           print` rules can show it as the whole page ---- */}
      {printHost && createPortal(<OrderInvoice order={order} />, printHost)}
    </Sheet>
  );
}
