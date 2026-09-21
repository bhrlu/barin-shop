import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type RefundRequest } from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { REFUND_STATUS } from "@/lib/orders";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

/** The admin action dialog: approve / reject / settle with an admin note.
 * Spec [FE-06] asks for a required bank tracking code on settlement — the
 * backend has no column for it yet (B5.3), so settlement today records the
 * note only; the input appears once the column lands. */
function RefundActionDialog({
  request,
  onClose,
}: {
  request: RefundRequest;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const resolve = useMutation({
    mutationFn: (input: { id: string; status: Resolution; admin_note?: string }) =>
      api.resolveRefund(input.id, input.status, input.admin_note),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["admin-refunds"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-payments"] });
      toast.success(
        variables.status === "rejected"
          ? "درخواست رد شد"
          : variables.status === "approved"
            ? "درخواست تأیید شد"
            : "بازپرداخت ثبت شد",
      );
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "ثبت نتیجه انجام نشد"),
  });

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
            disabled={resolve.isPending}
            onClick={() => resolve.mutate({ id: request.id, status: "refunded", admin_note: note })}
          >
            تأیید و ثبت بازگشت وجه
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Admin refund-requests centre (F2.4): reads `GET /admin/refunds` and resolves
 * claims with `PATCH /refunds/{id}` (approved / rejected / refunded — settling
 * also flips the order's payment status to `refunded` server-side).
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
                      سفارش <span className="font-mono tracking-wider">#{toFa(request.order_number)}</span>
                      <span
                        className={`ms-2 inline-block rounded-full px-2 py-0.5 text-[11px] ${
                          request.status === "refunded"
                            ? "bg-sand text-sage-deep"
                            : settled
                              ? "bg-muted text-muted-foreground"
                              : "bg-terracotta/10 text-terracotta"
                        }`}
                      >
                        {REFUND_STATUS[request.status] ?? request.status}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatFaDate(request.created_at)}
                      {request.admin_note ? ` · یادداشت: ${request.admin_note}` : ""}
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

                <div className="mt-3">
                  {settled ? (
                    <span className="text-xs text-muted-foreground">به این درخواست رسیدگی شده است.</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setActive(request)}
                      className="text-xs text-terracotta underline-offset-4 hover:underline"
                    >
                      رسیدگی به درخواست
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {active ? <RefundActionDialog request={active} onClose={() => setActive(null)} /> : null}
    </div>
  );
}
