import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, type ProductWrite } from "@/lib/api";
import type { AdminProduct } from "@/lib/catalog";
import { categories } from "@/data/products";
import {
  AVAILABILITIES,
  BADGES,
  emptyProductForm,
  productSchema,
  productToForm,
  type ProductFormValues,
} from "@/lib/product-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { ProductImageManager } from "@/components/admin/ProductImageManager";
import { VariantEditor } from "@/components/admin/VariantEditor";

const selectClass = "h-9 w-full rounded-md border border-input bg-background px-3 text-sm";

/**
 * Product create/edit (AB-FE-03, spec [FE-04]): React Hook Form + the Zod schema in
 * `lib/product-form.ts`, two columns from `md` up (wide: what the product is; narrow:
 * price, stock, availability, visibility), stacked below. Editing an existing product
 * also shows its size × colour matrix. The request payload is unchanged.
 */
export function ProductEditor({
  product,
  onClose,
}: {
  /** `null` = a new product */
  product: AdminProduct | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [imagesBusy, setImagesBusy] = useState(false);
  const form = useForm<ProductFormValues, unknown, ProductWrite>({
    resolver: zodResolver(productSchema),
    defaultValues: product ? productToForm(product) : emptyProductForm,
    // errors appear on submit, then follow each edit. Not on blur: a message appearing
    // as a field loses focus moves «ذخیره محصول» away from the pointer mid-click.
    reValidateMode: "onChange",
  });
  const availability = form.watch("availability");

  const save = useMutation({
    mutationFn: async (payload: ProductWrite) => {
      if (product) await api.updateProduct(product.id, payload);
      else await api.createProduct(payload);
    },
    onSuccess: () => {
      // the admin list and the storefront catalogue both show these rows
      void queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      toast.success("محصول ذخیره شد");
      onClose();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "ذخیره نشد"),
  });

  const text = (
    name: "name" | "material" | "sizes" | "colors" | "tags",
    label: string,
    options: { placeholder?: string; description?: string } = {},
  ) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input {...field} placeholder={options.placeholder} className="bg-background" />
          </FormControl>
          {options.description ? <FormDescription>{options.description}</FormDescription> : null}
          <FormMessage />
        </FormItem>
      )}
    />
  );

  const amount = (
    name: "price" | "old_price" | "stock" | "low_stock_threshold",
    label: string,
    description?: string,
  ) => (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input {...field} dir="ltr" inputMode="numeric" className="bg-background" />
          </FormControl>
          {description ? <FormDescription>{description}</FormDescription> : null}
          <FormMessage />
        </FormItem>
      )}
    />
  );

  return (
    <section className="space-y-6 rounded-3xl bg-sand p-6">
      <Form {...form}>
        <form
          noValidate
          aria-label={product ? "ویرایش محصول" : "افزودن محصول"}
          onSubmit={form.handleSubmit((payload) => save.mutate(payload))}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg">{product ? "ویرایش محصول" : "افزودن محصول"}</h3>
            <button type="button" onClick={onClose} className="text-xs text-muted-foreground">
              بستن
            </button>
          </div>

          <div className="mt-5 grid gap-6 md:grid-cols-[minmax(0,1fr)_300px]">
            {/* wide column: what the product is */}
            <div className="min-w-0 space-y-4">
              {text("name", "نام")}
              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>دسته‌بندی</FormLabel>
                    <FormControl>
                      <select {...field} className={selectClass}>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>توضیحات</FormLabel>
                    <FormControl>
                      <Textarea {...field} rows={5} className="bg-background" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {text("material", "جنس")}
              <div className="grid gap-4 sm:grid-cols-2">
                {text("sizes", "سایزها", { description: "با کاما جدا کنید: S, M, L" })}
                {text("tags", "برچسب‌ها", { placeholder: "کتان, تابستانی" })}
              </div>
              {text("colors", "رنگ‌ها", {
                description: "نام و کد رنگ، جدا شده با کاما: کرم #f0ebe3, زغالی #3a352f",
              })}
              <FormField
                control={form.control}
                name="images"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>گالری تصاویر</FormLabel>
                    <ProductImageManager
                      value={field.value}
                      onChange={field.onChange}
                      onBusyChange={setImagesBusy}
                    />
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* narrow column: price, stock, availability, visibility */}
            <aside className="space-y-4 md:border-r md:border-border/70 md:pr-6">
              {amount("price", "قیمت (تومان)")}
              {amount("old_price", "قیمت قبل از تخفیف", "خالی = بدون تخفیف")}
              {amount("stock", "موجودی")}
              {amount("low_stock_threshold", "آستانه هشدار موجودی کم")}
              <FormField
                control={form.control}
                name="availability"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>وضعیت عرضه</FormLabel>
                    <FormControl>
                      <select {...field} className={selectClass}>
                        {AVAILABILITIES.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="available_at"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>تاریخ عرضه (برای به‌زودی / پیش‌خرید)</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="date"
                        dir="ltr"
                        disabled={availability === "in_stock"}
                        className="bg-background disabled:opacity-50"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="badge"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>نشان محصول</FormLabel>
                    <FormControl>
                      <select {...field} className={selectClass}>
                        {BADGES.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {(
                [
                  ["active", "نمایش در فروشگاه"],
                  ["is_new", "محصول جدید"],
                ] as const
              ).map(([name, label]) => (
                <FormField
                  key={name}
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between gap-3 space-y-0">
                      <FormLabel className="font-normal">{label}</FormLabel>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              ))}
              <Button type="submit" disabled={save.isPending || imagesBusy} className="w-full">
                {imagesBusy ? "در انتظار پایان آپلود تصاویر…" : "ذخیره محصول"}
              </Button>
            </aside>
          </div>
        </form>
      </Form>

      {product ? (
        <VariantEditor product={product} />
      ) : (
        <p className="text-xs text-muted-foreground">
          تنوع‌های سایز × رنگ (موجودی، SKU و قیمت اختصاصی) پس از ذخیرهٔ محصول تعریف می‌شوند.
        </p>
      )}
    </section>
  );
}
