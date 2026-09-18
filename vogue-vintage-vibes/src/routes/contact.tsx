import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Clock, Mail, MapPin, Phone } from "lucide-react";
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

function ContactPage() {
  const [sent, setSent] = useState(false);

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
            setSent(true);
            toast.success("پیام شما ثبت شد (نمایشی)");
          }}
        >
          <div>
            <Label htmlFor="name">نام</Label>
            <Input id="name" required className="mt-2 rounded-none" />
          </div>
          <div>
            <Label htmlFor="email">ایمیل یا شماره تماس</Label>
            <Input id="email" required className="mt-2 rounded-none" />
          </div>
          <div>
            <Label htmlFor="message">پیام</Label>
            <Textarea id="message" required rows={5} className="mt-2 rounded-none" />
          </div>
          <Button type="submit" className="h-11 rounded-none px-8 text-sm tracking-widest">
            ارسال پیام
          </Button>
          {sent && (
            <p className="text-xs text-muted-foreground">
              این فرم نمایشی است و پیام جایی ذخیره نمی‌شود.
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