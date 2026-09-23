import { queryOptions, useQuery } from "@tanstack/react-query";
import {
  api,
  type Availability,
  type Product as ApiProduct,
  type ProductBadge,
  type SearchHit,
} from "@/lib/api";
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

/**
 * Map raw image references (asset keys, absolute URLs, `uploads/…` storage paths)
 * to displayable URLs, whatever their order or duplication in the input.
 */
export async function resolveImageMap(
  references: (string | null | undefined)[],
): Promise<Map<string, string>> {
  const paths = Array.from(new Set(references.filter((ref): ref is string => !!ref)));
  const signed = await signStorageImages([{ images: paths }]);
  return new Map(paths.map((path) => [path, signed.get(path) ?? img(path)]));
}

export type AdminProduct = Product & {
  stock: number;
  active: boolean;
  rawImages: string[];
  tags: string[];
  badge: ProductBadge | null;
  availability: Availability;
  availableAt: string | null;
  lowStockThreshold: number;
  avgRating: number | null;
  reviewCount: number;
};

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
    tags: row.tags ?? [],
    badge: row.badge,
    availability: row.availability,
    availableAt: row.available_at,
    lowStockThreshold: row.low_stock_threshold,
    avgRating: row.avg_rating,
    reviewCount: row.review_count,
    stock: row.stock,
    active: row.active,
  };
}

/** Map a list of API rows to the local shape, signing storage images once. */
export async function toProducts(rows: ApiProduct[]): Promise<AdminProduct[]> {
  const signed = await resolveImageMap(rows.flatMap((row) => row.images ?? []));
  return rows.map((row) => toProduct(row, signed));
}

export const catalogQuery = queryOptions({
  queryKey: ["catalog"],
  queryFn: async () => {
    // include_inactive is ignored for anonymous callers; admins receive inactive rows too.
    // No `page` param → the API returns a bare array (F2.5 keeps it backward-compatible).
    return toProducts((await api.products({ include_inactive: true })) as ApiProduct[]);
  },
});

/**
 * `/shop` filter options (sizes, colours, tags, price range) from `GET /products/facets`,
 * so the page no longer downloads the whole catalogue to build them (F5.8). The key
 * sits under `["catalog"]`, so the admin's catalogue invalidations refresh it too.
 */
export const facetsQuery = queryOptions({
  queryKey: ["catalog", "facets"],
  queryFn: async () => {
    const facets = await api.productFacets();
    return {
      sizes: facets.sizes,
      colors: facets.colors,
      tags: [...facets.tags].sort((a, b) => a.localeCompare(b, "fa")),
      priceBounds: { min: facets.price_min ?? 0, max: facets.price_max ?? 2000000 },
    };
  },
});

// --- single product, its variants, reviews and discovery rails ------------------

export const productQuery = (id: string) =>
  queryOptions({
    queryKey: ["product", id],
    queryFn: async () => {
      const row = await api.product(id);
      const signed = await resolveImageMap(row.images ?? []);
      return toProduct(row, signed);
    },
  });

export const variantsQuery = (id: string) =>
  queryOptions({
    queryKey: ["product", id, "variants"],
    queryFn: () => api.productVariants(id),
  });

export const reviewsQuery = (id: string, limit = 20) =>
  queryOptions({
    queryKey: ["product", id, "reviews", limit],
    queryFn: () => api.productReviews(id, limit),
  });

export const relatedQuery = (id: string, limit = 4) =>
  queryOptions({
    queryKey: ["product", id, "related", limit],
    queryFn: async () => toProducts(await api.relatedProducts(id, limit)),
  });

export const recommendationsQuery = (id: string, limit = 8) =>
  queryOptions({
    queryKey: ["product", id, "recommendations", limit],
    queryFn: async () => toProducts(await api.recommendedProducts(id, limit)),
  });

/** Signed-in customer's most recently viewed products (newest first). */
export const recentlyViewedQuery = (limit = 8) =>
  queryOptions({
    queryKey: ["recently-viewed", limit],
    queryFn: async () => toProducts(await api.recentlyViewed(limit)),
  });

export function useCatalog() {
  const query = useQuery(catalogQuery);
  const all = query.data ?? [];
  return {
    ...query,
    all,
    products: all.filter((p) => p.active),
    byId: (id: string) => all.find((p) => p.id === id),
  };
}

// --- search (backend `GET /search`) ------------------------------------------

/**
 * `GET /search` hits carry less data than `GET /products` rows; this fills the
 * local `Product` shape `ProductCard` renders (name, price, category, image).
 */
function hitToProduct(hit: SearchHit, images: Map<string, string>): Product {
  return {
    id: hit.id,
    name: hit.name,
    category: hit.category as CategoryId,
    price: hit.price,
    ...(hit.old_price ? { oldPrice: hit.old_price } : {}),
    colors: [],
    sizes: [],
    images: [hit.image ? (images.get(hit.image) ?? img(hit.image)) : img(undefined)],
    material: "",
    description: "",
    isNew: hit.is_new,
    availability: hit.stock > 0 ? "in_stock" : "coming_soon",
  };
}

/** Full-text search through the backend, with storage-backed images signed. */
export const searchQuery = (q: string) =>
  queryOptions({
    queryKey: ["search", q],
    queryFn: async () => {
      const result = await api.search(q, 40);
      const images = await resolveImageMap(result.hits.map((hit) => hit.image));
      return {
        query: result.query,
        total: result.total,
        products: result.hits.map((hit) => hitToProduct(hit, images)),
      };
    },
  });
