import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({
    meta: [
      { title: "فراموشی رمز عبور — ساندِه" },
      { name: "description", content: "درخواست لینک بازیابی رمز عبور حساب ساندِه." },
      { property: "og:title", content: "فراموشی رمز عبور — ساندِه" },
      { property: "og:description", content: "بازیابی رمز عبور حساب کاربری ساندِه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ForgotPasswordPage,
});

/** F2.3 — ask for a reset link. The API answers the same way for every address
 * (it never says whether an account exists), so the page does too. */
function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const request = useMutation({ mutationFn: (value: string) => api.forgotPassword(value) });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    request.mutate(email.trim());
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <h1 className="text-center text-3xl">فراموشی رمز عبور</h1>

      {request.isSuccess ? (
        <div className="mt-8 rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm">
          <MailCheck className="mx-auto size-8 text-sage-deep" aria-hidden />
          <p className="mt-3 text-sm leading-7" role="status">
            {request.data.message}
          </p>
          <p className="mt-2 text-xs leading-6 text-muted-foreground">
            لینک فقط برای مدت کوتاهی و یک بار کار می‌کند. اگر ایمیلی نرسید، پوشهٔ هرزنامه را هم
            ببینید یا چند دقیقهٔ دیگر دوباره درخواست دهید.
          </p>
          <Link to="/auth" className="mt-4 inline-block text-sm text-terracotta underline">
            بازگشت به صفحهٔ ورود
          </Link>
        </div>
      ) : (
        <>
          <p className="mt-2 text-center text-sm text-muted-foreground">
            ایمیل حساب خود را وارد کنید تا لینک تعیین رمز تازه برایتان ارسال شود.
          </p>
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <Label htmlFor="email">ایمیل</Label>
              <Input
                id="email"
                type="email"
                dir="ltr"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 bg-background"
                required
              />
            </div>
            {request.isError ? (
              <p className="text-sm text-destructive" role="alert">
                {request.error instanceof ApiError && request.error.status < 500
                  ? request.error.message
                  : "ارسال درخواست ممکن نشد. کمی بعد دوباره تلاش کنید."}
              </p>
            ) : null}
            <Button type="submit" disabled={request.isPending} className="h-11 w-full">
              {request.isPending ? "در حال ارسال…" : "ارسال لینک بازیابی"}
            </Button>
          </form>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            رمز را به یاد آوردید؟{" "}
            <Link to="/auth" className="text-terracotta underline">
              وارد شوید
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
