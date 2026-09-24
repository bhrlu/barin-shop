import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Minus, Plus, RefreshCcw, Truck } from "lucide-react";
import type { ProductBadge, ProductVariant } from "@/lib/api";
import { api } from "@/lib/api";
import { categoryTitle } from "@/data/products";
import {
  productQuery,
  recommendationsQuery,
  relatedQuery,
  variantsQuery,
  type AdminProduct,
} from "@/lib/catalog";
import { defaultColor, variantStockFor } from "@/lib/variants";
import { formatFaDate, formatToman, toFa } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { recordGuestView } from "@/lib/recently-viewed";
import { useCart } from "@/lib/cart";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ProductRail } from "@/components/product/ProductRail";
import { ReviewsSection } from "@/components/product/ReviewsSection";
import { VariantPicker } from "@/components/product/VariantPicker";
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

const BADGE_LABELS: Record<ProductBadge, string> = {
  sale: "حراج",
  new: "جدید",
  exclusive: "ویژه",
  coming_soon: "به‌زودی",
  preorder: "پیش‌خرید",
};

function ProductPage() {
  const { id } = Route.useParams();
  const product = useQuery(productQuery(id));
  const variants = useQuery({ ...variantsQuery(id), enabled: product.isSuccess });
  const related = useQuery({ ...relatedQuery(id, 4), enabled: product.isSuccess });
  const recommended = useQuery({ ...recommendationsQuery(id, 8), enabled: product.isSuccess });

  if (product.isLoading) {
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

  if (product.isError || !product.data || !product.data.active) {
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

  const relatedIds = new Set((related.data ?? []).map((item) => item.id));
  const alsoSuggested = (recommended.data ?? []).filter((item) => !relatedIds.has(item.id));

  return (
    <>
      {/* key resets the gallery/selection state when the route param changes */}
      <ProductDetail key={product.data.id} product={product.data} variants={variants.data ?? []} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <ProductRail title="محصولات مرتبط" eyebrow="هم‌خانواده" products={related.data ?? []} />
        <ProductRail title="پیشنهاد برای شما" eyebrow="شاید بپسندید" products={alsoSuggested} />
        <ReviewsSection
          productId={product.data.id}
          fallbackAverage={product.data.avgRating}
          fallbackCount={product.data.reviewCount}
        />
      </div>
    </>
  );
}

function ProductDetail({
  product,
  variants,
}: {
  product: AdminProduct;
  variants: ProductVariant[];
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { add } = useCart();
  const [size, setSize] = useState<string | null>(null);
  const [color, setColor] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [active, setActive] = useState(0);

  const selectedColor = color ?? defaultColor(product, variants);
  const maxQuantity = 20;

  // `POST /products/{id}/view` — signed-in visitors go straight to the server;
  // guests record the view in localStorage (F3.4b/D7(c), merged at sign-in).
  // Invalidate the rail afterwards so «بازدیدهای اخیر» is correct even when the
  // visitor navigates away before the request settles.
  useEffect(() => {
    if (user) {
      void api
        .recordProductView(product.id)
        .then(() => queryClient.invalidateQueries({ queryKey: ["recently-viewed"] }))
        .catch(() => {});
    } else {
      recordGuestView(product.id);
      queryClient.invalidateQueries({ queryKey: ["recently-viewed"] });
    }
  }, [user, product.id, queryClient]);

  const combo = size ? variantStockFor(product, variants, size, selectedColor) : null;
  const availability = product.availability ?? "in_stock";
  const comingSoon = availability === "coming_soon";
  const preorder = availability === "preorder";
  const availableAt = formatFaDate(product.availableAt);
  const badge = product.badge ?? (product.isNew ? "new" : null);
  // F5.18: a size×colour with its own price (variant `price_override`) shows that price;
  // the server charges it too
  const selectedVariant = size
    ? variants.find((variant) => variant.size === size && variant.color === selectedColor)
    : undefined;
  const price = selectedVariant?.price_override ?? product.price;
  const discount =
    product.oldPrice && product.oldPrice > price
      ? Math.round(((product.oldPrice - price) / product.oldPrice) * 100)
      : null;

  const purchasable = !comingSoon && !preorder && Boolean(combo) && !combo?.soldOut;
  const stockForMax = combo && combo.available ? combo.stock : product.stock;
  const quantityCeiling = Math.max(1, Math.min(maxQuantity, stockForMax || 1));

  const handleAdd = () => {
    if (comingSoon || preorder) return;
    if (!size) {
      toast.error("لطفاً سایز را انتخاب کنید");
      return;
    }
    if (!combo || combo.soldOut) {
      toast.error("این ترکیب سایز و رنگ موجود نیست");
      return;
    }
    add({ productId: product.id, size, color: selectedColor, quantity });
    toast.success("به سبد خرید اضافه شد");
  };

  const addLabel = comingSoon
    ? "به‌زودی"
    : preorder
      ? "پیش‌خرید"
      : !size
        ? "انتخاب سایز"
        : !purchasable
          ? "ناموجود"
          : "افزودن به سبد خرید";

  const stockMessage = comingSoon
    ? availableAt
      ? `این محصول از ${availableAt} عرضه می‌شود.`
      : "این محصول به‌زودی عرضه می‌شود."
    : preorder
      ? availableAt
        ? `پیش‌خرید تا ${availableAt}؛ پس از عرضه ارسال می‌شود.`
        : "این محصول پیش‌فروش است."
      : combo && combo.stock <= product.lowStockThreshold && !combo.soldOut
        ? `فقط ${toFa(combo.stock)} عدد در انبار`
        : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <nav className="text-xs text-muted-foreground">
        <Link to="/" className="hover:text-foreground">
          خانه
        </Link>
        <span className="mx-2">/</span>
        <Link to="/shop" search={{ category: product.category }} className="hover:text-foreground">
          {categoryTitle(product.category)}
        </Link>
      </nav>

      <div className="mt-6 grid gap-10 md:grid-cols-2">
        <div>
          <div className="relative overflow-hidden bg-sand">
            <img
              src={product.images[active] ?? product.images[0]}
              alt={product.name}
              width={900}
              height={1100}
              className="h-auto w-full object-cover"
            />
            {badge && (
              <span className="surface-warm absolute top-3 right-3 rounded-full px-3 py-1 text-[10px] tracking-[0.2em]">
                {BADGE_LABELS[badge]}
              </span>
            )}
          </div>
          {product.images.length > 1 && (
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
          )}
        </div>

        <div>
          <p className="text-[11px] tracking-[0.2em] text-muted-foreground">
            {categoryTitle(product.category)}
          </p>
          <h1 className="mt-2 text-3xl leading-tight">{product.name}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
            {product.avgRating != null && product.reviewCount > 0 && (
              <span className="text-gold">
                ★ {toFa(product.avgRating.toFixed(1))}
                <span className="text-muted-foreground"> ({toFa(product.reviewCount)} نظر)</span>
              </span>
            )}
            {(comingSoon || preorder) && (
              <span className="rounded-full bg-sage/25 px-3 py-1 text-sage-deep">
                {comingSoon ? "به‌زودی" : "پیش‌خرید"}
              </span>
            )}
            {!comingSoon && !preorder && product.stock <= 0 && (
              <span className="rounded-full bg-clay px-3 py-1 text-muted-foreground">ناموجود</span>
            )}
          </div>

          <p className="mt-4 flex items-baseline gap-3">
            <span className="text-xl" data-testid="product-price">
              {formatToman(price)} تومان
            </span>
            {product.oldPrice && product.oldPrice > price && (
              <span className="text-sm text-muted-foreground line-through">
                {formatToman(product.oldPrice)}
              </span>
            )}
            {discount != null && (
              <span className="rounded-full bg-terracotta/10 px-2 py-0.5 text-xs text-terracotta">
                ٪{toFa(discount)} تخفیف
              </span>
            )}
          </p>
          <p className="mt-5 text-sm leading-7 text-muted-foreground">{product.description}</p>

          {product.tags.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {product.tags.map((tag) => (
                <Link
                  key={tag}
                  to="/shop"
                  search={{ q: tag }}
                  className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          <VariantPicker
            product={product}
            variants={variants}
            size={size}
            color={selectedColor}
            onSize={setSize}
            onColor={(next) => {
              setColor(next);
              // keep the chosen size only if it is still purchasable in the new colour
              if (size && variantStockFor(product, variants, size, next).soldOut) setSize(null);
            }}
          />

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
                onClick={() => setQuantity((q) => Math.min(quantityCeiling, q + 1))}
                aria-label="افزایش تعداد"
                className="p-2.5"
              >
                <Plus className="size-4" />
              </button>
            </div>
            <Button
              onClick={handleAdd}
              disabled={!purchasable}
              className="h-11 flex-1 rounded-none text-sm"
            >
              {addLabel}
            </Button>
          </div>

          {stockMessage && (
            <p
              className={cn(
                "mt-3 text-xs",
                comingSoon || preorder ? "text-sage-deep" : "text-terracotta",
              )}
            >
              {stockMessage}
            </p>
          )}

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
                {product.material}. شست‌وشو با آب سرد، خشک کردن در سایه و اتوی ملایم توصیه می‌شود.
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
                ارسال به تهران ۲۴ ساعت کاری و به سایر شهرها ۲ تا ۴ روز کاری. تعویض سایز تا ۷ روز پس
                از تحویل امکان‌پذیر است.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </div>
    </div>
  );
}
