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

/** Normalise an optional repeatable query param into a list. */
function asList(value: string | string[] | undefined): string[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
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

/** Headers with the stored bearer token attached (every backend call). */
function authHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

/** Response text → JSON when it parses, the raw string otherwise, null when empty. */
function parseBody(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** The error every failed backend call throws: FastAPI's `detail`, else the body. */
function apiError(status: number, data: unknown): ApiError {
  const detail =
    data && typeof data === "object" && "detail" in data
      ? (data as { detail: unknown }).detail
      : data;
  return new ApiError(status, messageFrom(detail, `خطای سرور (${status})`), detail);
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, body: rawBody, ...rest } = init ?? {};
  const headers = authHeaders(rest.headers);
  let body = rawBody;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const finalInit: RequestInit = { ...rest, headers };
  if (body !== undefined) finalInit.body = body;
  const res = await fetch(`${API_URL}${path}`, finalInit);
  if (res.status === 204) return undefined as T;
  const data = parseBody(await res.text());
  if (!res.ok) throw apiError(res.status, data);
  return data as T;
}

/** A downloaded file: the body plus the name the server chose (null if none). */
export type DownloadedFile = { blob: Blob; filename: string | null };

/** RFC 6266 filename: the UTF-8 `filename*` when present, else `filename`. */
function filenameFrom(disposition: string | null): string | null {
  if (!disposition) return null;
  const extended = /filename\*\s*=\s*[^']*'[^']*'([^;]+)/i.exec(disposition);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      /* malformed escape — fall back to the plain name */
    }
  }
  const plain = /filename\s*=\s*(?:"([^"]+)"|([^;]+))/i.exec(disposition);
  return (plain?.[1] ?? plain?.[2])?.trim() || null;
}

/** GET a file (AB-FE-02): same bearer token and `ApiError` as `request()`, but
 * the body comes back as a Blob. The backend must expose `Content-Disposition`
 * via CORS for the filename to be readable cross-origin. */
async function requestFile(path: string): Promise<DownloadedFile> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw apiError(res.status, parseBody(await res.text()));
  return { blob: await res.blob(), filename: filenameFrom(res.headers.get("Content-Disposition")) };
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
  /** One value or many (OR within the facet), sent as repeated `size` params. */
  size?: string | string[];
  color?: string | string[];
  min_price?: number;
  max_price?: number;
  sort?: ProductSort;
  include_inactive?: boolean;
  /** F2.5: when `page` is set the API returns the `{items,total,…}` envelope. */
  page?: number;
  page_size?: number;
};

/** Paginated list envelope (F2.5). Endpoints keep bare arrays when no `page`
 * param is sent, so old callers stay valid. */
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

/** Normalize a bare array (legacy response) into the Page envelope. Accepts
 * promises so callers can wrap a request directly. */
export function toPage<T>(data: T[] | Page<T>): Page<T>;
export function toPage<T>(data: Promise<T[] | Page<T>>): Promise<Page<T>>;
export function toPage<T>(
  data: T[] | Page<T> | Promise<T[] | Page<T>>,
): Page<T> | Promise<Page<T>> {
  if (data instanceof Promise) return data.then((resolved) => toPage(resolved));
  if (Array.isArray(data))
    return { items: data, total: data.length, page: 1, page_size: data.length, pages: 1 };
  return data;
}

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

export type ContactMessage = {
  id: string;
  user_id: string | null;
  name: string;
  contact: string;
  message: string;
  status: string;
  created_at: string | null;
};

export type ContactMessageStatus = "new" | "answered";

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
  // admin-entered postal/courier code (F2.8); absent until an admin sets it
  tracking_code: string | null;
  created_at: string;
  items: OrderItem[];
};

export type AdminCoupon = {
  id: string;
  code: string;
  percent_off: number | null;
  amount_off: number | null;
  min_subtotal: number;
  max_uses: number | null;
  max_uses_per_user: number;
  used_count: number;
  expires_at: string | null;
  active: boolean;
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
  province?: string | null;
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

export type StockIssueReason =
  "not_found" | "inactive" | "not_available" | "size_invalid" | "insufficient_stock";

export type StockIssue = {
  product_id: string;
  reason: StockIssueReason;
  available: number | null;
};

export type StockCheckResult = { ok: boolean; subtotal: number; issues: StockIssue[] };

export type KpiRange = "today" | "7d" | "30d" | "all";

export type AdminKpis = {
  range: KpiRange;
  grossRevenue: number;
  netRevenue: number;
  paidOrders: number;
  aov: number;
  pendingRefunds: number;
  lowStock: number;
  deltas: {
    grossRevenue: number | null;
    netRevenue: number | null;
    paidOrders: number | null;
    aov: number | null;
  };
  series: { date: string; revenue: number }[];
  statusBreakdown: { status: string; count: number }[];
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

export type ExportFormat = "csv" | "xlsx";

/** Bounds for `/admin/export/*`, already in the backend's wire format — build
 * them with `exportRange()`. Omitted bounds default server-side to 30 days. */
export type ExportRange = { from?: string; to?: string };

/** `GET /admin/export/report` (B2.2). Buckets are UTC days/months; `orders`
 * counts every order, `revenue` excludes cancelled ones; best-sellers exclude
 * cancelled orders and are capped at 10. */
export type SalesReport = {
  from: string;
  to: string;
  daily: { day: string; orders: number; revenue: number }[];
  monthly: { month: string; orders: number; revenue: number }[];
  bestSellers: { productId: string | null; name: string; units: number; revenue: number }[];
};

/**
 * Turn an inclusive local calendar range (`YYYY-MM-DD` from `<input type=date>`)
 * into `/admin/export/*` bounds. The backend reads `from`/`to` as UTC wall-clock
 * time (it drops any offset, B2.2b) and treats `to` as exclusive, so send local
 * midnight of `fromDate` and local midnight of the day *after* `toDate`, both as
 * offset-less UTC ISO strings.
 */
export function exportRange(fromDate: string, toDate: string): ExportRange {
  const localMidnight = (ymd: string, addDays = 0) => {
    const [year = 1970, month = 1, day = 1] = ymd.split("-").map(Number);
    return new Date(year, month - 1, day + addDays);
  };
  const naiveUtc = (date: Date) => date.toISOString().slice(0, 19);
  return { from: naiveUtc(localMidnight(fromDate)), to: naiveUtc(localMidnight(toDate, 1)) };
}

function exportQuery(range: ExportRange, status?: string): string {
  const qs = new URLSearchParams();
  if (range.from) qs.set("from", range.from);
  if (range.to) qs.set("to", range.to);
  if (status) qs.set("status", status);
  return qs.toString() ? `?${qs}` : "";
}

/** Roles `PUT /admin/users/{id}/roles` may set (B5.4). The legacy `admin` and
 * `customer` rows are outside its reach and are never sent. */
export type StaffRole = "super_admin" | "order_manager" | "support";

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

/** One `audit_logs` row as `GET /admin/audit-logs` returns it (B5.1, spec [BE-04]). */
export type AuditLogEntry = {
  id: string;
  admin_id: string | null;
  admin_email: string | null;
  admin_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string | null;
};

/** Filters for `GET /admin/audit-logs`; the endpoint pages by limit/offset and
 * returns a bare array (no `Page<T>` envelope, no total). */
export type AuditLogQuery = {
  action?: string;
  entity_type?: string;
  entity_id?: string;
  admin_id?: string;
  limit?: number;
  offset?: number;
};

export type RefundRequest = {
  id: string;
  order_id: string;
  order_number: string;
  amount: number;
  reason: string;
  status: string;
  admin_note: string | null;
  // spec [BE-03]: Paya/Satna code recorded at settlement, plus who/when
  bank_tracking_code: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  // claimant contact details (admin list only)
  user_email: string | null;
  user_name: string | null;
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
    // repeated params: the backend treats them as OR within the facet
    for (const value of asList(params.size)) qs.append("size", value);
    for (const value of asList(params.color)) qs.append("color", value);
    if (params.min_price != null) qs.set("min_price", String(params.min_price));
    if (params.max_price != null) qs.set("max_price", String(params.max_price));
    if (params.sort) qs.set("sort", params.sort);
    if (params.include_inactive) qs.set("include_inactive", "true");
    if (params.page) qs.set("page", String(params.page));
    if (params.page_size) qs.set("page_size", String(params.page_size));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Product[] | Page<Product>>(`/products${suffix}`);
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
  // `POST /stock/check` takes a bare JSON array of lines (not `{ lines }`) and
  // needs no auth, so guests get the same validation as signed-in customers.
  stockCheck: (lines: CheckoutLine[]) =>
    request<StockCheckResult>("/stock/check", { method: "POST", json: lines }),

  // --- addresses ---
  addresses: () => request<Address[]>("/addresses"),
  createAddress: (body: Omit<Address, "id" | "created_at">) =>
    request<Address>("/addresses", { method: "POST", json: body }),
  updateAddress: (id: string, patch: Partial<Omit<Address, "id" | "created_at">>) =>
    request<Address>(`/addresses/${id}`, { method: "PATCH", json: patch }),
  deleteAddress: (id: string) => request<void>(`/addresses/${id}`, { method: "DELETE" }),

  // --- contact ---
  // public: a guest can ask about a size or an order without an account
  // `website` is the B3.11 honeypot — always empty when a person submits the form
  contact: (body: { name: string; contact: string; message: string; website?: string }) =>
    request<ContactMessage>("/contact", { method: "POST", json: body }),
  // admin inbox (F2.1b) — F2.5: optional page/page_size envelope
  adminContactMessages: (status?: ContactMessageStatus, page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<ContactMessage[] | Page<ContactMessage>>(`/admin/contact-messages${suffix}`);
  },
  markContactMessage: (id: string, status: ContactMessageStatus) =>
    request<ContactMessage>(`/admin/contact-messages/${id}`, { method: "PATCH", json: { status } }),
  deleteContactMessage: (id: string) =>
    request<void>(`/admin/contact-messages/${id}`, { method: "DELETE" }),

  // --- favorites ---
  favorites: () => request<string[]>("/favorites"),
  toggleFavorite: (productId: string) =>
    request<{ product_id: string; is_favorite: boolean }>(`/favorites/${productId}`, {
      method: "POST",
    }),

  // --- orders ---
  orders: (page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Order[] | Page<Order>>(`/orders${suffix}`);
  },
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
  resolveRefund: (
    requestId: string,
    status: string,
    admin_note?: string,
    bank_tracking_code?: string,
  ) =>
    request<{ ok: boolean }>(`/refunds/${requestId}`, {
      method: "PATCH",
      json: {
        status,
        admin_note,
        bank_tracking_code: bank_tracking_code || null,
      },
    }),
  patchOrder: (
    id: string,
    patch: { status?: string; payment_status?: string; tracking_code?: string | null },
  ) => request<Order>(`/orders/${id}`, { method: "PATCH", json: patch }),
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
  adminKpis: (range: KpiRange = "30d") => request<AdminKpis>(`/admin/kpis?range=${range}`),
  adminUsers: (page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AdminUser[] | Page<AdminUser>>(`/admin/users${suffix}`);
  },
  // full replacement of the target's staff roles (F5.6 / B5.4, audited server-side)
  adminSetUserRoles: (userId: string, roles: StaffRole[]) =>
    request<{ userId: string; roles: StaffRole[] }>(`/admin/users/${userId}/roles`, {
      method: "PUT",
      json: { roles },
    }),
  adminOrders: (page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Order[] | Page<Order>>(`/admin/orders${suffix}`);
  },
  adminPayments: (page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<PaymentRecord[] | Page<PaymentRecord>>(`/admin/payments${suffix}`);
  },
  adminRefunds: () => request<RefundRequest[]>("/admin/refunds"),
  // audit trail (F5.5) — newest first, audit capability (admin/super_admin)
  adminAuditLogs: (query: AuditLogQuery = {}) => {
    const qs = new URLSearchParams();
    if (query.action) qs.set("action", query.action);
    if (query.entity_type) qs.set("entity_type", query.entity_type);
    if (query.entity_id) qs.set("entity_id", query.entity_id);
    if (query.admin_id) qs.set("admin_id", query.admin_id);
    if (query.limit) qs.set("limit", String(query.limit));
    if (query.offset) qs.set("offset", String(query.offset));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AuditLogEntry[]>(`/admin/audit-logs${suffix}`);
  },

  // --- admin coupon CRUD (F4.5 / spec FE-07) ---
  adminCoupons: () => request<{ coupons: AdminCoupon[] }>("/coupons"),
  adminCreateCoupon: (input: {
    code: string;
    percent_off: number | null;
    amount_off: number | null;
    min_subtotal: number;
    max_uses: number | null;
    max_uses_per_user: number;
    expires_at: string | null;
  }) => request<CouponValidation>("/coupons", { method: "POST", body: JSON.stringify(input) }),
  adminUpdateCoupon: (
    id: string,
    patch: Partial<{
      active: boolean;
      percent_off: number | null;
      amount_off: number | null;
      min_subtotal: number;
      max_uses: number | null;
      max_uses_per_user: number;
      expires_at: string | null;
    }>,
  ) => request<{ ok: boolean }>(`/coupons/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  adminDeleteCoupon: (id: string) => request<void>(`/coupons/${id}`, { method: "DELETE" }),
  adminGenerateCouponCode: () => request<{ code: string }>("/coupons/generate", { method: "POST" }),

  // --- admin exports & sales report (AB-FE-02 / B2.2) — `orders` capability ---
  adminExportOrders: (format: ExportFormat, range: ExportRange = {}, status?: string) =>
    requestFile(`/admin/export/orders.${format}${exportQuery(range, status)}`),
  adminExportProducts: (format: ExportFormat) => requestFile(`/admin/export/products.${format}`),
  adminSalesReport: (range: ExportRange = {}) =>
    request<SalesReport>(`/admin/export/report${exportQuery(range)}`),

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
  adminReviews: (status?: "published" | "hidden", page?: number, pageSize?: number) => {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (page) qs.set("page", String(page));
    if (pageSize) qs.set("page_size", String(pageSize));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Review[] | Page<Review>>(`/admin/reviews${suffix}`);
  },
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
  // merchandising / availability (defaults applied by the backend)
  tags: string[];
  badge: ProductBadge | null;
  availability: Availability;
  available_at: string | null;
  low_stock_threshold: number;
};

export { API_URL };
