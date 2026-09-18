import { createFileRoute } from "@tanstack/react-router";
import fabric from "@/assets/cat-tshirt.jpg";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "درباره ساندِه — پوشاک زنانه مینیمال" },
      {
        name: "description",
        content:
          "داستان برند ساندِه: تولید محدود، پارچه‌های طبیعی و برش‌های کلاسیک برای پوشاک زنانه.",
      },
      { property: "og:title", content: "درباره ساندِه" },
      {
        property: "og:description",
        content: "تولید محدود، پارچه‌های طبیعی و برش‌های کلاسیک.",
      },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
      <p className="text-xs tracking-[0.3em] text-muted-foreground">درباره ما</p>
      <h1 className="mt-5 text-4xl leading-tight">لباس کمتر، انتخاب بهتر</h1>
      <p className="mt-6 text-sm leading-8 text-muted-foreground">
        ساندِه از یک کارگاه کوچک با سه چرخ خیاطی شروع شد. باور ما ساده بود: به‌جای تولید انبوه،
        تعداد کمی تکه بسازیم که خوب دوخته شده‌اند و سال‌ها می‌مانند.
      </p>

      <div className="mt-10 overflow-hidden bg-sand">
        <img
          src={fabric}
          alt="پارچه‌های پنبه‌ای تاشده در رنگ‌های خنثی"
          loading="lazy"
          width={900}
          height={1100}
          className="h-72 w-full object-cover"
        />
      </div>

      <div className="mt-12 grid gap-10 sm:grid-cols-3">
        <div>
          <h2 className="font-display text-xl">پارچه</h2>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            پنبه، کتان و ویسکوز از تأمین‌کنندگان کوچک؛ بدون الیاف نفتی سنگین.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl">دوخت</h2>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            همه‌ی تکه‌ها در کارگاه خودمان دوخته می‌شوند؛ درزهای دوبل و کنترل کیفیت دستی.
          </p>
        </div>
        <div>
          <h2 className="font-display text-xl">تعداد محدود</h2>
          <p className="mt-3 text-sm leading-7 text-muted-foreground">
            هر فصل فقط چند طرح، در تیراژ کم؛ چیزی برای دور ریختن باقی نمی‌ماند.
          </p>
        </div>
      </div>
    </div>
  );
}