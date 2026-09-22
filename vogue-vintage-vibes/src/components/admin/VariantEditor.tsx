import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type ProductVariant } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";
import { toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Per-product size × colour stock editor.
 *
 * An explicit variant row is authoritative for its combination on the backend
 * (see `app/services/variants.py`), which is why a row can be deactivated
 * individually. Datalists suggest the product's own sizes/colours but any value
 * the API accepts is allowed, so a typo shows up here rather than silently
 * creating an unreachable combination.
 */

type Draft = { size: string; color: string; stock: string; active: boolean };
/** Same as `Draft` with the stock parsed — what actually goes to the API. */
type VariantPayload = { size: string; color: string; stock: number; active: boolean };

function toDraft(variant: ProductVariant): Draft {
  return {
    size: variant.size,
    color: variant.color,
    stock: String(variant.stock),
    active: variant.active,
  };
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

/** Non-negative integer, or `null` for anything the backend would reject. */
function parseStock(value: string): number | null {
  const trimmed = value.trim();
  return /^\d+$/.test(trimmed) ? Number(trimmed) : null;
}

export function VariantEditor({ product }: { product: AdminProduct }) {
  const queryClient = useQueryClient();
  const variants = useQuery({
    queryKey: ["admin-variants", product.id],
    queryFn: () => api.productVariants(product.id),
  });
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [draft, setDraft] = useState<Draft>({
    size: product.sizes[0] ?? "",
    color: product.colors[0]?.name ?? "",
    stock: "0",
    active: true,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-variants", product.id] });
    void queryClient.invalidateQueries({ queryKey: ["product", product.id, "variants"] });
    void queryClient.invalidateQueries({ queryKey: ["catalog"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-products"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-inventory"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-low-stock"] });
  };

  const create = useMutation({
    mutationFn: (payload: VariantPayload) =>
      api.createVariant(product.id, {
        size: payload.size.trim(),
        color: payload.color.trim(),
        stock: payload.stock,
        active: payload.active,
      }),
    onSuccess: () => {
      refresh();
      setDraft({ ...draft, stock: "0" });
      toast.success("تنوع جدید ثبت شد");
    },
    onError: (error) => toast.error(errorMessage(error, "ثبت تنوع انجام نشد")),
  });

  const update = useMutation({
    mutationFn: (input: { id: string; payload: Partial<VariantPayload> }) =>
      api.updateVariant(input.id, {
        ...(input.payload.size !== undefined ? { size: input.payload.size.trim() } : {}),
        ...(input.payload.color !== undefined ? { color: input.payload.color.trim() } : {}),
        ...(input.payload.stock !== undefined ? { stock: input.payload.stock } : {}),
        ...(input.payload.active !== undefined ? { active: input.payload.active } : {}),
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

  const handleCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.size.trim() || !draft.color.trim()) {
      toast.error("سایز و رنگ را وارد کنید");
      return;
    }
    const stock = parseStock(draft.stock);
    if (stock === null) {
      toast.error("موجودی باید یک عدد صحیح و نامنفی باشد");
      return;
    }
    create.mutate({ ...draft, stock });
  };

  const rows = variants.data ?? [];
  const sizesId = `variant-sizes-${product.id}`;
  const colorsId = `variant-colors-${product.id}`;

  return (
    <section className="rounded-3xl border border-border p-5">
      <h3 className="text-sm">
        تنوع‌های سایز × رنگ
        {rows.length > 0 && <span className="text-muted-foreground"> ({toFa(rows.length)})</span>}
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        موجودی هر ترکیب، موجودی محصول را بازنویسی می‌کند؛ ترکیب غیرفعال قابل سفارش نیست.
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

      {variants.isLoading ? (
        <p className="mt-4 text-xs text-muted-foreground">در حال بارگذاری…</p>
      ) : variants.isError ? (
        <p className="mt-4 text-xs text-terracotta">خواندن تنوع‌ها انجام نشد.</p>
      ) : rows.length === 0 ? (
        <p className="mt-4 text-xs text-muted-foreground">
          تنوعی ثبت نشده؛ موجودی کل محصول برای همه ترکیب‌ها اعمال می‌شود.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map((variant) => {
            const row = drafts[variant.id] ?? toDraft(variant);
            const stock = parseStock(row.stock);
            const dirty =
              row.size !== variant.size ||
              row.color !== variant.color ||
              stock !== variant.stock ||
              row.active !== variant.active;
            return (
              <li
                key={variant.id}
                className="grid gap-3 rounded-xl bg-sand p-3 md:grid-cols-[1fr_1fr_110px_auto_auto]"
              >
                <Input
                  aria-label="سایز"
                  list={sizesId}
                  value={row.size}
                  onChange={(e) =>
                    setDrafts({ ...drafts, [variant.id]: { ...row, size: e.target.value } })
                  }
                  className="h-9 bg-background"
                />
                <Input
                  aria-label="رنگ"
                  list={colorsId}
                  value={row.color}
                  onChange={(e) =>
                    setDrafts({ ...drafts, [variant.id]: { ...row, color: e.target.value } })
                  }
                  className="h-9 bg-background"
                />
                <Input
                  aria-label="موجودی"
                  dir="ltr"
                  inputMode="numeric"
                  value={row.stock}
                  onChange={(e) =>
                    setDrafts({ ...drafts, [variant.id]: { ...row, stock: e.target.value } })
                  }
                  className="h-9 bg-background"
                />
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={row.active}
                    onChange={(e) =>
                      setDrafts({ ...drafts, [variant.id]: { ...row, active: e.target.checked } })
                    }
                  />
                  فعال
                </label>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label="ذخیره تنوع"
                    disabled={!dirty || update.isPending}
                    onClick={() => {
                      if (stock === null) {
                        toast.error("موجودی باید یک عدد صحیح و نامنفی باشد");
                        return;
                      }
                      update.mutate({
                        id: variant.id,
                        payload: { size: row.size, color: row.color, stock, active: row.active },
                      });
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
              </li>
            );
          })}
        </ul>
      )}

      <form onSubmit={handleCreate} className="mt-5 border-t border-border pt-5">
        <p className="text-xs text-muted-foreground">افزودن ترکیب</p>
        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_110px_auto_auto]">
          <div>
            <Label className="sr-only">سایز</Label>
            <Input
              aria-label="سایز جدید"
              list={sizesId}
              placeholder="سایز"
              value={draft.size}
              onChange={(e) => setDraft({ ...draft, size: e.target.value })}
              className="h-9 bg-background"
            />
          </div>
          <div>
            <Label className="sr-only">رنگ</Label>
            <Input
              aria-label="رنگ جدید"
              list={colorsId}
              placeholder="رنگ"
              value={draft.color}
              onChange={(e) => setDraft({ ...draft, color: e.target.value })}
              className="h-9 bg-background"
            />
          </div>
          <Input
            aria-label="موجودی جدید"
            dir="ltr"
            inputMode="numeric"
            value={draft.stock}
            onChange={(e) => setDraft({ ...draft, stock: e.target.value })}
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
        </div>
      </form>
    </section>
  );
}
