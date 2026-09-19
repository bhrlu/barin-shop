/**
 * API client for the SÂNDÉ FastAPI backend — the sole backend.
 *
 * Replaces @/integrations/supabase/*: JWT stored in localStorage, typed fetch
 * helpers for every endpoint the frontend uses. The browser talks to the
 * backend directly at VITE_API_URL (SSR fallback: VITE_BACKEND_URL process env).
 */

const API_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.["VITE_API_URL"]) ||
  (typeof process !== "undefined" ? process.env?.["VITE_BACKEND_URL"] : "") ||
  "http://localhost:8000";

const TOKEN_KEY = "sande.access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function messageFrom(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message: unknown }).message;
    if (typeof message === "string") return message;
  }
  if (detail != null) {
    try {
      return JSON.stringify(detail);
    } catch {
      /* ignore */
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, body: rawBody, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = rawBody;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const finalInit: RequestInit = { ...rest, headers };
  if (body !== undefined) finalInit.body = body;
  const res = await fetch(`${API_URL}${path}`, finalInit);
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : data;
    throw new ApiError(res.status, messageFrom(detail, `خطای سرور (${res.status})`), detail);
  }
  return data as T;
}

// ---------------------------------------------------------------------------
// Types (mirror backend schemas)
// ---------------------------------------------------------------------------

export type UserInfo = {
  id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  role: string;
  created_at: string | null;
};

export type TokenResponse = { access_token: string; token_type: string; user: UserInfo };

export type ProductColor = { name: string; hex: string };

export type Availability = "in_stock" | "coming_soon" | "preorder";
export type ProductBadge = "sale" | "coming_soon" | "preorder" | "new" | "exclusive";
export type ProductSort = "new" | "price_asc" | "price_desc" | "popular" | "rating";

export type Product = {
  id: string;
  name: string;
  category: string;
  price: number;
  old_price: number | null;
  sizes: string[];
  colors: ProductColor[];
  images: string[];
  material: string;
  description: string;
  is_new: boolean;
  stock: number;
  active: boolean;
  tags: string[];
  badge: ProductBadge | null;
  availability: Availability;
  available_at: string | null;
  low_stock_threshold: number;
  avg_rating: number | null;
  review_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type ProductListParams = {
  category?: string;
  tag?: string;
  badge?: ProductBadge;
  availability?: Availability;
  on_sale?: boolean;
  size?: string;
  color?: string;
  min_price?: number;
  max_price?: number;
  sort?: ProductSort;
  include_inactive?: boolean;
};

// --- catalog: variants / reviews / discovery -----------------------------------

export type ProductVariant = {
  id: string;
  product_id: string;
  size: string;
  color: string;
  sku: string | null;
  stock: number;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ProductVariantInput = {
  size: string;
  color: string;
  sku?: string | null;
  stock?: number;
  active?: boolean;
};

export type Review = {
  id: string;
  product_id: string;
  user_id: string;
  rating: number;
  title: string;
  body: string;
  status: string;
  seller_reply: string | null;
  seller_replied_at: string | null;
  created_at: string | null;
  author_name: string | null;
};

export type ReviewList = {
  product_id: string;
  average: number | null;
  count: number;
  distribution: Record<string, number>;
  reviews: Review[];
};

export type ReviewInput = { rating: number; title?: string; body?: string };

export type SearchSuggestion = {
  id: string | null;
  label: string;
  kind: "product" | "category" | "tag" | "query";
  image: string | null;
};

export type SearchHit = {
  id: string;
  name: string;
  category: string;
  price: number;
  old_price: number | null;
  image: string | null;
  stock: number;
  is_new: boolean;
};

export type SearchResult = { query: string; total: number; hits: SearchHit[] };

export type SearchHistoryEntry = {
  id: string;
  query: string;
  created_at: string | null;
};

export type InventorySummary = {
  totalProducts: number;
  totalUnits: number;
  inventoryValue: number;
  outOfStock: number;
  lowStock: number;
  totalVariants: number;
  variantsOutOfStock: number;
};

export type LowStockProduct = {
  id: string;
  name: string;
  category: string;
  stock: number;
  low_stock_threshold: number;
};

export type LowStockVariant = {
  id: string;
  product_id: string;
  product_name: string;
  size: string;
  color: string;
  stock: number;
};

export type LowStockReport = {
  products: LowStockProduct[];
  variants: LowStockVariant[];
};

export type Address = {
  id: string;
  title: string;
  receiver: string;
  phone: string;
  province: string;
  city: string;
  postal_code: string | null;
  line: string;
  is_default: boolean;
  created_at: string | null;
};

export type OrderItem = {
  id: string;
  order_id: string;
  product_id: string | null;
  name: string;
  price: number;
  size: string | null;
  color: string | null;
  image: string | null;
  quantity: number;
};

export type Order = {
  id: string;
  order_number: string;
  user_id: string;
  status: string;
  payment_status: string;
  payment_method: string;
  subtotal: number;
  discount: number;
  shipping: number;
  total: number;
  shipping_address: Record<string, string>;
  note: string | null;
  created_at: string;
  items: OrderItem[];
};

export type PaymentRecord = {
  id: string;
  order_id: string;
  amount: number;
  method: string;
  status: string;
  reference: string | null;
  created_at: string;
  order_number?: string;
};

export type CheckoutLine = { product_id: string; size: string; color: string; quantity: number };

export type CheckoutAddress = {
  full_name: string;
  phone: string;
  city: string;
  line: string;
  postal_code?: string | null;
  note?: string | null;
};

export type CheckoutResult = {
  order_id: string;
  order_number: string;
  subtotal: number;
  discount: number;
  shipping: number;
  total: number;
  coupon_applied: string | null;
};

export type CouponValidation = {
  code: string;
  discount: number;
  percent_off: number | null;
  amount_off: number | null;
  min_subtotal: number;
  expires_at: string | null;
};

export type StockIssue = {
  product_id: string;
  reason: "not_found" | "inactive" | "insufficient_stock";
  available: number | null;
};

export type AdminStats = {
  revenue: number;
  orderCount: number;
  pending: number;
  productCount: number;
  outOfStock: number;
  userCount: number;
  latest: {
    id: string;
    order_number: string;
    status: string;
    total: number;
    created_at: string;
  }[];
};

export type AdminUser = {
  id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  created_at: string;
  roles: string[];
  order_count: number;
  spent: number;
};

export type RefundRequest = {
  id: string;
  order_id: string;
  order_number: string;
  amount: number;
  reason: string;
  status: string;
  admin_note: string | null;
  created_at: string;
};

export type PaymentSession = {
  order_id: string;
  order_number: string;
  total: number;
  payment_status: string;
  tracking_code: string;
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  // --- auth ---
  signUp: (body: { email: string; password: string; full_name?: string; phone?: string }) =>
    request<TokenResponse>("/auth/signup", { method: "POST", json: body }),
  signIn: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", json: body }),
  me: () => request<UserInfo>("/auth/me"),
  updateMe: (body: {
    full_name?: string | null;
    phone?: string | null;
    avatar_url?: string | null;
  }) => request<UserInfo>("/auth/me", { method: "PATCH", json: body }),

  // --- catalog ---
  products: (params: ProductListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.category) qs.set("category", params.category);
    if (params.tag) qs.set("tag", params.tag);
    if (params.badge) qs.set("badge", params.badge);
    if (params.availability) qs.set("availability", params.availability);
    if (params.on_sale) qs.set("on_sale", "true");
    if (params.size) qs.set("size", params.size);
    if (params.color) qs.set("color", params.color);
    if (params.min_price != null) qs.set("min_price", String(params.min_price));
    if (params.max_price != null) qs.set("max_price", String(params.max_price));
    if (params.sort) qs.set("sort", params.sort);
    if (params.include_inactive) qs.set("include_inactive", "true");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Product[]>(`/products${suffix}`);
  },
  product: (id: string) => request<Product>(`/products/${encodeURIComponent(id)}`),
  relatedProducts: (id: string, limit = 4) =>
    request<Product[]>(`/products/${encodeURIComponent(id)}/related?limit=${limit}`),
  recommendedProducts: (id: string, limit = 4) =>
    request<Product[]>(`/products/${encodeURIComponent(id)}/recommendations?limit=${limit}`),
  compareProducts: (ids: string[]) =>
    request<Product[]>(`/products/compare?ids=${ids.map(encodeURIComponent).join(",")}`),
  recordProductView: (id: string) =>
    request<{ ok: boolean }>(`/products/${encodeURIComponent(id)}/view`, { method: "POST" }),
  recentlyViewed: (limit = 10) => request<Product[]>(`/recently-viewed?limit=${limit}`),
  productVariants: (id: string) =>
    request<ProductVariant[]>(`/products/${encodeURIComponent(id)}/variants`),
  productReviews: (id: string, limit = 20) =>
    request<ReviewList>(`/products/${encodeURIComponent(id)}/reviews?limit=${limit}`),
  createReview: (id: string, body: ReviewInput) =>
    request<Review>(`/products/${encodeURIComponent(id)}/reviews`, { method: "POST", json: body }),
  deleteReview: (reviewId: string) => request<void>(`/reviews/${reviewId}`, { method: "DELETE" }),
  createProduct: (body: ProductWrite) =>
    request<Product>("/products", { method: "POST", json: body }),
  updateProduct: (id: string, body: Partial<ProductWrite>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", json: body }),
  deleteProduct: (id: string) => request<void>(`/products/${id}`, { method: "DELETE" }),

  // --- cart / checkout ---
  validateCoupon: (code: string, subtotal: number) =>
    request<CouponValidation>("/coupons/validate", {
      method: "POST",
      json: { code, subtotal },
    }),
  checkout: (body: {
    lines: CheckoutLine[];
    address: CheckoutAddress;
    coupon_code?: string | null;
  }) => request<CheckoutResult>("/checkout", { method: "POST", json: body }),
  stockCheck: (lines: CheckoutLine[]) =>
    request<{ ok: boolean; subtotal: number; issues: StockIssue[] }>("/stock/check", {
      method: "POST",
      json: { lines },
    }),

  // --- addresses ---
  addresses: () => request<Address[]>("/addresses"),
  createAddress: (body: Omit<Address, "id" | "created_at">) =>
    request<Address>("/addresses", { method: "POST", json: body }),
  deleteAddress: (id: string) => request<void>(`/addresses/${id}`, { method: "DELETE" }),

  // --- favorites ---
  favorites: () => request<string[]>("/favorites"),
  toggleFavorite: (productId: string) =>
    request<{ product_id: string; is_favorite: boolean }>(`/favorites/${productId}`, {
      method: "POST",
    }),

  // --- orders ---
  orders: () => request<Order[]>("/orders"),
  order: (id: string) => request<Order>(`/orders/${id}`),
  cancelOrder: (id: string) =>
    request<{ ok: boolean; order_number: string; refund_eligible: boolean }>(
      `/orders/${id}/cancel`,
      { method: "POST" },
    ),
  requestRefund: (id: string, reason: string) =>
    request<{ id: string; order_id: string; amount: number; status: string }>(
      `/orders/${id}/refunds`,
      { method: "POST", json: { reason } },
    ),
  resolveRefund: (requestId: string, status: string, admin_note?: string) =>
    request<{ ok: boolean }>(`/refunds/${requestId}`, {
      method: "PATCH",
      json: { status, admin_note },
    }),
  patchOrder: (id: string, patch: { status?: string; payment_status?: string }) =>
    request<Order>(`/orders/${id}`, { method: "PATCH", json: patch }),
  paymentSession: (id: string) => request<PaymentSession>(`/orders/${id}/payment-session`),
  paymentComplete: (id: string, outcome: "success" | "failure") =>
    request<{ ok: boolean; order_number: string; reference: string | null }>(
      `/orders/${id}/payment-complete`,
      { method: "POST", json: { outcome } },
    ),

  // --- payments ---
  myPayments: () => request<PaymentRecord[]>("/payments/mine"),

  // --- admin ---
  adminStats: () => request<AdminStats>("/admin/stats"),
  adminUsers: () => request<AdminUser[]>("/admin/users"),
  adminOrders: () => request<Order[]>("/admin/orders"),
  adminPayments: () => request<PaymentRecord[]>("/admin/payments"),
  adminRefunds: () => request<RefundRequest[]>("/admin/refunds"),

  // --- storage (MinIO) ---
  signStorage: (paths: string[]) =>
    request<{ path: string; url: string | null }[]>("/storage/sign", {
      method: "POST",
      json: { paths },
    }),
  uploadImage: async (file: File) => {
    const presign = await request<{ path: string; upload_url: string }>("/storage/upload-url", {
      method: "POST",
      json: { filename: file.name, content_type: file.type || "image/jpeg" },
    });
    const res = await fetch(presign.upload_url, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "image/jpeg" },
    });
    if (!res.ok) throw new ApiError(res.status, "آپلود انجام نشد");
    return presign.path;
  },

  // --- search ---
  search: (q: string, limit = 20) =>
    request<SearchResult>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  searchSuggest: (q: string, limit = 8) =>
    request<SearchSuggestion[]>(`/search/suggest?q=${encodeURIComponent(q)}&limit=${limit}`),
  searchHistory: (limit = 10) => request<SearchHistoryEntry[]>(`/search/history?limit=${limit}`),
  clearSearchHistory: () => request<void>("/search/history", { method: "DELETE" }),
  deleteSearchHistory: (id: string) => request<void>(`/search/history/${id}`, { method: "DELETE" }),

  // --- admin: catalog & inventory ---
  inventory: () => request<InventorySummary>("/admin/inventory"),
  lowStock: (threshold?: number) =>
    request<LowStockReport>(
      threshold != null
        ? `/admin/inventory/low-stock?threshold=${threshold}`
        : "/admin/inventory/low-stock",
    ),
  adminReviews: (status?: "published" | "hidden") =>
    request<Review[]>(status ? `/admin/reviews?status=${status}` : "/admin/reviews"),
  moderateReview: (id: string, status: "published" | "hidden") =>
    request<Review>(`/reviews/${id}`, { method: "PATCH", json: { status } }),
  replyToReview: (id: string, seller_reply: string) =>
    request<Review>(`/reviews/${id}`, { method: "PATCH", json: { seller_reply } }),
  createVariant: (productId: string, body: ProductVariantInput) =>
    request<ProductVariant>(`/products/${encodeURIComponent(productId)}/variants`, {
      method: "POST",
      json: body,
    }),
  updateVariant: (variantId: string, body: Partial<ProductVariantInput>) =>
    request<ProductVariant>(`/variants/${variantId}`, { method: "PATCH", json: body }),
  deleteVariant: (variantId: string) =>
    request<void>(`/variants/${variantId}`, { method: "DELETE" }),
};

export type ProductWrite = {
  name: string;
  category: string;
  price: number;
  old_price: number | null;
  sizes: string[];
  colors: ProductColor[];
  images: string[];
  material: string;
  description: string;
  is_new: boolean;
  stock: number;
  active: boolean;
};

export { API_URL };
