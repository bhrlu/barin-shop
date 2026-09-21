# Back-End Development Tasks & Specifications (Back-Office)

This document outlines the required database schemas, Row Level Security (RLS) policies, Role-Based Access Control (RBAC), server functions/APIs, and integration workflows for the store's admin back-office.

---

## Epic 1: Database Architecture & Data Models

### [BE-01] Product Variants Matrix & Inventory Management
- **Goal:** Support multi-dimensional product variations (Size × Color) with independent inventory levels, pricing overrides, and SKUs.
- **Tables Required:**
  - `product_variants`:
    - `id` (UUID, PK, default `gen_random_uuid()`)
    - `product_id` (UUID, FK -> `products.id` ON DELETE CASCADE)
    - `sku` (VARCHAR, UNIQUE, indexed)
    - `size` (VARCHAR)
    - `color_name` (VARCHAR)
    - `color_hex` (VARCHAR)
    - `price_override` (NUMERIC, NULLABLE)
    - `stock_quantity` (INTEGER, NOT NULL DEFAULT 0)
    - `created_at` (TIMESTAMPTZ DEFAULT now())
  - `inventory_logs`:
    - `id` (UUID, PK)
    - `variant_id` (UUID, FK -> `product_variants.id`)
    - `change_amount` (INTEGER: positive for restock, negative for deduction)
    - `reason` (ENUM: `'purchase'`, `'restock'`, `'return'`, `'manual_adjustment'`)
    - `created_by` (UUID, FK -> `auth.users.id`)
    - `created_at` (TIMESTAMPTZ DEFAULT now())
- **Constraints & Indexes:** Unique composite key on `(product_id, size, color_name)`. Index on `sku` and `product_id`.

### [BE-02] Promotional Engine & Coupons
- **Goal:** Manage promotion campaigns, discount codes, usage limits, and expiration criteria.
- **Tables Required:**
  - `coupons`:
    - `id` (UUID, PK)
    - `code` (VARCHAR, UNIQUE, case-insensitive index)
    - `discount_type` (ENUM: `'percentage'`, `'fixed'`)
    - `value` (NUMERIC NOT NULL)
    - `min_order_amount` (NUMERIC DEFAULT 0)
    - `max_discount_cap` (NUMERIC NULLABLE)
    - `usage_limit` (INTEGER NULLABLE)
    - `used_count` (INTEGER DEFAULT 0)
    - `starts_at` (TIMESTAMPTZ NOT NULL)
    - `expires_at` (TIMESTAMPTZ NOT NULL)
    - `is_active` (BOOLEAN DEFAULT true)
  - `coupon_usages`:
    - `id` (UUID, PK)
    - `coupon_id` (UUID, FK -> `coupons.id`)
    - `user_id` (UUID, FK -> `auth.users.id`)
    - `order_id` (UUID, FK -> `orders.id`)
    - `used_at` (TIMESTAMPTZ DEFAULT now())
- **Acceptance Criteria:** Prevent race conditions on `usage_limit` using transactional counters or optimistic locking.

### [BE-03] Returns & Refund Requests Processing
- **Goal:** Customer cancellation/return requests, admin approval lifecycle, and accounting tracking.
- **Tables Required:**
  - `refund_requests`:
    - `id` (UUID, PK)
    - `order_id` (UUID, FK -> `orders.id`)
    - `user_id` (UUID, FK -> `auth.users.id`)
    - `amount` (NUMERIC NOT NULL)
    - `reason` (TEXT NOT NULL)
    - `status` (ENUM: `'pending'`, `'approved'`, `'rejected'`, `'refunded'`)
    - `bank_tracking_code` (VARCHAR NULLABLE)
    - `admin_notes` (TEXT NULLABLE)
    - `resolved_by` (UUID, FK -> `auth.users.id` NULLABLE)
    - `resolved_at` (TIMESTAMPTZ NULLABLE)
- **RLS Policies:**
  - Authenticated users can insert and select only their own records for orders they own.
  - Admins (via `has_role(auth.uid(), 'admin')`) have unrestricted SELECT and UPDATE privileges.

### [BE-04] Admin RBAC & Audit Logging
- **Goal:** Provide granular staff permissions and maintain a tamper-resistant trail of system changes.
- **Tables Required:**
  - `user_roles`: `(id, user_id, role: 'super_admin' | 'order_manager' | 'support', UNIQUE(user_id, role))`
  - `audit_logs`:
    - `id` (UUID, PK)
    - `admin_id` (UUID, FK -> `auth.users.id`)
    - `action` (VARCHAR, e.g. `'update_order_status'`, `'product_price_change'`)
    - `entity_type` (VARCHAR, e.g. `'order'`, `'product'`, `'user'`)
    - `entity_id` (VARCHAR)
    - `old_values` (JSONB)
    - `new_values` (JSONB)
    - `ip_address` (VARCHAR NULLABLE)
    - `created_at` (TIMESTAMPTZ DEFAULT now())

---

## Epic 2: Server Functions, APIs & Business Logic

### [BE-05] Order Lifecycle Management RPC (`updateOrderStatus`)
- **Signature:** `updateOrderStatus({ orderId, nextStatus, trackingCode?, internalNote? })`
- **Logic:**
  - Validate state machine transitions (e.g. `'cancelled'` orders cannot move to `'shipped'`).
  - Automatically reserve/commit stock on payment success; restore stock on order cancellation.
  - Insert log entries into `audit_logs`.
- **Execution:** Atomic database transaction to safeguard inventory consistency.

### [BE-06] Coupon Validation Engine (`validateCoupon`)
- **Signature:** `validateCoupon({ code, cartTotal, userId })`
- **Validation Rules:**
  - Code existence and active state (`is_active = true`).
  - Date validity (`starts_at <= now() <= expires_at`).
  - Total order value meets `min_order_amount`.
  - Global `usage_limit` not exceeded.
  - User-specific check (e.g. max 1 use per customer in `coupon_usages`).
- **Response:** Calculated discount deduction amount, sanitized coupon payload, or standard error codes.

### [BE-07] SMS Notification Gateway Integration
- **Provider:** Connect to transactional SMS service provider.
- **Triggers:**
  - On order status changed to `'processing'` or `'shipped'` (with postal tracking number).
  - On refund request approved/settled.
  - Immediate alert to operations team on high-value orders or new refund claims.

### [BE-08] Orders & Financial Data Export Service (`exportOrders`)
- **Signature:** `exportOrders({ fromDate, toDate, status?, format: 'csv' | 'xlsx' })`
- **Output:** Streamed CSV/XLSX export containing complete customer shipping details, SKU breakdown, payment reference, and tax/discount splits.

### [BE-09] Dashboard Aggregations RPC (`getDashboardKPIs`)
- **Signature:** `getDashboardKPIs({ timeRange: 'today' | '7d' | '30d' | 'all' })`
- **Aggregated Metrics:** Gross Revenue, Net Revenue, Total Paid Orders, Average Order Value (AOV), Pending Refunds Count, and Low-Stock Alert Count (< 5 units).
