import { createFileRoute, Link } from "@tanstack/react-router";
import hero from "@/assets/hero.jpg";
import { categories } from "@/data/products";
import { ProductCard } from "@/components/ProductCard";
import { img, useCatalog } from "@/lib/catalog";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ساندِه | فروشگاه آنلاین پوشاک زنانه" },
      {
        name: "description",
        content:
          "تی‌شرت، کراپ‌تاپ، شورت، جوراب و ست زنانه با رنگ‌های خنثی و پارچه‌های طبیعی؛ ارسال به سراسر ایران.",
      },
      { property: "og:title", content: "ساندِه | فروشگاه آنلاین پوشاک زنانه" },
      {
        property: "og:description",
        content: "کالکشن مینیمال و کلاسیک ساندِه برای روزهای معمولی.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { products } = useCatalog();
  const newest = (products.filter((p) => p.isNew).length ? products.filter((p) => p.isNew) : products).slice(0, 3);
  const big = categories[0]!;
  const rest = categories.slice(1);

  return (
    <>
      <section className="surface-courtyard relative overflow-hidden">
        <div className="pointer-events-none absolute -top-24 -left-24 size-72 rounded-full bg-terracotta/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 right-0 size-80 rounded-full bg-gold/20 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 md:grid-cols-2 md:py-24">
          <div className="fade-up">
            <p className="inline-flex items-center gap-2 rounded-full bg-terracotta/12 px-4 py-1.5 text-xs tracking-[0.28em] text-terracotta">
              کالکشن تابستان ۱۴۰۵
            </p>
            <h1 className="mt-6 text-5xl leading-[1.15] md:text-6xl">
              سادگی،
              <br />
              <span className="text-terracotta">دوخته‌شده</span> برای هر روز
            </h1>
            <p className="mt-6 max-w-md text-sm leading-8 text-muted-foreground">
              پارچه‌های طبیعی، رنگ‌های خاکی و برش‌هایی که به مد وابسته نیستند. هر تکه طوری
              طراحی شده که سال‌ها همراهتان بماند.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                to="/shop"
                search={{}}
                className="surface-warm shadow-soft inline-flex items-center rounded-full px-8 py-3.5 text-sm tracking-widest transition-transform hover:-translate-y-0.5"
              >
                دیدن کالکشن
              </Link>
              <Link
                to="/shop"
                search={{ category: "set" }}
                className="inline-flex items-center rounded-full border border-sage-deep/40 px-7 py-3.5 text-sm tracking-widest text-sage-deep transition-colors hover:bg-sage-deep hover:text-background"
              >
                ست‌های جدید
              </Link>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-xs text-muted-foreground">
              <span>ارسال سریع به سراسر ایران</span>
              <span className="text-terracotta/60">•</span>
              <span>۷ روز مهلت تعویض سایز</span>
              <span className="text-terracotta/60">•</span>
              <span>پارچه‌ی ۱۰۰٪ طبیعی</span>
            </div>
          </div>
          <div className="relative">
            <div className="absolute -inset-3 rotate-2 rounded-[2rem] bg-terracotta/15" />
            <div className="shadow-soft relative overflow-hidden rounded-[1.75rem] bg-clay">
              <img
                src={hero}
                alt="مدل با کراپ‌تاپ کرم و شورت کتان شنی"
                width={1408}
                height={1760}
                className="h-auto w-full object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto mt-20 max-w-6xl px-4 sm:px-6">
        <div className="flex items-end justify-between border-b rule-terracotta pb-4">
          <h2 className="text-3xl">
            دسته‌بندی‌ها
            <span className="mt-2 block h-0.5 w-16 bg-terracotta" />
          </h2>
          <Link
            to="/shop"
            search={{}}
            className="text-xs text-terracotta transition-opacity hover:opacity-70"
          >
            همه محصولات
          </Link>
        </div>

        <div className="mt-8 grid auto-rows-[170px] grid-cols-2 gap-4 md:grid-cols-4 md:auto-rows-[190px]">
          <Link
            to="/shop"
            search={{ category: big.id }}
            className="group relative col-span-2 row-span-2 overflow-hidden rounded-[1.5rem] bg-clay"
          >
            <img
              src={img(big.image)}
              alt={big.title}
              loading="lazy"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
            />
            <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-foreground/70 to-transparent p-6">
              <span className="font-display text-3xl text-background">{big.title}</span>
            </span>
          </Link>

          {rest.map((category, i) => (
            <Link
              key={category.id}
              to="/shop"
              search={{ category: category.id }}
              className={`group relative overflow-hidden rounded-[1.5rem] bg-clay ${
                i === 1 ? "md:row-span-2" : ""
              }`}
            >
              <img
                src={img(category.image)}
                alt={category.title}
                loading="lazy"
                className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
              />
              <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-foreground/65 to-transparent p-4">
                <span className="font-display text-xl text-background">{category.title}</span>
              </span>
            </Link>
          ))}

          <div className="surface-warm flex flex-col justify-between rounded-[1.5rem] p-6">
            <p className="text-xs tracking-[0.25em] opacity-80">تخفیف فصل</p>
            <p className="font-display text-4xl leading-none">۳۰٪</p>
            <Link to="/shop" search={{ category: "shorts" }} className="text-sm underline">
              شورت‌های کتان
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto mt-24 max-w-6xl px-4 sm:px-6">
        <div className="flex items-end justify-between border-b rule-terracotta pb-4">
          <h2 className="text-3xl">
            جدیدترین‌ها
            <span className="mt-2 block h-0.5 w-16 bg-sage" />
          </h2>
          <Link
            to="/shop"
            search={{}}
            className="text-xs text-terracotta transition-opacity hover:opacity-70"
          >
            دیدن همه
          </Link>
        </div>
        <div className="mt-8 grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
          {newest.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>

      <section className="mt-24 bg-sage-deep text-background">
        <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
          <p className="text-xs tracking-[0.3em] text-background/70">تخفیف پایان فصل</p>
          <h2 className="mt-4 text-4xl">
            تا <span className="text-gold">۳۰٪</span> روی ست‌ها و شورت‌های کتان
          </h2>
          <Link
            to="/shop"
            search={{ category: "set" }}
            className="mt-8 inline-flex rounded-full bg-background px-8 py-3.5 text-sm tracking-widest text-foreground transition-transform hover:-translate-y-0.5"
          >
            خرید ست‌ها
          </Link>
        </div>
      </section>

      <section className="mx-auto mt-24 max-w-3xl rounded-[2rem] bg-sand px-6 py-14 text-center">
        <h2 className="text-3xl">داستان ساندِه</h2>
        <span className="mx-auto mt-4 block h-0.5 w-16 bg-terracotta" />
        <p className="mt-5 text-sm leading-8 text-muted-foreground">
          ما در یک کارگاه کوچک شروع کردیم؛ با این باور که لباس خوب لازم نیست پیچیده باشد. هر
          فصل تعداد محدودی تکه تولید می‌کنیم، از پارچه‌هایی که به پوست و طبیعت مهربان‌اند.
        </p>
        <Link to="/about" className="mt-6 inline-block text-sm text-terracotta underline">
          بیشتر بخوانید
        </Link>
      </section>
    </>
  );
}
