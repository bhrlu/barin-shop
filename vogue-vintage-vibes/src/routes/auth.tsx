import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Search = { redirect?: string };

export const Route = createFileRoute("/auth")({
  validateSearch: (search: Record<string, unknown>): Search => {
    const value = search["redirect"];
    return typeof value === "string" && value.startsWith("/") ? { redirect: value } : {};
  },
  head: () => ({
    meta: [
      { title: "ورود و ثبت‌نام — ساندِه" },
      {
        name: "description",
        content: "ورود به حساب کاربری ساندِه برای پیگیری سفارش‌ها، آدرس‌ها و علاقه‌مندی‌ها.",
      },
      { property: "og:title", content: "ورود و ثبت‌نام — ساندِه" },
      { property: "og:description", content: "ورود به حساب کاربری فروشگاه ساندِه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AuthPage,
});

function AuthPage() {
  const { redirect } = Route.useSearch();
  const navigate = useNavigate();
  const { user, loading, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) navigate({ to: redirect ?? "/account", replace: true });
  }, [loading, user, navigate, redirect]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (mode === "signup") {
        await signUp({ email, password, full_name: fullName });
      } else {
        await signIn(email, password);
      }
      toast.success("خوش آمدید");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "خطایی رخ داد");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <h1 className="text-center text-3xl">{mode === "signin" ? "ورود به حساب" : "ساخت حساب"}</h1>
      <p className="mt-2 text-center text-sm text-muted-foreground">
        سفارش‌ها، آدرس‌ها و علاقه‌مندی‌های شما در یک جا
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        {mode === "signup" && (
          <div>
            <Label htmlFor="fullName">نام و نام خانوادگی</Label>
            <Input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="mt-2 bg-background"
              required
            />
          </div>
        )}
        <div>
          <Label htmlFor="email">ایمیل</Label>
          <Input
            id="email"
            type="email"
            dir="ltr"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 bg-background"
            required
          />
        </div>
        <div>
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor="password">رمز عبور</Label>
            {mode === "signin" && (
              <Link to="/forgot-password" className="text-xs text-terracotta hover:underline">
                رمز عبور را فراموش کرده‌اید؟
              </Link>
            )}
          </div>
          <Input
            id="password"
            type="password"
            dir="ltr"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            className="mt-2 bg-background"
            required
          />
        </div>
        <Button type="submit" disabled={busy} className="h-11 w-full">
          {mode === "signin" ? "ورود" : "ثبت‌نام"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "signin" ? "حساب ندارید؟" : "قبلاً ثبت‌نام کرده‌اید؟"}{" "}
        <button
          type="button"
          className="text-terracotta underline"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
        >
          {mode === "signin" ? "ثبت‌نام کنید" : "وارد شوید"}
        </button>
      </p>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        <Link to="/" className="hover:text-foreground">
          بازگشت به فروشگاه
        </Link>
      </p>
    </div>
  );
}
