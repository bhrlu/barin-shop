/**
 * The admin product editor's form model (AB-FE-03): labels, Zod schemas and the
 * mapping between a catalogue row, the form and the API payload.
 *
 * The schemas mirror the backend's constraints (`app/schemas.py` `ProductBase`,
 * `ProductVariantIn`) and add none of their own (R8). Numbers are typed as text, so
 * Persian / Arabic digits are accepted and read as Latin ones. The product payload is
 * exactly what the pre-RHF form sent.
 */
import { z } from "zod";
import type { Availability, ProductBadge, ProductWrite } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";
import { toLatinDigits } from "@/lib/format";

export const BADGES: { value: ProductBadge | ""; label: string }[] = [
  { value: "", label: "بدون نشان" },
  { value: "sale", label: "حراج" },
  { value: "new", label: "جدید" },
  { value: "exclusive", label: "ویژه" },
  { value: "coming_soon", label: "به‌زودی" },
  { value: "preorder", label: "پیش‌خرید" },
];

export const AVAILABILITIES: { value: Availability; label: string }[] = [
  { value: "in_stock", label: "موجود" },
  { value: "coming_soon", label: "به‌زودی" },
  { value: "preorder", label: "پیش‌خرید" },
];

const digits = (value: string) => toLatinDigits(value.trim());

/** A required whole number ≥ `min` typed as text (backend: `int`, `gt=0` / `ge=0`). */
export const wholeNumber = (label: string, min: 0 | 1) =>
  z
    .string()
    .transform(digits)
    .pipe(
      z
        .string()
        .min(1, `${label} را وارد کنید`)
        .regex(/^\d+$/, `${label} باید یک عدد صحیح باشد`)
        .transform(Number)
        .refine(
          (value) => value >= min,
          min === 1 ? `${label} باید بیشتر از صفر باشد` : `${label} نمی‌تواند منفی باشد`,
        ),
    );

/** An optional whole number > 0: empty → `null` (backend: `int | None`, `gt=0`). */
export const optionalPositive = (label: string) =>
  z
    .string()
    .transform(digits)
    .pipe(
      z.union([
        z.literal("").transform(() => null),
        z
          .string()
          .regex(/^\d+$/, `${label} باید یک عدد صحیح باشد`)
          .transform(Number)
          .refine((value) => value > 0, `${label} باید بیشتر از صفر باشد`),
      ]),
    );

const list = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export const productSchema = z
  .object({
    name: z.string().min(1, "نام محصول را وارد کنید").max(200, "نام حداکثر ۲۰۰ نویسه است"),
    category: z.string().min(1, "دسته را انتخاب کنید").max(40, "دسته نامعتبر است"),
    price: wholeNumber("قیمت", 1),
    old_price: optionalPositive("قیمت قبل از تخفیف"),
    stock: wholeNumber("موجودی", 0),
    // an empty threshold was always sent as 0
    low_stock_threshold: z
      .string()
      .transform(digits)
      .pipe(
        z.union([
          z.literal("").transform(() => 0),
          z.string().regex(/^\d+$/, "آستانه باید یک عدد صحیح و نامنفی باشد").transform(Number),
        ]),
      ),
    sizes: z.string(),
    colors: z.string(),
    tags: z.string(),
    images: z.array(z.string()),
    material: z.string(),
    description: z.string(),
    is_new: z.boolean(),
    active: z.boolean(),
    badge: z.enum(["", "sale", "new", "exclusive", "coming_soon", "preorder"]),
    availability: z.enum(["in_stock", "coming_soon", "preorder"]),
    available_at: z.string(),
  })
  .transform((form): ProductWrite => ({
    name: form.name,
    category: form.category,
    price: form.price,
    old_price: form.old_price,
    sizes: list(form.sizes),
    // «نام #hex» per comma-separated chunk — the last word is the colour code
    colors: list(form.colors).map((chunk) => {
      const parts = chunk.split(/\s+/);
      const hex = parts.pop() ?? "#cccccc";
      return { name: parts.join(" ") || "رنگ", hex };
    }),
    images: form.images,
    material: form.material,
    description: form.description,
    stock: form.stock,
    is_new: form.is_new,
    active: form.active,
    tags: list(form.tags),
    badge: form.badge === "" ? null : form.badge,
    availability: form.availability,
    // only meaningful for coming_soon / preorder; cleared otherwise
    available_at: form.availability === "in_stock" || !form.available_at ? null : form.available_at,
    low_stock_threshold: form.low_stock_threshold,
  }));

export type ProductFormValues = z.input<typeof productSchema>;

export const emptyProductForm: ProductFormValues = {
  name: "",
  category: "tshirt",
  price: "",
  old_price: "",
  sizes: "S, M, L",
  colors: "کرم #f0ebe3, تِراکوتا #b5654a",
  images: ["cat-tshirt"],
  material: "",
  description: "",
  stock: "25",
  is_new: true,
  active: true,
  tags: "",
  badge: "",
  availability: "in_stock",
  available_at: "",
  low_stock_threshold: "5",
};

/** `available_at` is a date input value (`YYYY-MM-DD`); the API returns ISO strings. */
function toDateInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

export function productToForm(product: AdminProduct): ProductFormValues {
  return {
    name: product.name,
    category: product.category,
    price: String(product.price),
    old_price: product.oldPrice ? String(product.oldPrice) : "",
    sizes: product.sizes.join(", "),
    colors: product.colors.map((c) => `${c.name} ${c.hex}`).join(", "),
    images: product.rawImages,
    material: product.material,
    description: product.description,
    stock: String(product.stock),
    is_new: product.isNew ?? true,
    active: product.active ?? true,
    tags: product.tags.join(", "),
    badge: product.badge ?? "",
    availability: product.availability ?? "in_stock",
    available_at: toDateInput(product.availableAt),
    low_stock_threshold: String(product.lowStockThreshold ?? 5),
  };
}

// --- variant rows ([BE-01] matrix: size, colour + swatch, SKU, stock, price override) --

export const variantSchema = z.object({
  size: z.string().trim().min(1, "سایز را وارد کنید").max(40, "سایز حداکثر ۴۰ نویسه است"),
  color: z.string().trim().min(1, "رنگ را وارد کنید").max(60, "رنگ حداکثر ۶۰ نویسه است"),
  sku: z.string().trim().max(80, "SKU حداکثر ۸۰ نویسه است"),
  stock: wholeNumber("موجودی", 0),
  price_override: optionalPositive("قیمت اختصاصی"),
  color_hex: z.string().regex(/^(#[0-9a-fA-F]{6})?$/, "کد رنگ باید به شکل #RRGGBB باشد"),
  active: z.boolean(),
});

export type VariantDraft = z.input<typeof variantSchema>;
export type VariantValues = z.output<typeof variantSchema>;

/** First message per field, for inline errors. */
export function fieldErrors(error: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "");
    if (!(key in out)) out[key] = issue.message;
  }
  return out;
}
