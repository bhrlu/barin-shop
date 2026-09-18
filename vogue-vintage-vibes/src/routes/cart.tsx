import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Minus, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useCatalog } from "@/lib/catalog";
import { formatToman, toFa } from "@/lib/format";
import { useCart } from "@/lib/cart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/cart")({
  head: () => ({
    meta: [
      { title: "سبد خرید — ساندِه" },
      { name: "description", content: "مرور و ویرایش سبد خرید شما در فروشگاه ساندِه." },
      { property: "og:title", content: "سبد خرید — ساندِه" },
      { property: "og:description", content: "مرور و ویرایش سبد خرید." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: CartPage,
});

const SHIPPING = 89000;
const FREE_SHIPPING_FROM = 2000000;

function CartPage() {
  const { lines, subtotal, setQuantity, remove } = useCart();
  const { byId } = useCatalog();
  const [code, setCode] = useState("");
  const [discount, setDiscount] = useState(0);

  const shipping = subtotal === 0 || subtotal >= FREE_SHIPPING_FROM ? 0 : SHIPPING;
  const total = Math.max(0, subtotal - discount) + shipping;

  const applyCode = () => {
    if (code.trim().toUpperCase() === "SANDE10") {
      setDiscount(Math.round(subtotal * 0.1));
      toast.success("کد تخفیف ۱۰٪ اعمال شد");
    } else {
      setDiscount(0);
      toast.error("کد تخفیف معتبر نیست");
    }
  };

  if (lines.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-24 text-center sm:px-6">
        <h1 className="text-3xl">سبد خرید شما خالی است</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          از کالکشن جدید شروع کنید و تکه‌های مورد علاقه‌تان را اضافه کنید.
        </p>
        <Link
          to="/shop"
          search={{}}
          className="mt-8 inline-flex border border-foreground px-8 py-3 text-sm tracking-widest transition-colors hover:bg-foreground hover:text-background"
        >
          رفتن به فروشگاه
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <h1 className="text-4xl">سبد خرید</h1>

      <div className="mt-10 grid gap-12 md:grid-cols-[1fr_320px]">
        <ul className="divide-y divide-border border-y border-border">
          {lines.map((line, index) => {
            const product = byId(line.productId);
            if (!product) return null;
            return (
              <li key={`${line.productId}-${line.size}-${line.color}`} className="flex gap-4 py-6">
                <Link to="/product/$id" params={{ id: product.id }} className="w-24 shrink-0">
                  <img
                    src={product.images[0]}
                    alt={product.name}
                    loading="lazy"
                    className="h-32 w-full object-cover"
                  />
                </Link>
                <div className="flex-1">
                  <Link to="/product/$id" params={{ id: product.id }}>
                    <h2 className="font-display text-lg">{product.name}</h2>
                  </Link>
                  <p className="mt-1 text-xs text-muted-foreground">
                    سایز {toFa(line.size)} · رنگ {line.color}
                  </p>
                  <div className="mt-4 flex items-center gap-4">
                    <div className="flex items-center border border-border">
                      <button
                        type="button"
                        aria-label="کاهش"
                        onClick={() => setQuantity(index, line.quantity - 1)}
                        className="p-2"
                      >
                        <Minus className="size-3.5" />
                      </button>
                      <span className="w-8 text-center text-sm">{toFa(line.quantity)}</span>
                      <button
                        type="button"
                        aria-label="افزایش"
                        onClick={() => setQuantity(index, line.quantity + 1)}
                        className="p-2"
                      >
                        <Plus className="size-3.5" />
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => remove(index)}
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" /> حذف
                    </button>
                  </div>
                </div>
                <p className="shrink-0 text-sm">
                  {formatToman(product.price * line.quantity)} تومان
                </p>
              </li>
            );
          })}
        </ul>

        <aside className="h-fit bg-sand p-6">
          <h2 className="text-xl">خلاصه سفارش</h2>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">جمع کالاها</dt>
              <dd>{formatToman(subtotal)} تومان</dd>
            </div>
            {discount > 0 && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">تخفیف</dt>
                <dd>−{formatToman(discount)} تومان</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-muted-foreground">ارسال</dt>
              <dd>{shipping === 0 ? "رایگان" : `${formatToman(shipping)} تومان`}</dd>
            </div>
            <div className="flex justify-between border-t border-border pt-3 text-base">
              <dt>مبلغ نهایی</dt>
              <dd>{formatToman(total)} تومان</dd>
            </div>
          </dl>

          <div className="mt-6 flex gap-2">
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="کد تخفیف"
              className="rounded-none bg-background"
            />
            <Button variant="outline" className="rounded-none" onClick={applyCode}>
              ثبت
            </Button>
          </div>

          <Link
            to="/checkout"
            className="mt-6 block bg-foreground py-3 text-center text-sm tracking-widest text-background transition-opacity hover:opacity-90"
          >
            تکمیل خرید
          </Link>
        </aside>
      </div>
    </div>
  );
}