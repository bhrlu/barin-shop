import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Clock, Mail, MapPin, Phone } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/contact")({
  head: () => ({
    meta: [
      { title: "تماس با ساندِه" },
      {
        name: "description",
        content: "راه‌های ارتباط با پشتیبانی ساندِه برای سایز، سفارش و مرجوعی.",
      },
      { property: "og:title", content: "تماس با ساندِه" },
      { property: "og:description", content: "پشتیبانی سایز، سفارش و مرجوعی." },
    ],
  }),
  component: ContactPage,
});

const empty = { name: "", contact: "", message: "" };

function ContactPage() {
  const [form, setForm] = useState(empty);
  const [sent, setSent] = useState(false);

  const submit = useMutation({
    mutationFn: () => api.contact(form),
    onSuccess: () => {
      setForm(empty);
      setSent(true);
      toast.success("پیام شما ثبت شد");
    },
    onError: () => toast.error("ارسال پیام ناموفق بود؛ لطفاً دوباره تلاش کنید."),
  });

  const field = (key: keyof typeof empty, label: string, minLength: number) => (
    <div>
      <Label htmlFor={key}>{label}</Label>
      <Input
        id={key}
        value={form[key]}
        required
        minLength={minLength}
        // the API rejects anything shorter, so fail here instead of in a toast
        onChange={(event) => {
          setSent(false);
          setForm({ ...form, [key]: event.target.value });
        }}
        className="mt-2 rounded-none"
      />
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6">
      <h1 className="text-4xl">تماس با ما</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        درباره‌ی سایز، سفارش یا تعویض سؤالی دارید؟ پیام بگذارید.
      </p>

      <div className="mt-12 grid gap-12 md:grid-cols-2">
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            submit.mutate();
          }}
        >
          {field("name", "نام", 2)}
          <div>
            <Label htmlFor="contact">ایمیل یا شماره تماس</Label>
            <Input
              id="contact"
              value={form.contact}
              required
              minLength={5}
              onChange={(event) => {
                setSent(false);
                setForm({ ...form, contact: event.target.value });
              }}
              className="mt-2 rounded-none"
            />
          </div>
          <div>
            <Label htmlFor="message">پیام</Label>
            <Textarea
              id="message"
              value={form.message}
              required
              minLength={5}
              rows={5}
              onChange={(event) => {
                setSent(false);
                setForm({ ...form, message: event.target.value });
              }}
              className="mt-2 rounded-none"
            />
          </div>
          <Button
            type="submit"
            disabled={submit.isPending}
            className="h-11 rounded-none px-8 text-sm tracking-widest"
          >
            {submit.isPending ? "در حال ارسال…" : "ارسال پیام"}
          </Button>
          {sent && (
            <p className="text-xs text-muted-foreground">
              پیام شما ثبت شد. اگر ایمیل یا شماره‌ی درست وارد کرده باشید، پاسخ می‌دهیم.
            </p>
          )}
        </form>

        <div className="bg-sand p-8 text-sm">
          <ul className="space-y-5">
            <li className="flex items-start gap-3">
              <Phone className="mt-0.5 size-4 text-primary" />
              <span>۰۲۱-۴۴۵۵۶۶۷۷</span>
            </li>
            <li className="flex items-start gap-3">
              <Mail className="mt-0.5 size-4 text-primary" />
              <span>hello@sande.example</span>
            </li>
            <li className="flex items-start gap-3">
              <MapPin className="mt-0.5 size-4 text-primary" />
              <span>تهران، خیابان ولیعصر، کوچه‌ی نسترن، پلاک ۱۲</span>
            </li>
            <li className="flex items-start gap-3">
              <Clock className="mt-0.5 size-4 text-primary" />
              <span>شنبه تا چهارشنبه، ۱۰ تا ۱۸</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
