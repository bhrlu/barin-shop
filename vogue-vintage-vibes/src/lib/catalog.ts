import { queryOptions, useQuery } from "@tanstack/react-query";
import { api, type Product as ApiProduct } from "@/lib/api";
import type { CategoryId, Product } from "@/data/products";

import catTshirt from "@/assets/cat-tshirt.jpg";
import catCrop from "@/assets/cat-crop.jpg";
import catShorts from "@/assets/cat-shorts.jpg";
import catSocks from "@/assets/cat-socks.jpg";
import catSet from "@/assets/cat-set.jpg";
import modelTshirt from "@/assets/model-tshirt.jpg";
import modelCrop from "@/assets/model-crop.jpg";

const assets: Record<string, string> = {
  "cat-tshirt": catTshirt,
  "cat-crop": catCrop,
  "cat-shorts": catShorts,
  "cat-socks": catSocks,
  "cat-set": catSet,
  "model-tshirt": modelTshirt,
  "model-crop": modelCrop,
};

/** Resolve a stored image reference: bundled asset key or absolute URL. */
export function img(reference: string | undefined): string {
  if (!reference) return catTshirt;
  if (/^https?:\/\//.test(reference) || reference.startsWith("/")) return reference;
  return assets[reference] ?? catTshirt;
}

/** A stored reference that lives in the product-images storage bucket. */
export function isStoragePath(reference: string): boolean {
  return reference.startsWith("uploads/");
}

/** Resolve any list of stored references (asset keys, URLs, storage paths) to displayable URLs. */
export async function resolveImageUrls(references: string[]): Promise<string[]> {
  const signed = await signStorageImages([{ images: references }]);
  return references.map((reference) => signed.get(reference) ?? img(reference));
}

/** Build signed URLs for every storage-backed image reference in one round trip. */
async function signStorageImages(rows: { images?: string[] }[]): Promise<Map<string, string>> {
  const paths = Array.from(new Set(rows.flatMap((row) => row.images ?? []).filter(isStoragePath)));
  const map = new Map<string, string>();
  if (paths.length === 0) return map;
  const signed = await api.signStorage(paths);
  for (const item of signed) {
    if (item.url) map.set(item.path, item.url);
  }
  return map;
}

export type AdminProduct = Product & { stock: number; active: boolean; rawImages: string[] };

export function toProduct(row: ApiProduct, signed?: Map<string, string>): AdminProduct {
  const resolve = (reference: string) => signed?.get(reference) ?? img(reference);
  const rawImages = row.images ?? [];
  return {
    id: row.id,
    name: row.name,
    category: row.category as CategoryId,
    price: row.price,
    ...(row.old_price ? { oldPrice: row.old_price } : {}),
    colors: (Array.isArray(row.colors) ? row.colors : []) as { name: string; hex: string }[],
    sizes: row.sizes ?? [],
    images: rawImages.map(resolve),
    rawImages,
    material: row.material,
    description: row.description,
    isNew: row.is_new,
    stock: row.stock,
    active: row.active,
  };
}

export const catalogQuery = queryOptions({
  queryKey: ["catalog"],
  queryFn: async () => {
    // include_inactive is ignored for anonymous callers; admins receive inactive rows too.
    const rows = await api.products({ include_inactive: true });
    const signed = await signStorageImages(rows);
    return rows.map((row) => toProduct(row, signed));
  },
});

export function useCatalog() {
  const query = useQuery(catalogQuery);
  const all = query.data ?? [];
  const products = all.filter((p) => p.active);
  const sizes = Array.from(new Set(products.flatMap((p) => p.sizes)));
  const colors = Array.from(
    new Map(products.flatMap((p) => p.colors).map((c) => [c.name, c])).values(),
  );
  const prices = products.map((p) => p.price);
  return {
    ...query,
    all,
    products,
    byId: (id: string) => all.find((p) => p.id === id),
    allSizes: sizes,
    allColors: colors,
    priceBounds: {
      min: prices.length ? Math.min(...prices) : 0,
      max: prices.length ? Math.max(...prices) : 2000000,
    },
  };
}
