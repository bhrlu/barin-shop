import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type RefundRequest } from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/_authenticated/admin/refunds")({
  head: () => ({
    meta: [
      { title: "بازپرداخت‌ها — ساندِه" },
      { name: "description", content: "بررسی و تسویه درخواست‌های بازپرداخت مشتریان ساندِه." },
      { property: "og:title", content: "بازپرداخت‌ها — ساندِه" },
      { property: "og:description", content: "بررسی و تسویه درخواست‌های بازپرداخت." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminRefunds,
});

const TABS = [
  { value: "pending", label: "در انتظار بررسی" },
  { value: "settled", label: "تسویه‌شده" },
  { value: "all", label: "همه" },
] as const;

type Tab = (typeof TABS)[number]["value"];

type Resolution = "approved" | "rejected" | "refunded";

const isSettled = (status: string) => status === "rejected" || status === "refunded";

/** The admin action dialog ([FE-06]): approve / reject / settle. The Paya/Satna
 * bank tracking code is **required for settlement** — the backend 422s without
 * it, and the disabled button mirrors that rule. */
function RefundActionDialog({ request, onClose }: { request: RefundRequest; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [bankCode, setBankCode] = useState(request.bank_tracking_code ?? "");

  const resolve = useMutation({
    mutationFn: (input: {
      id: string;
      status: Resolution;
      admin_note?: string;
      bank_tracking_code?: string;
    }) => api.resolveRefund(input.id, input.status, input.admin_note, input.bank_tracking_code),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["admin-refunds"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-payments"] });
      toast.success(
        variables.status === "rejected"
          ? "درخواست رد شد"
          : variables.status === "approved"
            ? "درخواست تأیید شد"
            : "بازپرداخت با کد رهگیری بانکی ثبت شد",
      );
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "ثبت نتیجه انجام نشد"),
  });

  const bankRequired = bankCode.trim().length === 0;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>رسیدگی به درخواست بازپرداخت</DialogTitle>
          <DialogDescription>
            سفارش #{toFa(request.order_number)} · {formatToman(request.amount)} تومان
          </DialogDescription>
        </DialogHeader>

        {request.reason ? (
          <blockquote className="rounded-lg border-s-4 border-terracotta bg-muted/40 p-3 text-sm leading-6">
            {request.reason}
          </blockquote>
        ) : (
          <p className="text-xs text-muted-foreground">دلیلی ثبت نشده است.</p>
        )}

        <div className="space-y-1.5">
          <label htmlFor="refund-bank-code" className="text-xs text-muted-foreground">
            کد رهگیری بانکی (پایا/ساتنا)
            <span className="text-terracotta"> *</span>
          </label>
          <Input
            id="refund-bank-code"
            value={bankCode}
            onChange={(e) => setBankCode(e.target.value)}
            maxLength={60}
            dir="ltr"
            required
            placeholder="کد پیگیری بانک"
            className="font-mono tracking-wider"
          />
          <p className="text-[11px] text-muted-foreground">
            برای ثبت بازگشت وجه الزامی است؛ بدون آن پول از دید بانک قابل ردیابی نیست.
          </p>
        </div>

        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder="یادداشت مدیر (دلیل تأیید یا رد)"
        />

        <DialogFooter className="flex-row gap-2">
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            disabled={resolve.isPending}
            onClick={() => resolve.mutate({ id: request.id, status: "rejected", admin_note: note })}
          >
            رد درخواست
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="flex-1"
            disabled={resolve.isPending}
            onClick={() => resolve.mutate({ id: request.id, status: "approved", admin_note: note })}
          >
            تأیید درخواست
          </Button>
          <Button
            type="button"
            className="flex-1"
            disabled={resolve.isPending || bankRequired}
            title={bankRequired ? "کد رهگیری بانکی الزامی است" : undefined}
            onClick={() =>
              resolve.mutate({
                id: request.id,
                status: "refunded",
                admin_note: note,
                bank_tracking_code: bankCode.trim(),
              })
            }
          >
            تأیید و ثبت بازگشت وجه
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Admin refund-requests centre (F2.4 + B5.3): reads `GET /admin/refunds` and
 * resolves claims with `PATCH /refunds/{id}` (approved / rejected / refunded).
 * Settlement requires the bank tracking code and records the resolver and
 * timestamp server-side ([BE-03]).
 */
function AdminRefunds() {
  const [tab, setTab] = useState<Tab>("pending");
  const [active, setActive] = useState<RefundRequest | null>(null);

  const refunds = useQuery({
    queryKey: ["admin-refunds"],
    queryFn: () => api.adminRefunds(),
  });

  const list = (refunds.data ?? []).filter((r) =>
    tab === "all" ? true : tab === "pending" ? !isSettled(r.status) : isSettled(r.status),
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-lg">
          درخواست‌های بازپرداخت {list.length ? `(${toFa(list.length)})` : ""}
        </h2>
        <div className="flex gap-2">
          {TABS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setTab(option.value)}
              aria-pressed={tab === option.value}
              className={
                tab === option.value
                  ? "rounded-full border border-terracotta bg-terracotta/10 px-4 py-2 text-xs text-terracotta"
                  : "rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {refunds.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-3xl bg-clay" />
          ))}
        </div>
      ) : refunds.isError ? (
        <p className="text-sm text-terracotta">خواندن درخواست‌ها انجام نشد.</p>
      ) : list.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          درخواستی با این وضعیت وجود ندارد.
        </div>
      ) : (
        <ul className="space-y-4">
          {list.map((request) => {
            const settled = isSettled(request.status);
            return (
              <li key={request.id} className="rounded-3xl border border-border p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm">
                      سفارش{" "}
                      <span className="font-mono tracking-wider">
                        #{toFa(request.order_number)}
                      </span>
                      <StatusBadge
                        status={request.status}
                        className="ms-2 !px-2 !py-0.5 !text-[11px]"
                      />
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {request.user_name || "مشتری"}
                      {request.user_email ? ` · ${request.user_email}` : ""} ·{" "}
                      {formatFaDate(request.created_at)}
                    </p>
                  </div>
                  <p className="font-mono text-sm font-bold text-rose-600">
                    {formatToman(request.amount)} تومان
                  </p>
                </div>

                {request.reason ? (
                  <blockquote className="mt-3 rounded-lg border-s-4 border-terracotta bg-muted/40 p-3 text-sm leading-6">
                    {request.reason}
                  </blockquote>
                ) : null}

                {settled ? (
                  <p className="mt-3 text-xs text-muted-foreground">
                    به این درخواست رسیدگی شده است
                    {request.status === "refunded" && request.bank_tracking_code ? (
                      <>
                        {" "}
                        · کد رهگیری بانکی:{" "}
                        <span className="font-mono tracking-wider text-foreground">
                          {toFa(request.bank_tracking_code)}
                        </span>
                      </>
                    ) : null}
                    {request.resolved_at ? ` · ${formatFaDate(request.resolved_at)}` : ""}
                  </p>
                ) : (
                  <div className="mt-3">
                    <button
                      type="button"
                      onClick={() => setActive(request)}
                      className="text-xs text-terracotta underline-offset-4 hover:underline"
                    >
                      رسیدگی به درخواست
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {active ? <RefundActionDialog request={active} onClose={() => setActive(null)} /> : null}
    </div>
  );
}
