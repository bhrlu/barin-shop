/**
 * API client for the SÂNDÉ FastAPI backend — the sole backend.
 *
 * Replaces @/integrations/supabase/*: JWT stored in localStorage, typed fetch
 * helpers for every endpoint the frontend uses. The browser talks to the
 * backend directly at VITE_API_URL (SSR fallback: BACKEND_URL process env).
 */

const API_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  (typeof process !== "undefined" ? process.env?.VITE_BACKEND_URL : "") ||
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
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init?.body;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, body });
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
    const message =
      (data && typeof data === "object" && "detail" in data &&
        typeof (data as { detail: unknown }).detail === "string"
        ? (data as { detail: string }).detail
        : null) ??
      (data && typeof data === "object" && "detail" in data
        ? JSON.stringify((data as { detail: unknown }).detail)
        : null) ??
      `خطای سرور (${res.status})`;
    throw new ApiError(res.status, message);
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
  created_at: string | null;
  updated_at: string | null;
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

export type StockIssue = { product_id: string; reason: string; available: number | null };

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

  // --- catalog ---
  products: (params?: { category?: string; include_inactive?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set("category", params.category);
    if (params?.include_inactive) qs.set("include_inactive", "true");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<Product[]>(`/products${suffix}`);
  },
  product: (id: string) => request<Product>(`/products/${id}`),

  // --- addresses ---
  addresses: () => request<Address[]>("/addresses"),
  createAddress: (body: Omit<Address, "id" | "created_at">) =>
    request<Address>("/addresses", { method: "POST", json: body }),
  deleteAddress: (id: string) =>
    request<void>(`/addresses/${id}`, { method: "DELETE" }),

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
    request<{ ok: boolean; order_number: string; refund_eligible: boolean }>(`/orders/${id}/cancel`, {
      method: "POST",
    }),
  requestRefund: (id: string, reason: string) =>
    request<{ id: string; status: string }>(`/orders/${id}/refunds`, {
      method: "POST",
      json: { reason },
    }),
  resolveRefund: (requestId: string, status: string, admin_note?: string) =>
    request<{ ok: boolean }>(`/refunds/${requestId}`, {
      method: "PATCH",
      json: { status, admin_note },
    }),
  patchOrder: (id: string, patch: { status?: string; payment_status?: string }) =>
    request<Order>(`/orders/${id}`, { method: "PATCH", json: patch }),
  paymentSession: (id: string) =>
    request<{
      order_id: string;
      order_number: string;
      total: number;
      payment_status: string;
      tracking_code: string;
    }>(`/orders/${id}/payment-session`),
  paymentComplete: (id: string, outcome: "success" | "failure") =>
    request<{ ok: boolean; order_number: string; reference: string | null }>(
      `/orders/${id}/payment-complete`,
      { method: "POST", json: { outcome } },
    ),
  myPayments: () => request<PaymentRecord[]>("/admin/payments").catch(() => request<PaymentRecord[]>("/orders")).then(() => [] as PaymentRecord[]),

  // --- admin ---
  adminStats: () =>
    request<{
      revenue: number;
      orderCount: number;
      pending: number;
      productCount: number;
      outOfStock: number;
      userCount: number;
      latest: { id: string; order_number: string; status: string; total: number; created_at: string }[];
    }>("/admin/stats"),
  adminUsers: () =>
    request<
      {
        id: string;
        email: string | null;
        full_name: string | null;
        phone: string | null;
        created_at: string;
        roles: string[];
        order_count: number;
        spent: number;
      }[]
    >("/admin/users"),
  adminOrders: () => request<Order[]>("/admin/orders"),
  adminPayments: () => request<PaymentRecord[]>("/admin/payments"),
  adminRefunds: () =>
    request<
      {
        id: string;
        order_id: string;
        order_number: string;
        amount: number;
        reason: string;
        status: string;
        admin_note: string | null;
        created_at: string;
      }[]
    >("/admin/refunds"),

  // --- storage (MinIO) ---
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
    request<{ query: string; total: number; hits: { id: string; name: string; price: number }[] }>(
      `/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
};

export { API_URL };
