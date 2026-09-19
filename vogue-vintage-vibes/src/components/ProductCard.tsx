import { Link } from "@tanstack/react-router";
import { GitCompareArrows, Star } from "lucide-react";
import { toast } from "sonner";
import type { Product } from "@/data/products";
import { categoryTitle } from "@/data/products";
import { formatToman, toFa } from "@/lib/format";
import { useCompare } from "@/lib/compare";
import { cn } from "@/lib/utils";

export function ProductCard({ product }: { product: Product }) {
  const [first, second] = product.images;
  const { has, toggle } = useCompare();
  const comparing = has(product.id);

  return (
    <div className="group relative">
      <Link
        to="/product/$id"
        params={{ id: product.id }}
        className="block"
        aria-label={product.name}
      >
        <div className="relative overflow-hidden rounded-[1.25rem] bg-clay transition-shadow duration-500 group-hover:shadow-soft">
          <img
            src={first}
            alt={product.name}
            loading="lazy"
            width={900}
            height={1100}
            className="h-auto w-full object-cover transition-opacity duration-500 group-hover:opacity-0"
          />
          <img
            src={second ?? first}
            alt=""
            aria-hidden="true"
            loading="lazy"
            width={900}
            height={1100}
            className="absolute inset-0 h-full w-full scale-105 object-cover opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          />
          {product.isNew && (
            <span className="surface-warm absolute top-3 right-3 rounded-full px-3 py-1 text-[10px] tracking-[0.2em]">
              جدید
            </span>
          )}
        </div>
        <div className="pt-3">
          <p className="text-[11px] tracking-[0.18em] text-sage-deep">
            {categoryTitle(product.category)}
          </p>
          <h3 className="mt-1 font-display text-lg leading-7 transition-colors group-hover:text-terracotta">
            {product.name}
          </h3>
          <p className="mt-1 flex items-center gap-2 text-sm">
            <span className="text-terracotta">{formatToman(product.price)} تومان</span>
            {product.oldPrice && (
              <span className="text-xs text-muted-foreground line-through">
                {formatToman(product.oldPrice)}
              </span>
            )}
          </p>
          {product.avgRating != null && (product.reviewCount ?? 0) > 0 && (
            <p className="mt-1 flex items-center gap-1 text-xs">
              <Star className="size-3.5 fill-gold text-gold" />
              <span className="text-foreground">{toFa(product.avgRating.toFixed(1))}</span>
              <span className="text-muted-foreground">({toFa(product.reviewCount ?? 0)} نظر)</span>
            </p>
          )}
        </div>
      </Link>

      {/* sibling of the link, not a child — nested interactive elements are invalid */}
      <button
        type="button"
        aria-label={
          comparing ? `حذف ${product.name} از مقایسه` : `افزودن ${product.name} به مقایسه`
        }
        aria-pressed={comparing}
        onClick={() => {
          const result = toggle(product.id);
          if (result === "full") toast.error("حداکثر ۴ محصول را می‌توان مقایسه کرد");
          else if (result === "added") toast.success("به مقایسه اضافه شد");
        }}
        className={cn(
          "absolute top-3 left-3 rounded-full p-1.5 shadow-soft transition-colors",
          comparing
            ? "bg-terracotta text-primary-foreground"
            : "bg-background/85 text-foreground/60 hover:text-terracotta",
        )}
      >
        <GitCompareArrows className="size-3.5" />
      </button>
    </div>
  );
}
