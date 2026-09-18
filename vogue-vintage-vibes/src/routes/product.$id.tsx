import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Minus, Plus, Truck, RefreshCcw } from "lucide-react";
import { categoryTitle } from "@/data/products";
import { useCatalog } from "@/lib/catalog";
import { formatToman, toFa } from "@/lib/format";
import { useCart } from "@/lib/cart";
import { Button } from "@/components/ui/button";
import { ProductCard } from "@/components/ProductCard";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export const Route = createFileRoute("/product/$id")({
  head: () => ({
    meta: [
      { title: "جزئیات محصول — ساندِه" },
      {
        name: "description",
        content: "مشخصات، جنس پارچه، رنگ و سایزهای موجود این محصول ساندِه را ببینید.",
      },
      { property: "og:title", content: "جزئیات محصول — ساندِه" },
      { property: "og:description", content: "مشخصات، رنگ و سایزهای موجود محصول." },
      { property: "og:type", content: "product" },
    ],
  }),
  component: ProductPage,
});

function ProductPage() {
  const { id } = Route.useParams();
  const { byId, products: allProducts, isLoading } = useCatalog();
  const product = byId(id);
  const { add } = useCart();
  const [size, setSize] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [active, setActive] = useState(0);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grid gap-10 md:grid-cols-2">
          <div className="aspect-[4/5] animate-pulse rounded-[1.5rem] bg-clay" />
          <div className="space-y-4">
            <div className="h-8 w-2/3 animate-pulse rounded bg-clay" />
            <div className="h-4 w-1/3 animate-pulse rounded bg-clay" />
            <div className="h-24 animate-pulse rounded bg-clay" />
          </div>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
        <h1 className="text-3xl">محصول یافت نشد</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          این محصول حذف شده یا موقتاً موجود نیست.
        </p>
        <Link
          to="/shop"
          search={{}}
          className="mt-8 inline-flex border border-foreground px-8 py-3 text-sm tracking-widest"
        >
          رفتن به فروشگاه
        </Link>
      </div>
    );
  }

  const selectedColor = color ?? product.colors[0]?.name ?? "";
  const related = allProducts
    .filter((p) => p.category === product.category && p.id !== product.id)
    .slice(0, 3);

  const handleAdd = () => {
    if (!size) {
      toast.error("لطفاً سایز را انتخاب کنید");
      return;
    }
    add({ productId: product.id, size, color: selectedColor, quantity });
    toast.success("به سبد خرید اضافه شد");
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <nav className="text-xs text-muted-foreground">
        <Link to="/" className="hover:text-foreground">
          خانه
        </Link>
        <span className="mx-2">/</span>
        <Link
          to="/shop"
          search={{ category: product.category }}
          className="hover:text-foreground"
        >
          {categoryTitle(product.category)}
        </Link>
      </nav>

      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <div>
          <div className="overflow-hidden bg-sand">
            <img
              src={product.images[active] ?? product.images[0]}
              alt={product.name}
              width={900}
              height={1100}
              className="h-auto w-full object-cover"
            />
          </div>
          <div className="mt-3 flex gap-3">
            {product.images.map((image, index) => (
              <button
                key={index}
                type="button"
                onClick={() => setActive(index)}
                className={`w-20 overflow-hidden border ${
                  active === index ? "border-foreground" : "border-transparent"
                }`}
                aria-label={`تصویر ${toFa(index + 1)}`}
              >
                <img src={image} alt="" loading="lazy" className="h-24 w-full object-cover" />
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-[11px] tracking-[0.2em] text-muted-foreground">
            {categoryTitle(product.category)}
          </p>
          <h1 className="mt-2 text-3xl leading-tight">{product.name}</h1>
          <p className="mt-4 flex items-baseline gap-3">
            <span className="text-xl">{formatToman(product.price)} تومان</span>
            {product.oldPrice && (
              <span className="text-sm text-muted-foreground line-through">
                {formatToman(product.oldPrice)}
              </span>
            )}
          </p>
          <p className="mt-5 text-sm leading-7 text-muted-foreground">{product.description}</p>

          <div className="mt-8">
          <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">
              رنگ: {selectedColor}
            </p>
            <div className="flex gap-3">
              {product.colors.map((c) => (
                <button
                  key={c.name}
                  type="button"
                  onClick={() => setColor(c.name)}
                  aria-label={c.name}
                  className={`size-8 rounded-full border border-border ${
                    selectedColor === c.name ? "ring-1 ring-foreground ring-offset-2" : ""
                  }`}
                  style={{ backgroundColor: c.hex }}
                />
              ))}
            </div>
          </div>

          <div className="mt-8">
            <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">سایز</p>
            <div className="flex flex-wrap gap-2">
              {product.sizes.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSize(s)}
                  className={`border px-4 py-2 text-sm transition-colors ${
                    size === s
                      ? "border-foreground bg-foreground text-background"
                      : "border-border hover:border-foreground"
                  }`}
                >
                  {toFa(s)}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-8 flex items-center gap-4">
            <div className="flex items-center border border-border">
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                aria-label="کاهش تعداد"
                className="p-2.5"
              >
                <Minus className="size-4" />
              </button>
              <span className="w-10 text-center text-sm">{toFa(quantity)}</span>
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.min(20, q + 1))}
                aria-label="افزایش تعداد"
                className="p-2.5"
              >
                <Plus className="size-4" />
              </button>
            </div>
            <Button onClick={handleAdd} className="h-11 flex-1 rounded-none text-sm">
              افزودن به سبد خرید
            </Button>
          </div>

          <div className="mt-6 space-y-2 text-xs text-muted-foreground">
            <p className="flex items-center gap-2">
              <Truck className="size-4" /> ارسال رایگان برای خرید بالای ۲٫۰۰۰٫۰۰۰ تومان
            </p>
            <p className="flex items-center gap-2">
              <RefreshCcw className="size-4" /> ۷ روز مهلت تعویض سایز
            </p>
          </div>

          <Accordion type="single" collapsible className="mt-8">
            <AccordionItem value="material">
              <AccordionTrigger className="text-sm">جنس و مراقبت</AccordionTrigger>
              <AccordionContent className="text-sm leading-7 text-muted-foreground">
                {product.material}. شست‌وشو با آب سرد، خشک کردن در سایه و اتوی ملایم توصیه
                می‌شود.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="size">
              <AccordionTrigger className="text-sm">راهنمای سایز</AccordionTrigger>
              <AccordionContent className="text-sm leading-7 text-muted-foreground">
                {product.category === "socks"
                  ? "سایزها بر اساس شماره کفش انتخاب می‌شوند."
                  : "XS معادل ۳۴-۳۶، S معادل ۳۸، M معادل ۴۰، L معادل ۴۲ و XL معادل ۴۴ است. اگر بین دو سایز هستید، سایز بزرگ‌تر را انتخاب کنید."}
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="ship">
              <AccordionTrigger className="text-sm">ارسال و مرجوعی</AccordionTrigger>
              <AccordionContent className="text-sm leading-7 text-muted-foreground">
                ارسال به تهران ۲۴ ساعت کاری و به سایر شهرها ۲ تا ۴ روز کاری. تعویض سایز تا ۷
                روز پس از تحویل امکان‌پذیر است.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </div>

      {related.length > 0 && (
        <section className="mt-20">
          <h2 className="text-2xl">محصولات مرتبط</h2>
          <div className="mt-6 grid grid-cols-2 gap-x-5 gap-y-10 lg:grid-cols-3">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}