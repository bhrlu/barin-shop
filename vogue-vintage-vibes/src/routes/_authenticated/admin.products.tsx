import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useCatalog, type AdminProduct } from "@/lib/catalog";
import { categories, categoryTitle } from "@/data/products";
import { formatToman, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ProductImageManager } from "@/components/admin/ProductImageManager";

export const Route = createFileRoute("/_authenticated/admin/products")({
  component: AdminProducts,
});

type FormState = {
  id?: string;
  name: string;
  category: string;
  price: string;
  old_price: string;
  sizes: string;
  colors: string;
  images: string[];
  material: string;
  description: string;
  stock: string;
  is_new: boolean;
  active: boolean;
};

const emptyForm: FormState = {
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
};

function toForm(product: AdminProduct & { rawImages?: string[] }): FormState {
  return {
    id: product.id,
    name: product.name,
    category: product.category,
    price: String(product.price),
    old_price: product.oldPrice ? String(product.oldPrice) : "",
    sizes: product.sizes.join(", "),
    colors: product.colors.map((c) => `${c.name} ${c.hex}`).join(", "),
    images: product.rawImages ?? [],
    material: product.material,
    description: product.description,
    stock: String(product.stock),
    is_new: product.isNew ?? true,
    active: product.active ?? true,
  };
}

function parsePayload(form: FormState) {
  return {
    name: form.name,
    category: form.category,
    price: Number(form.price),
    old_price: form.old_price ? Number(form.old_price) : null,
    sizes: form.sizes.split(",").map((s) => s.trim()).filter(Boolean),
    colors: form.colors
      .split(",")
      .map((chunk) => chunk.trim())
      .filter(Boolean)
      .map((chunk) => {
        const parts = chunk.split(/\s+/);
        const hex = parts.pop() ?? "#cccccc";
        return { name: parts.join(" ") || "رنگ", hex };
      }),
    images: form.images,
    material: form.material,
    description: form.description,
    stock: Number(form.stock),
    is_new: form.is_new,
    active: form.active,
  };
}

function AdminProducts() {
  const { all, isLoading } = useCatalog();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["catalog"] });

  const save = useMutation({
    mutationFn: async (state: FormState) => {
      const payload = parsePayload(state);
      if (state.id) {
        const { error } = await supabase.from("products").update(payload as never).eq("id", state.id);
        if (error) throw error;
      } else {
        const { error } = await supabase.from("products").insert({ ...payload, id: crypto.randomUUID() });
        if (error) throw error;
      }
    },
    onSuccess: () => {
      invalidate();
      setForm(null);
      toast.success("محصول ذخیره شد");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "ذخیره نشد"),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("products").delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => {
      invalidate();
      toast.success("محصول حذف شد");
    },
    onError: () => toast.error("حذف انجام نشد (ممکن است در سفارش‌ها استفاده شده باشد)"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg">فهرست محصولات {all.length ? `(${toFa(all.length)})` : ""}</h2>
        <Button onClick={() => setForm(emptyForm)} className="gap-2">
          <Plus className="size-4" /> محصول جدید
        </Button>
      </div>

      {form && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(form);
          }}
          className="grid gap-4 rounded-3xl bg-sand p-6 md:grid-cols-2"
        >
          <div className="md:col-span-2 flex items-center justify-between">
            <h3 className="text-lg">{form.id ? "ویرایش محصول" : "افزودن محصول"}</h3>
            <button type="button" onClick={() => setForm(null)} className="text-xs text-muted-foreground">
              بستن
            </button>
          </div>
          <div>
            <Label>نام</Label>
            <Input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>دسته‌بندی</Label>
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="mt-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>قیمت (تومان)</Label>
            <Input
              required
              dir="ltr"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>قیمت قبل از تخفیف</Label>
            <Input
              dir="ltr"
              value={form.old_price}
              onChange={(e) => setForm({ ...form, old_price: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>سایزها (با کاما)</Label>
            <Input
              value={form.sizes}
              onChange={(e) => setForm({ ...form, sizes: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div>
            <Label>موجودی</Label>
            <Input
              dir="ltr"
              value={form.stock}
              onChange={(e) => setForm({ ...form, stock: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>رنگ‌ها (نام و کد رنگ، جدا شده با کاما)</Label>
            <Input
              value={form.colors}
              onChange={(e) => setForm({ ...form, colors: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>گالری تصاویر</Label>
            <div className="mt-3">
              <ProductImageManager
                value={form.images}
                onChange={(images) => setForm({ ...form, images })}
              />
            </div>
          </div>
          <div className="md:col-span-2">
            <Label>جنس</Label>
            <Input
              value={form.material}
              onChange={(e) => setForm({ ...form, material: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="md:col-span-2">
            <Label>توضیحات</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="mt-2 bg-background"
            />
          </div>
          <div className="flex items-center gap-6 md:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_new}
                onChange={(e) => setForm({ ...form, is_new: e.target.checked })}
              />
              محصول جدید
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm({ ...form, active: e.target.checked })}
              />
              نمایش در فروشگاه
            </label>
          </div>
          <Button type="submit" disabled={save.isPending} className="md:col-span-2">
            ذخیره محصول
          </Button>
        </form>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">در حال بارگذاری…</p>
      ) : (
        <ul className="divide-y divide-border rounded-3xl border border-border">
          {all.map((product) => (
            <li key={product.id} className="flex flex-wrap items-center gap-4 p-4 text-sm">
              <img src={product.images[0]} alt="" className="size-14 rounded-xl object-cover" />
              <div className="flex-1">
                <p>{product.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {categoryTitle(product.category)} · موجودی {toFa(product.stock)}
                  {!product.active && " · غیرفعال"}
                </p>
              </div>
              <span>{formatToman(product.price)} تومان</span>
              <button
                type="button"
                onClick={() => setForm(toForm(product))}
                aria-label="ویرایش"
                className="text-muted-foreground hover:text-terracotta"
              >
                <Pencil className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => remove.mutate(product.id)}
                aria-label="حذف"
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}