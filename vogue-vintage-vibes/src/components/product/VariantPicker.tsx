import type { ProductVariant } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";
import { variantStockFor } from "@/lib/variants";
import { toFa } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Size × colour selection. Availability mirrors the backend (an explicit variant
 * wins for its combination; a deactivated or empty one is not purchasable), so
 * the UI can never offer a combination checkout would reject.
 */
export function VariantPicker({
  product,
  variants,
  size,
  color,
  onSize,
  onColor,
}: {
  product: AdminProduct;
  variants: ProductVariant[];
  size: string | null;
  color: string;
  onSize: (size: string) => void;
  onColor: (color: string) => void;
}) {
  const selected = size ? variantStockFor(product, variants, size, color) : null;

  return (
    <div className="mt-8 space-y-8">
      <div>
        <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">رنگ: {color}</p>
        <div className="flex flex-wrap gap-3">
          {product.colors.map((option) => {
            const soldOut = product.sizes.every(
              (s) => variantStockFor(product, variants, s, option.name).soldOut,
            );
            return (
              <button
                key={option.name}
                type="button"
                onClick={() => onColor(option.name)}
                disabled={soldOut}
                aria-pressed={color === option.name}
                aria-label={soldOut ? `${option.name} — ناموجود` : option.name}
                title={soldOut ? `${option.name} — ناموجود` : option.name}
                className={cn(
                  "size-8 rounded-full border border-border transition",
                  color === option.name && "ring-1 ring-foreground ring-offset-2",
                  soldOut && "cursor-not-allowed opacity-35",
                )}
                style={{ backgroundColor: option.hex }}
              />
            );
          })}
        </div>
      </div>

      <div>
        <p className="mb-3 text-xs tracking-[0.2em] text-muted-foreground">سایز</p>
        <div className="flex flex-wrap gap-2">
          {product.sizes.map((option) => {
            const { soldOut } = variantStockFor(product, variants, option, color);
            return (
              <button
                key={option}
                type="button"
                onClick={() => onSize(option)}
                disabled={soldOut}
                aria-pressed={size === option}
                title={soldOut ? `${toFa(option)} — ناموجود` : toFa(option)}
                className={cn(
                  "border px-4 py-2 text-sm transition-colors",
                  size === option
                    ? "border-foreground bg-foreground text-background"
                    : "border-border hover:border-foreground",
                  soldOut &&
                    "cursor-not-allowed border-dashed text-muted-foreground/60 line-through hover:border-border",
                )}
              >
                {toFa(option)}
              </button>
            );
          })}
        </div>

        <p className="mt-3 min-h-5 text-xs text-muted-foreground" aria-live="polite">
          {!size
            ? "برای دیدن موجودی، سایز را انتخاب کنید."
            : selected?.soldOut
              ? "این ترکیب سایز و رنگ موجود نیست."
              : selected && selected.stock <= product.lowStockThreshold
                ? `فقط ${toFa(selected.stock)} عدد باقی مانده`
                : "موجود در انبار"}
        </p>
      </div>
    </div>
  );
}
