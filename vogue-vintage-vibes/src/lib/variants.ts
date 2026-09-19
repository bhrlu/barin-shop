/**
 * Size × colour availability for the storefront.
 *
 * Mirror of the backend's `app/services/variants.py`: an explicit
 * `product_variants` row is authoritative for its combination (its `active` flag
 * can disable it), otherwise the product's aggregate stock applies. Sharing the
 * rule keeps the UI from offering a combination checkout would reject.
 */

import type { ProductVariant } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";

export type ComboStock = { stock: number; available: boolean; soldOut: boolean };

/** Effective stock for one combination given its (optional) variant row. */
export function comboStock(
  product: { stock: number },
  variant: ProductVariant | undefined,
): ComboStock {
  const stock = variant ? variant.stock : product.stock;
  const available = variant ? variant.active : true;
  return { stock, available, soldOut: !available || stock <= 0 };
}

/** Effective stock for a size×color of this product. */
export function variantStockFor(
  product: Pick<AdminProduct, "id" | "stock">,
  variants: ProductVariant[],
  size: string,
  color: string,
): ComboStock {
  return comboStock(
    product,
    variants.find((v) => v.product_id === product.id && v.size === size && v.color === color),
  );
}

/** First colour with at least one purchasable size; falls back to the first colour. */
export function defaultColor(product: AdminProduct, variants: ProductVariant[]): string {
  const withStock = product.colors.find((color) =>
    product.sizes.some((size) => !variantStockFor(product, variants, size, color.name).soldOut),
  );
  return withStock?.name ?? product.colors[0]?.name ?? "";
}
