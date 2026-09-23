import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Copy, Plus, Ticket, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type AdminCoupon } from "@/lib/api";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/_authenticated/admin/coupons")({
  component: AdminCoupons,
});

const FILTERS = [
  { key: "all", label: "همه" },
  { key: "active", label: "فعال" },
  { key: "inactive", label: "غیرفعال" },
  { key: "expired", label: "منقضی" },
] as const;

type FilterKey = (typeof FILTERS)[number]["key"];

const isExpired = (iso: string | null) => Boolean(iso) && new Date(iso!).getTime() < Date.now();

/** Ticket-styled coupon card (spec [FE-07]) with usage progress and the
 * active toggle. */
function CouponCard({ coupon, onEdit }: { coupon: AdminCoupon; onEdit: (c: AdminCoupon) => void }) {
  const queryClient = useQueryClient();
  const [copied, setCopied] = useState(false);

  const toggle = useMutation({
    mutationFn: () => api.adminUpdateCoupon(coupon.id, { active: !coupon.active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-coupons"] });
      toast.success(coupon.active ? "کد تخفیف غیرفعال شد" : "کد تخفیف فعال شد");
    },
    onError: () => toast.error("تغییر وضعیت ناموفق بود"),
  });

  const remove = useMutation({
    mutationFn: () => api.adminDeleteCoupon(coupon.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-coupons"] });
      toast.success("کد تخفیف حذف شد");
    },
    onError: () => toast.error("حذف ناموفق بود"),
  });

  const usagePct = coupon.max_uses
    ? Math.min(100, Math.round((coupon.used_count / coupon.max_uses) * 100))
    : 0;
  const valueLabel = coupon.percent_off
    ? coupon.max_discount_cap
      ? `${toFa(coupon.percent_off)}٪ تخفیف، حداکثر ${formatToman(coupon.max_discount_cap)} تومان`
      : `${toFa(coupon.percent_off)}٪ تخفیف`
    : `${formatToman(coupon.amount_off ?? 0)} تومان تخفیف`;

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(coupon.code);
      setCopied(true);
      toast.success("کد کپی شد");
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("کپی انجام نشد");
    }
  };

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-dashed p-4 transition-colors ${
        coupon.active ? "border-terracotta/50 bg-terracotta/5" : "border-border bg-secondary/40"
      }`}
    >
      {/* ticket notches */}
      <span className="absolute -left-3 top-1/2 size-6 -translate-y-1/2 rounded-full bg-background" />
      <span className="absolute -right-3 top-1/2 size-6 -translate-y-1/2 rounded-full bg-background" />

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => void copyCode()}
            className="flex items-center gap-1.5 font-mono text-base font-semibold tracking-wider text-terracotta"
            title="کپی کد"
          >
            {coupon.code}
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5 opacity-60" />}
          </button>
          <p className="mt-1 text-xs text-muted-foreground">{valueLabel}</p>
        </div>
        <Switch checked={coupon.active} onCheckedChange={() => toggle.mutate()} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div>
          <dt className="text-muted-foreground">حداقل سبد</dt>
          <dd>{formatToman(coupon.min_subtotal)} تومان</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">انقضا</dt>
          <dd>
            {coupon.expires_at ? (
              <span className={isExpired(coupon.expires_at) ? "text-destructive" : ""}>
                {formatFaDate(coupon.expires_at)}
              </span>
            ) : (
              "بدون محدودیت"
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">سقف کل</dt>
          <dd>{coupon.max_uses ? `${toFa(coupon.max_uses)} بار` : "نامحدود"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">سقف هر کاربر</dt>
          <dd>{toFa(coupon.max_uses_per_user)} بار</dd>
        </div>
      </dl>

      {coupon.max_uses ? (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>مصرف‌شده</span>
            <span>
              {toFa(coupon.used_count)} از {toFa(coupon.max_uses)}
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary">
            <div
              className={`h-full rounded-full ${usagePct >= 100 ? "bg-destructive" : "bg-terracotta"}`}
              style={{ width: `${usagePct}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="mt-3 text-[11px] text-muted-foreground">
          {toFa(coupon.used_count)} بار استفاده شده
        </p>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-2">
        <button
          type="button"
          onClick={() => onEdit(coupon)}
          className="text-xs text-terracotta underline-offset-2 hover:underline"
        >
          ویرایش
        </button>
        <button
          type="button"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-destructive disabled:opacity-50"
        >
          <Trash2 className="size-3.5" />
          حذف
        </button>
      </div>
    </div>
  );
}

type FormState = {
  code: string;
  percent_off: string;
  amount_off: string;
  min_subtotal: string;
  max_discount_cap: string; // percent coupons only; "" = uncapped
  max_uses: string;
  max_uses_per_user: string;
  expires_at: string; // date input (yyyy-mm-dd)
};

const EMPTY_FORM: FormState = {
  code: "",
  percent_off: "",
  amount_off: "",
  min_subtotal: "",
  max_discount_cap: "",
  max_uses: "",
  max_uses_per_user: "1",
  expires_at: "",
};

function CouponDialog({
  open,
  editing,
  onClose,
}: {
  open: boolean;
  editing: AdminCoupon | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  // (re)populate the form when the dialog opens for a different coupon
  const key = editing?.id ?? "new";
  if (open && loadedFor !== key) {
    setLoadedFor(key);
    setForm(
      editing
        ? {
            code: editing.code,
            percent_off: editing.percent_off ? String(editing.percent_off) : "",
            amount_off: editing.amount_off ? String(editing.amount_off) : "",
            min_subtotal: editing.min_subtotal ? String(editing.min_subtotal) : "",
            max_discount_cap: editing.max_discount_cap ? String(editing.max_discount_cap) : "",
            max_uses: editing.max_uses ? String(editing.max_uses) : "",
            max_uses_per_user: String(editing.max_uses_per_user ?? 1),
            expires_at: editing.expires_at ? editing.expires_at.slice(0, 10) : "",
          }
        : EMPTY_FORM,
    );
    setError(null);
  }

  const set = (field: keyof FormState) => (event: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [field]: event.target.value }));

  const save = useMutation({
    mutationFn: async () => {
      const percent = form.percent_off ? Number(form.percent_off) : null;
      const amount = form.amount_off ? Number(form.amount_off) : null;
      if (percent === null && amount === null)
        throw new Error("یکی از «درصد» یا «مبلغ» را پر کنید");
      // a coupon is one kind: the backend prefers percent, so both would hide the amount
      if (percent !== null && amount !== null)
        throw new Error("فقط یکی از «درصد» یا «مبلغ» را پر کنید");
      const minSubtotal = form.min_subtotal ? Number(form.min_subtotal) : 0;
      const perUser = form.max_uses_per_user ? Number(form.max_uses_per_user) : 1;
      const maxUses = form.max_uses ? Number(form.max_uses) : null;
      // the ceiling only means something for a percent coupon (AB-BE-03)
      const cap = percent !== null && form.max_discount_cap ? Number(form.max_discount_cap) : null;
      const expires = form.expires_at
        ? new Date(`${form.expires_at}T23:59:59`).toISOString()
        : null;
      if (editing) {
        // F5.16: PATCH treats null as "unchanged", so an emptied field is sent in
        // its clear encoding (expiry "" → none, total cap 0 → unlimited), and only
        // the chosen kind is sent — the backend clears the other one
        await api.adminUpdateCoupon(editing.id, {
          ...(percent !== null
            ? { percent_off: percent, max_discount_cap: cap ?? 0 } // 0 clears it
            : { amount_off: amount }),
          min_subtotal: minSubtotal,
          max_uses: maxUses ?? 0,
          max_uses_per_user: perUser,
          expires_at: expires ?? "",
        });
      } else {
        await api.adminCreateCoupon({
          code: form.code.trim().toUpperCase(),
          percent_off: percent,
          amount_off: amount,
          min_subtotal: minSubtotal,
          max_discount_cap: cap,
          max_uses: maxUses,
          max_uses_per_user: perUser,
          expires_at: expires,
        });
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-coupons"] });
      toast.success(editing ? "کد تخفیف به‌روزرسانی شد" : "کد تخفیف ساخته شد");
      onClose();
    },
    onError: (err: Error) => setError(err.message || "ذخیره ناموفق بود"),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    save.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editing ? `ویرایش ${editing.code}` : "کد تخفیف جدید"}</DialogTitle>
          <DialogDescription>
            درصد یا مبلغ ثابت را پر کنید — فقط یکی از آن‌ها اعمال می‌شود.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={submit}>
          <label className="grid gap-1 text-xs">
            <span className="text-muted-foreground">کد *</span>
            <input
              value={form.code}
              onChange={set("code")}
              disabled={Boolean(editing)}
              required
              dir="ltr"
              placeholder="SANDE15"
              className="h-9 rounded-md border border-input bg-background px-2 font-mono text-sm"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">درصد تخفیف</span>
              <input
                type="number"
                min={1}
                max={100}
                value={form.percent_off}
                onChange={set("percent_off")}
                placeholder="15"
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">مبلغ ثابت (تومان)</span>
              <input
                type="number"
                min={1}
                value={form.amount_off}
                onChange={set("amount_off")}
                placeholder="50000"
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">سقف تخفیف درصدی (تومان)</span>
              <input
                type="number"
                min={1}
                value={form.max_discount_cap}
                onChange={set("max_discount_cap")}
                disabled={!form.percent_off}
                placeholder={form.percent_off ? "بدون سقف" : "فقط برای کد درصدی"}
                className="h-9 rounded-md border border-input bg-background px-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">حداقل سبد (تومان)</span>
              <input
                type="number"
                min={0}
                value={form.min_subtotal}
                onChange={set("min_subtotal")}
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">سقف کل</span>
              <input
                type="number"
                min={1}
                value={form.max_uses}
                onChange={set("max_uses")}
                placeholder="نامحدود"
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">سقف هر کاربر</span>
              <input
                type="number"
                min={1}
                value={form.max_uses_per_user}
                onChange={set("max_uses_per_user")}
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
            <label className="grid gap-1 text-xs">
              <span className="text-muted-foreground">تاریخ انقضا</span>
              <input
                type="date"
                value={form.expires_at}
                onChange={set("expires_at")}
                className="h-9 rounded-md border border-input bg-background px-2"
              />
            </label>
          </div>
          {error ? <p className="text-xs text-destructive">{error}</p> : null}
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={save.isPending}
              className="rounded-full bg-terracotta px-4 py-2 text-xs font-medium text-white hover:bg-terracotta/90 disabled:opacity-50"
            >
              {save.isPending ? "در حال ذخیره…" : "ذخیره"}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AdminCoupons() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["admin-coupons"],
    queryFn: () => api.adminCoupons(),
  });
  const [filter, setFilter] = useState<FilterKey>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminCoupon | null>(null);

  const coupons = data?.coupons ?? [];
  const filtered = useMemo(() => {
    switch (filter) {
      case "active":
        return coupons.filter((c) => c.active && !isExpired(c.expires_at));
      case "inactive":
        return coupons.filter((c) => !c.active);
      case "expired":
        return coupons.filter((c) => isExpired(c.expires_at));
      default:
        return coupons;
    }
  }, [coupons, filter]);

  const generate = useMutation({
    mutationFn: () => api.adminGenerateCouponCode(),
    onSuccess: (res) => {
      setEditing(null);
      setDialogOpen(true);
      // pre-fill the dialog's code through the loadedFor mechanism by faking a
      // create-dialog open; simplest reliable path: copy to clipboard + toast
      void navigator.clipboard?.writeText(res.code).catch(() => {});
      toast.success(`کد پیشنهادی: ${res.code} (کپی شد)`);
      void queryClient.invalidateQueries({ queryKey: ["admin-coupons"] });
    },
    onError: () => toast.error("تولید کد ناموفق بود"),
  });

  const openNew = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (coupon: AdminCoupon) => {
    setEditing(coupon);
    setDialogOpen(true);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <Ticket className="size-4 text-terracotta" />
          <h2 className="font-semibold">کدهای تخفیف</h2>
          <span className="text-xs text-muted-foreground">({toFa(coupons.length)})</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            تولید کد
          </button>
          <button
            type="button"
            onClick={openNew}
            className="flex items-center gap-1.5 rounded-full bg-terracotta px-3 py-1.5 text-xs font-medium text-white hover:bg-terracotta/90"
          >
            <Plus className="size-3.5" />
            کد جدید
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
              filter === f.key
                ? "border-terracotta bg-terracotta/10 text-terracotta"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-44 animate-pulse rounded-2xl bg-secondary/60" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="mt-6 rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          کد تخفیفی در این دسته نیست.
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {filtered.map((coupon) => (
            <CouponCard key={coupon.id} coupon={coupon} onEdit={openEdit} />
          ))}
        </div>
      )}

      <CouponDialog
        open={dialogOpen}
        editing={editing}
        onClose={() => {
          setDialogOpen(false);
          setEditing(null);
        }}
      />
    </div>
  );
}
