import { Link } from "@tanstack/react-router";
import type { Product } from "@/data/products";
import { categoryTitle } from "@/data/products";
import { formatToman } from "@/lib/format";

export function ProductCard({ product }: { product: Product }) {
  const [first, second] = product.images;

  return (
    <Link
      to="/product/$id"
      params={{ id: product.id }}
      className="group block"
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
      </div>
    </Link>
  );
}