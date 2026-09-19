import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { toProducts } from "@/lib/catalog";
import { categoryTitle } from "@/data/products";
import { useCompare } from "@/lib/compare";
import { formatToman, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export const Route = createFileRoute("/compare")({
  head: () => ({
    meta: [
      { title: "مقایسه محصولات — ساندِه" },
      {
        name: "description",
        content: "محصولات انتخابی ساندِه را از نظر قیمت، جنس، رنگ، سایز و موجودی مقایسه کنید.",
      },
      { property: "og:title", content: "مقایسه محصولات — ساندِه" },
      { property: "og:description", content: "مقایسه ویژگی‌های محصولات ساندِه در یک نگاه." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ComparePage,
});

function ComparePage() {
  const { ids, remove, clear } = useCompare();
  const compare = useQuery({
    queryKey: ["compare", ids],
    queryFn: async () => toProducts(await api.compareProducts(ids)),
    enabled: ids.length > 0,
  });
  const products = compare.data ?? [];

  if (ids.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center sm:px-6">
        <h1 className="text-3xl">مقایسه محصولات</h1>
        <p className="mt-4 text-sm text-muted-foreground">
          هنوز محصولی برای مقایسه انتخاب نکرده‌اید. روی آیکون مقایسه در کارت هر محصول بزنید (حداکثر
          ۴ محصول).
        </p>
        <Button className="mt-8 rounded-none" asChild>
          <Link to="/shop" search={{}}>
            رفتن به فروشگاه
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl">مقایسه محصولات</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {toFa(products.length)} محصول انتخاب شده است.
          </p>
        </div>
        <Button type="button" variant="ghost" className="rounded-none" onClick={clear}>
          پاک کردن مقایسه
        </Button>
      </div>

      {compare.isLoading ? (
        <div className="mt-10 space-y-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-10 animate-pulse rounded bg-clay" />
          ))}
        </div>
      ) : compare.isError ? (
        <div className="mt-10 border border-dashed border-border p-12 text-center">
          <p className="text-muted-foreground">خواندن محصولات انجام نشد. دوباره تلاش کنید.</p>
        </div>
      ) : (
        <div className="mt-10 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-32 text-right">ویژگی</TableHead>
                {products.map((product) => (
                  <TableHead key={product.id} className="min-w-56 text-right align-top">
                    <div className="space-y-3 py-2">
                      <img
                        src={product.images[0]}
                        alt={product.name}
                        width={900}
                        height={1100}
                        className="h-40 w-full rounded-[1.25rem] object-cover"
                      />
                      <Link
                        to="/product/$id"
                        params={{ id: product.id }}
                        className="block font-display text-lg leading-6 hover:text-terracotta"
                      >
                        {product.name}
                      </Link>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-muted-foreground"
                        onClick={() => remove(product.id)}
                      >
                        <X className="size-3.5" />
                        حذف
                      </Button>
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">دسته</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>{categoryTitle(product.category)}</TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">قیمت</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>
                    <span className="text-terracotta">{formatToman(product.price)} تومان</span>
                    {product.oldPrice && (
                      <span className="mr-2 text-xs text-muted-foreground line-through">
                        {formatToman(product.oldPrice)}
                      </span>
                    )}
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">امتیاز</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>
                    {product.avgRating != null && (product.reviewCount ?? 0) > 0
                      ? `${toFa(product.avgRating.toFixed(1))} از ۵ (${toFa(product.reviewCount ?? 0)} نظر)`
                      : "بدون امتیاز"}
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">جنس</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id} className="text-sm text-muted-foreground">
                    {product.material}
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">سایزها</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>{product.sizes.map(toFa).join(" · ")}</TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">رنگ‌ها</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>
                    <span className="flex flex-wrap items-center gap-2">
                      {product.colors.map((color) => (
                        <span key={color.name} className="flex items-center gap-1 text-xs">
                          <span
                            className="size-3.5 rounded-full border border-border"
                            style={{ backgroundColor: color.hex }}
                          />
                          {color.name}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">برچسب‌ها</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>
                    <span className="flex flex-wrap gap-1">
                      {(product.tags ?? []).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground">وضعیت</TableCell>
                {products.map((product) => (
                  <TableCell key={product.id}>
                    {product.availability === "coming_soon"
                      ? "به‌زودی"
                      : product.availability === "preorder"
                        ? "پیش‌خرید"
                        : product.stock > 0
                          ? `${toFa(product.stock)} عدد در انبار`
                          : "ناموجود"}
                  </TableCell>
                ))}
              </TableRow>
              <TableRow>
                <TableCell className="text-xs text-muted-foreground" />
                {products.map((product) => (
                  <TableCell key={product.id}>
                    {product.availability === "in_stock" && product.stock > 0 ? (
                      <Button variant="outline" size="sm" className="rounded-none" asChild>
                        <Link to="/product/$id" params={{ id: product.id }}>
                          مشاهده و افزودن به سبد
                        </Link>
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">فعلاً قابل سفارش نیست</span>
                    )}
                  </TableCell>
                ))}
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
