import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";
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
      { name: "description", content: "ورود به حساب کاربری ساندِه برای پیگیری سفارش‌ها، آدرس‌ها و علاقه‌مندی‌ها." },
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
  const { user, loading } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (!loading && user) navigate({ to: redirect ?? "/account", replace: true });
  }, [loading, user, navigate, redirect]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: window.location.origin,
            data: { full_name: fullName },
          },
        });
        if (error) throw error;
        if (!data.session) {
          setSent(true);
          toast.success("ایمیل تأیید برای شما ارسال شد");
          return;
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      toast.success("خوش آمدید");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "خطایی رخ داد");
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    const result = await lovable.auth.signInWithOAuth("google", {
      redirect_uri: window.location.origin,
    });
    if (result.error) {
      toast.error("ورود با گوگل انجام نشد");
      return;
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16 sm:px-6">
      <h1 className="text-center text-3xl">{mode === "signin" ? "ورود به حساب" : "ساخت حساب"}</h1>
      <p className="mt-2 text-center text-sm text-muted-foreground">
        سفارش‌ها، آدرس‌ها و علاقه‌مندی‌های شما در یک جا
      </p>

      {sent ? (
        <div className="mt-8 rounded-2xl bg-sand p-6 text-center text-sm leading-7">
          لینک تأیید به {email} ارسال شد. پس از تأیید ایمیل می‌توانید وارد شوید.
        </div>
      ) : (
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
            <Label htmlFor="password">رمز عبور</Label>
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
      )}

      <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" /> یا <span className="h-px flex-1 bg-border" />
      </div>

      <Button variant="outline" className="h-11 w-full" onClick={google}>
        ورود با گوگل
      </Button>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "signin" ? "حساب ندارید؟" : "قبلاً ثبت‌نام کرده‌اید؟"}{" "}
        <button
          type="button"
          className="text-terracotta underline"
          onClick={() => {
            setMode(mode === "signin" ? "signup" : "signin");
            setSent(false);
          }}
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