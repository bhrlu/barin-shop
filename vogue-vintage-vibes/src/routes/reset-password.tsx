import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { CircleCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Search = { token?: string | undefined };

/** Same bounds as the backend's `ResetPasswordRequest`. */
const MIN_PASSWORD = 6;
const MAX_PASSWORD = 128;

export const Route = createFileRoute("/reset-password")({
  // rejected keys come back as explicit `undefined` (see DESIGN_SYSTEM: validateSearch)
  validateSearch: (search: Record<string, unknown>): Search => {
    const value = search["token"];
    return {
      token: typeof value === "string" && /^[A-Za-z0-9_-]{20,200}$/.test(value) ? value : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "تعیین رمز عبور تازه — ساندِه" },
      { name: "description", content: "تعیین رمز عبور تازه برای حساب ساندِه." },
      { property: "og:title", content: "تعیین رمز عبور تازه — ساندِه" },
      { property: "og:description", content: "بازیابی رمز عبور حساب کاربری ساندِه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ResetPasswordPage,
});

/** F2.3 — set a new password from the emailed one-time link. */
function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const reset = useMutation({
    mutationFn: (value: { token: string; password: string }) =>
      api.resetPassword(value.token, value.password),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!token) return;
    if (password.length < MIN_PASSWORD) {
      setLocalError(`رمز عبور باید دست‌کم ${MIN_PASSWORD.toLocaleString("fa-IR")} نویسه باشد.`);
      return;
    }
    if (password !== confirm) {
      setLocalError("تکرار رمز عبور با خود آن یکی نیست.");
      return;
    }
    setLocalError(null);
    reset.mutate({ token, password });
  };

  if (!token) {
    return (
      <Shell>
        <p className="text-sm leading-7 text-muted-foreground" role="alert">
          این لینک بازیابی کامل یا معتبر نیست. لطفاً از همان لینکی که در ایمیل آمده استفاده کنید یا
          لینک تازه‌ای درخواست دهید.
        </p>
        <Link to="/forgot-password" className="mt-4 inline-block text-sm text-terracotta underline">
          درخواست لینک تازه
        </Link>
      </Shell>
    );
  }

  if (reset.isSuccess) {
    return (
      <Shell>
        <CircleCheck className="mx-auto size-8 text-sage-deep" aria-hidden />
        <p className="mt-3 text-sm leading-7" role="status">
          رمز عبور شما تغییر کرد. اکنون می‌توانید با رمز تازه وارد شوید.
        </p>
        <Link to="/auth" className="mt-4 inline-block text-sm text-terracotta underline">
          ورود به حساب
        </Link>
      </Shell>
    );
  }

  const serverError =
    reset.error instanceof ApiError && reset.error.status < 500
      ? reset.error.message
      : reset.isError
        ? "تغییر رمز ممکن نشد. کمی بعد دوباره تلاش کنید."
        : null;
  const linkExpired = reset.error instanceof ApiError && reset.error.status === 400;

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <h1 className="text-center text-3xl">تعیین رمز عبور تازه</h1>
      <p className="mt-2 text-center text-sm text-muted-foreground">
        رمز تازه را دو بار وارد کنید.
      </p>
      <form onSubmit={submit} className="mt-8 space-y-4">
        <div>
          <Label htmlFor="password">رمز عبور تازه</Label>
          <Input
            id="password"
            type="password"
            dir="ltr"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={MIN_PASSWORD}
            maxLength={MAX_PASSWORD}
            className="mt-2 bg-background"
            required
          />
        </div>
        <div>
          <Label htmlFor="confirm">تکرار رمز عبور</Label>
          <Input
            id="confirm"
            type="password"
            dir="ltr"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            maxLength={MAX_PASSWORD}
            className="mt-2 bg-background"
            required
          />
        </div>
        {localError || serverError ? (
          <p className="text-sm text-destructive" role="alert">
            {localError ?? serverError}
          </p>
        ) : null}
        {linkExpired ? (
          <Link to="/forgot-password" className="inline-block text-sm text-terracotta underline">
            درخواست لینک تازه
          </Link>
        ) : null}
        <Button type="submit" disabled={reset.isPending} className="h-11 w-full">
          {reset.isPending ? "در حال ذخیره…" : "ذخیرهٔ رمز تازه"}
        </Button>
      </form>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <h1 className="text-center text-3xl">تعیین رمز عبور تازه</h1>
      <div className="mt-8 rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm">
        {children}
      </div>
    </div>
  );
}
