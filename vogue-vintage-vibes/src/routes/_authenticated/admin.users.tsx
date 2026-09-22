import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, toPage, type AdminUser, type StaffRole } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatToman, toFa } from "@/lib/format";
import { Pager } from "@/components/Pager";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

/** Staff roles (B5.4) each have their own Persian label; an unknown role shows
 * its raw name rather than being mislabelled as a customer. */
const ROLE_LABELS: Record<string, string> = {
  super_admin: "مدیر ارشد",
  admin: "مدیر",
  order_manager: "مدیر سفارش‌ها",
  support: "پشتیبانی",
  customer: "مشتری",
};

/** What each editable role unlocks — mirrors ROLE_CAPABILITIES in
 * backend/app/services/roles.py (the backend stays the authority). */
const EDITABLE_ROLES: { role: StaffRole; hint: string }[] = [
  {
    role: "super_admin",
    hint: "دسترسی کامل: کاربران و نقش‌ها، گزارش فعالیت‌ها و همهٔ بخش‌ها",
  },
  {
    role: "order_manager",
    hint: "سفارش‌ها، بازپرداخت‌ها، محصولات و انبار، تخفیف‌ها و پیام‌ها",
  },
  { role: "support", hint: "پیام‌ها، نظرات و داشبورد — بدون جابه‌جایی پول یا موجودی" },
];

const EDITABLE = new Set<string>(EDITABLE_ROLES.map((item) => item.role));

export const Route = createFileRoute("/_authenticated/admin/users")({
  component: AdminUsers,
});

const PAGE_SIZE = 20;

function AdminUsers() {
  const { user: me } = useAuth();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () => toPage(api.adminUsers(page, PAGE_SIZE)),
  });
  const users = data?.items ?? [];

  if (isLoading)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        در حال بارگذاری…
      </div>
    );

  if (!users.length)
    return (
      <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
        کاربری ثبت نشده است.
      </div>
    );

  return (
    <>
      <ul className="divide-y divide-border rounded-3xl border border-border">
        {users.map((user) => {
          const isSelf = user.id === me?.id;
          return (
            <li
              key={user.id}
              className="flex flex-wrap items-center justify-between gap-3 p-5 text-sm"
            >
              <div>
                <p>{user.full_name ?? "بدون نام"}</p>
                <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
                  {user.phone ?? "—"} ·{" "}
                  {toFa(new Date(user.created_at).toLocaleDateString("fa-IR"))}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs">
                {user.roles.map((role) => (
                  <span key={role} className="rounded-full bg-sand px-3 py-1">
                    {ROLE_LABELS[role] ?? role}
                  </span>
                ))}
                <span>{toFa(user.order_count)} سفارش</span>
                <span>{formatToman(user.spent)} تومان</span>
                <button
                  type="button"
                  onClick={() => setEditing(user)}
                  disabled={isSelf}
                  title={
                    isSelf ? "نقش‌های حساب خودتان را از اینجا نمی‌توانید تغییر دهید" : undefined
                  }
                  className="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ShieldCheck className="size-3.5" aria-hidden />
                  نقش‌ها
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      <Pager
        className="mt-6"
        page={data?.page ?? page}
        pages={data?.pages ?? 1}
        total={data?.total}
        onChange={setPage}
      />
      {editing ? (
        <RolesDialog key={editing.id} user={editing} onClose={() => setEditing(null)} />
      ) : null}
    </>
  );
}

/**
 * Two-step role change (spec [FE-08]): pick the new role set, then review the
 * added/removed roles and type the account's email to confirm. Sends the full
 * replacement set to `PUT /admin/users/{id}/roles`; legacy roles (`admin`,
 * `customer`) are outside that endpoint and shown read-only.
 */
function RolesDialog({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const queryClient = useQueryClient();
  const current = user.roles.filter((role): role is StaffRole => EDITABLE.has(role));
  const fixed = user.roles.filter((role) => !EDITABLE.has(role));
  const [selected, setSelected] = useState<Set<StaffRole>>(new Set(current));
  const [step, setStep] = useState<"edit" | "confirm">("edit");
  const [typed, setTyped] = useState("");

  const added = EDITABLE_ROLES.map((item) => item.role).filter(
    (role) => selected.has(role) && !current.includes(role),
  );
  const removed = current.filter((role) => !selected.has(role));
  const changed = added.length > 0 || removed.length > 0;
  // the email is the login identity; fall back to the id for a row without one
  const confirmToken = user.email ?? user.id;
  const confirmed = typed.trim().toLowerCase() === confirmToken.toLowerCase();

  const save = useMutation({
    mutationFn: () =>
      api.adminSetUserRoles(
        user.id,
        EDITABLE_ROLES.map((item) => item.role).filter((role) => selected.has(role)),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
      toast.success("نقش‌های کاربر به‌روز شد");
      onClose();
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError && error.status === 403
          ? "نقش شما اجازهٔ تغییر نقش کاربران را ندارد"
          : error instanceof ApiError
            ? error.message
            : "تغییر نقش انجام نشد",
      ),
  });

  const toggle = (role: StaffRole, on: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(role);
      else next.delete(role);
      return next;
    });
  };

  return (
    <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-serif">
            {step === "edit" ? "مدیریت نقش‌ها" : "تأیید تغییر دسترسی"}
          </DialogTitle>
          <DialogDescription>
            {user.full_name ?? "بدون نام"}
            {user.email ? (
              <span className="mt-1 block font-mono text-xs" dir="ltr">
                {user.email}
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        {step === "edit" ? (
          <div className="space-y-3">
            {EDITABLE_ROLES.map(({ role, hint }) => (
              <label
                key={role}
                className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 p-3 transition-colors hover:bg-muted/40"
              >
                <Checkbox
                  checked={selected.has(role)}
                  onCheckedChange={(value) => toggle(role, value === true)}
                  className="mt-0.5"
                />
                <span>
                  <span className="block text-sm">{ROLE_LABELS[role]}</span>
                  <span className="block text-xs text-muted-foreground">{hint}</span>
                </span>
              </label>
            ))}
            {fixed.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                نقش‌های ثابت (از این بخش قابل تغییر نیستند):{" "}
                {fixed.map((role) => ROLE_LABELS[role] ?? role).join("، ")}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              بدون هیچ نقش پرسنلی، کاربر فقط به حساب مشتری دسترسی دارد.
            </p>
          </div>
        ) : (
          <div className="space-y-4 text-sm">
            <ul className="space-y-1">
              {added.map((role) => (
                <li key={role} className="text-sage-deep">
                  + افزودن «{ROLE_LABELS[role]}»
                </li>
              ))}
              {removed.map((role) => (
                <li key={role} className="text-destructive">
                  − حذف «{ROLE_LABELS[role]}»
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted-foreground">
              تغییر از درخواست بعدی کاربر اعمال و در گزارش فعالیت‌ها ثبت می‌شود. برای تأیید،{" "}
              {user.email ? "ایمیل کاربر" : "شناسهٔ کاربر"} را بنویسید:
            </p>
            <p className="font-mono text-xs" dir="ltr">
              {confirmToken}
            </p>
            <input
              dir="ltr"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              aria-label="تأیید با ایمیل کاربر"
              autoComplete="off"
              className="h-10 w-full rounded-xl border border-border bg-card px-3 font-mono text-sm outline-none focus:border-terracotta"
            />
          </div>
        )}

        <DialogFooter className="gap-2">
          {step === "edit" ? (
            <>
              <Button variant="ghost" onClick={onClose}>
                انصراف
              </Button>
              <Button
                disabled={!changed}
                onClick={() => setStep("confirm")}
                className="bg-terracotta text-white hover:bg-terracotta/90"
              >
                ادامه
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                disabled={save.isPending}
                onClick={() => {
                  setTyped("");
                  setStep("edit");
                }}
              >
                بازگشت
              </Button>
              <Button
                disabled={!confirmed || save.isPending}
                onClick={() => save.mutate()}
                className="bg-terracotta text-white hover:bg-terracotta/90"
              >
                {save.isPending ? "در حال ذخیره…" : "تأیید و ذخیره"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
