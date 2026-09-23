import { useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type ProductVariant } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";
import { formatToman, toFa } from "@/lib/format";
import {
  fieldErrors,
  variantSchema,
  type VariantDraft,
  type VariantValues,
} from "@/lib/product-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Per-product size × colour matrix ([BE-01] / [FE-04], AB-FE-03): size, colour with a
 * swatch (`color_hex`), SKU (unique when set), stock and an optional price override
 * that the server charges instead of the product price (AB-BE-02; shown in the
 * storefront since F5.18).
 *
 * An explicit variant row is authoritative for its combination on the backend
 * (see `app/services/variants.py`), which is why a row can be deactivated
 * individually. Datalists suggest the product's own sizes/colours but any value the
 * API accepts is allowed. Rows are validated with `variantSchema` (mirrors
 * `ProductVariantIn`) before anything is sent.
 */

function toDraft(variant: ProductVariant): VariantDraft {
  return {
    size: variant.size,
    color: variant.color,
    sku: variant.sku ?? "",
    stock: String(variant.stock),
    price_override: variant.price_override ? String(variant.price_override) : "",
    color_hex: variant.color_hex ?? "",
    active: variant.active,
  };
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

const grid =
  "grid gap-3 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.3fr)_minmax(0,1fr)_84px_minmax(0,1fr)_auto_auto]";

/** Colour name + a round swatch that opens the native colour picker. */
function ColorField({
  name,
  hex,
  listId,
  label,
  onName,
  onHex,
}: {
  name: string;
  hex: string;
  listId: string;
  label: string;
  onName: (value: string) => void;
  onHex: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label
        title={hex ? hex.toUpperCase() : "بدون کد رنگ"}
        className={`relative size-9 shrink-0 cursor-pointer rounded-full border ${
          hex ? "border-border" : "border-dashed border-muted-foreground/50"
        }`}
        style={hex ? { background: hex } : undefined}
      >
        <span className="sr-only">{`نمونهٔ ${label}`}</span>
        <input
          type="color"
          aria-label={`نمونهٔ ${label}`}
          value={hex || "#cccccc"}
          onChange={(event) => onHex(event.target.value)}
          className="absolute inset-0 size-full cursor-pointer opacity-0"
        />
      </label>
      <Input
        aria-label={label}
        list={listId}
        placeholder="رنگ"
        value={name}
        onChange={(event) => onName(event.target.value)}
        className="h-9 min-w-0 bg-background"
      />
      {hex ? (
        <button
          type="button"
          aria-label={`حذف کد رنگ ${label}`}
          onClick={() => onHex("")}
          className="shrink-0 text-muted-foreground hover:text-destructive"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  );
}

function Errors({ errors }: { errors: Record<string, string> | undefined }): ReactNode {
  const messages = Object.values(errors ?? {});
  if (!messages.length) return null;
  return (
    <p role="alert" className="text-[11px] text-destructive md:col-span-full">
      {messages.join(" · ")}
    </p>
  );
}

export function VariantEditor({ product }: { product: AdminProduct }) {
  const queryClient = useQueryClient();
  const variants = useQuery({
    queryKey: ["admin-variants", product.id],
    queryFn: () => api.productVariants(product.id),
  });
  const [drafts, setDrafts] = useState<Record<string, VariantDraft>>({});
  const [errors, setErrors] = useState<Record<string, Record<string, string>>>({});
  const firstColor = product.colors[0];
  const emptyDraft: VariantDraft = {
    size: product.sizes[0] ?? "",
    color: firstColor?.name ?? "",
    sku: "",
    stock: "0",
    price_override: "",
    color_hex: /^#[0-9a-fA-F]{6}$/.test(firstColor?.hex ?? "") ? firstColor!.hex : "",
    active: true,
  };
  const [draft, setDraft] = useState<VariantDraft>(emptyDraft);

  /** Picking a colour the product already defines brings its code along. */
  const withKnownHex = (row: VariantDraft, name: string): VariantDraft => {
    const known = product.colors.find((color) => color.name === name.trim())?.hex ?? "";
    return {
      ...row,
      color: name,
      color_hex: !row.color_hex && /^#[0-9a-fA-F]{6}$/.test(known) ? known : row.color_hex,
    };
  };

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-variants", product.id] });
    void queryClient.invalidateQueries({ queryKey: ["product", product.id, "variants"] });
    void queryClient.invalidateQueries({ queryKey: ["catalog"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-products"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-inventory"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-low-stock"] });
  };

  const create = useMutation({
    mutationFn: (values: VariantValues) =>
      api.createVariant(product.id, {
        size: values.size,
        color: values.color,
        stock: values.stock,
        active: values.active,
        sku: values.sku || null,
        price_override: values.price_override,
        color_hex: values.color_hex || null,
      }),
    onSuccess: () => {
      refresh();
      setDraft({ ...draft, sku: "", stock: "0", price_override: "" });
      toast.success("تنوع جدید ثبت شد");
    },
    onError: (error) => toast.error(errorMessage(error, "ثبت تنوع انجام نشد")),
  });

  const update = useMutation({
    // every field is sent; the clear values are "" (SKU, colour code) and 0 (price)
    mutationFn: (input: { id: string; values: VariantValues }) =>
      api.updateVariant(input.id, {
        size: input.values.size,
        color: input.values.color,
        stock: input.values.stock,
        active: input.values.active,
        sku: input.values.sku,
        price_override: input.values.price_override ?? 0,
        color_hex: input.values.color_hex,
      }),
    onSuccess: (_data, variables) => {
      refresh();
      setDrafts((current) => {
        const next = { ...current };
        delete next[variables.id];
        return next;
      });
      toast.success("تنوع به‌روزرسانی شد");
    },
    onError: (error) => toast.error(errorMessage(error, "به‌روزرسانی تنوع انجام نشد")),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteVariant(id),
    onSuccess: () => {
      refresh();
      toast.success("تنوع حذف شد");
    },
    onError: (error) => toast.error(errorMessage(error, "حذف تنوع انجام نشد")),
  });

  /** Validate a row; on failure keep its messages and return null. */
  const validate = (key: string, row: VariantDraft): VariantValues | null => {
    const parsed = variantSchema.safeParse(row);
    setErrors((current) => {
      const next = { ...current };
      if (parsed.success) delete next[key];
      else next[key] = fieldErrors(parsed.error);
      return next;
    });
    return parsed.success ? parsed.data : null;
  };

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    const values = validate("new", draft);
    if (values) create.mutate(values);
  };

  const rows = variants.data ?? [];
  const sizesId = `variant-sizes-${product.id}`;
  const colorsId = `variant-colors-${product.id}`;
  const pricePlaceholder = `قیمت محصول: ${formatToman(product.price)}`;

  return (
    <section className="rounded-3xl border border-border bg-background/60 p-5">
      <h3 className="text-sm">
        تنوع‌های سایز × رنگ
        {rows.length > 0 && <span className="text-muted-foreground"> ({toFa(rows.length)})</span>}
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        موجودی هر ترکیب، موجودی محصول را بازنویسی می‌کند؛ ترکیب غیرفعال قابل سفارش نیست. قیمت
        اختصاصی خالی یعنی قیمت محصول.
      </p>

      <datalist id={sizesId}>
        {product.sizes.map((size) => (
          <option key={size} value={size} />
        ))}
      </datalist>
      <datalist id={colorsId}>
        {product.colors.map((color) => (
          <option key={color.name} value={color.name} />
        ))}
      </datalist>

      <div
        aria-hidden
        className={`${grid} mt-4 hidden px-3 text-[11px] text-muted-foreground md:grid`}
      >
        <span>سایز</span>
        <span>رنگ</span>
        <span>SKU</span>
        <span>موجودی</span>
        <span>قیمت اختصاصی (تومان)</span>
        <span />
        <span />
      </div>

      {variants.isLoading ? (
        <p className="mt-4 text-xs text-muted-foreground">در حال بارگذاری…</p>
      ) : variants.isError ? (
        <p className="mt-4 text-xs text-terracotta">خواندن تنوع‌ها انجام نشد.</p>
      ) : rows.length === 0 ? (
        <p className="mt-4 text-xs text-muted-foreground">
          تنوعی ثبت نشده؛ موجودی کل محصول برای همه ترکیب‌ها اعمال می‌شود.
        </p>
      ) : (
        <ul className="mt-2 space-y-3">
          {rows.map((variant) => {
            const row = drafts[variant.id] ?? toDraft(variant);
            const set = (patch: Partial<VariantDraft>) =>
              setDrafts({ ...drafts, [variant.id]: { ...row, ...patch } });
            const original = toDraft(variant);
            const dirty = (Object.keys(original) as (keyof VariantDraft)[]).some(
              (key) => row[key] !== original[key],
            );
            return (
              <li key={variant.id} className={`${grid} rounded-xl bg-sand p-3`}>
                <Input
                  aria-label="سایز"
                  list={sizesId}
                  value={row.size}
                  onChange={(e) => set({ size: e.target.value })}
                  className="h-9 bg-background"
                />
                <ColorField
                  name={row.color}
                  hex={row.color_hex}
                  listId={colorsId}
                  label="رنگ"
                  onName={(value) =>
                    setDrafts({ ...drafts, [variant.id]: withKnownHex(row, value) })
                  }
                  onHex={(value) => set({ color_hex: value })}
                />
                <Input
                  aria-label="SKU"
                  dir="ltr"
                  placeholder="SKU"
                  value={row.sku}
                  onChange={(e) => set({ sku: e.target.value })}
                  className="h-9 bg-background font-mono tracking-wider"
                />
                <Input
                  aria-label="موجودی"
                  dir="ltr"
                  inputMode="numeric"
                  value={row.stock}
                  onChange={(e) => set({ stock: e.target.value })}
                  className="h-9 bg-background"
                />
                <Input
                  aria-label="قیمت اختصاصی"
                  dir="ltr"
                  inputMode="numeric"
                  placeholder={pricePlaceholder}
                  value={row.price_override}
                  onChange={(e) => set({ price_override: e.target.value })}
                  className="h-9 bg-background"
                />
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={row.active}
                    onChange={(e) => set({ active: e.target.checked })}
                  />
                  فعال
                </label>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label="ذخیره تنوع"
                    disabled={!dirty || update.isPending}
                    onClick={() => {
                      const values = validate(variant.id, row);
                      if (values) update.mutate({ id: variant.id, values });
                    }}
                    className="text-muted-foreground transition-opacity hover:text-sage-deep disabled:opacity-30"
                  >
                    <Save className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="حذف تنوع"
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(variant.id)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
                <Errors errors={errors[variant.id]} />
              </li>
            );
          })}
        </ul>
      )}

      <form onSubmit={handleCreate} noValidate className="mt-5 border-t border-border pt-5">
        <p className="text-xs text-muted-foreground">افزودن ترکیب</p>
        <div className={`${grid} mt-3`}>
          <Input
            aria-label="سایز جدید"
            list={sizesId}
            placeholder="سایز"
            value={draft.size}
            onChange={(e) => setDraft({ ...draft, size: e.target.value })}
            className="h-9 bg-background"
          />
          <ColorField
            name={draft.color}
            hex={draft.color_hex}
            listId={colorsId}
            label="رنگ جدید"
            onName={(value) => setDraft(withKnownHex(draft, value))}
            onHex={(value) => setDraft({ ...draft, color_hex: value })}
          />
          <Input
            aria-label="SKU جدید"
            dir="ltr"
            placeholder="SKU"
            value={draft.sku}
            onChange={(e) => setDraft({ ...draft, sku: e.target.value })}
            className="h-9 bg-background font-mono tracking-wider"
          />
          <Input
            aria-label="موجودی جدید"
            dir="ltr"
            inputMode="numeric"
            value={draft.stock}
            onChange={(e) => setDraft({ ...draft, stock: e.target.value })}
            className="h-9 bg-background"
          />
          <Input
            aria-label="قیمت اختصاصی جدید"
            dir="ltr"
            inputMode="numeric"
            placeholder={pricePlaceholder}
            value={draft.price_override}
            onChange={(e) => setDraft({ ...draft, price_override: e.target.value })}
            className="h-9 bg-background"
          />
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={draft.active}
              onChange={(e) => setDraft({ ...draft, active: e.target.checked })}
            />
            فعال
          </label>
          <Button type="submit" disabled={create.isPending} className="h-9 gap-1.5">
            {create.isPending ? <Check className="size-4" /> : <Plus className="size-4" />}
            افزودن
          </Button>
          <Errors errors={errors["new"]} />
        </div>
      </form>
    </section>
  );
}
