import { useState, type FormEvent } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Star, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, type Review } from "@/lib/api";
import { reviewsQuery } from "@/lib/catalog";
import { useAuth } from "@/lib/auth";
import { formatFaDate, toFa } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const STARS = [5, 4, 3, 2, 1];

function Stars({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("flex items-center gap-0.5", className)} aria-hidden="true">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={cn(
            "size-3.5",
            n <= Math.round(value) ? "fill-gold text-gold" : "text-muted-foreground/30",
          )}
        />
      ))}
    </span>
  );
}

type Draft = { rating: number; title: string; body: string };

function ReviewCard({ review }: { review: Review }) {
  return (
    <li className="border-b border-border/70 py-6 last:border-0">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm">{review.author_name ?? "کاربر ساندِه"}</p>
          <div className="mt-1 flex items-center gap-3">
            <Stars value={review.rating} />
            <span
              className="text-xs text-muted-foreground"
              aria-label={`${toFa(review.rating)} از ۵`}
            >
              {toFa(review.rating)} از ۵
            </span>
          </div>
        </div>
        <time className="shrink-0 text-xs text-muted-foreground">
          {formatFaDate(review.created_at)}
        </time>
      </div>

      {review.title && <p className="mt-3 font-display text-lg">{review.title}</p>}
      {review.body && <p className="mt-2 text-sm leading-7 text-muted-foreground">{review.body}</p>}

      {review.seller_reply && (
        <div className="mt-4 border-r-2 border-terracotta/40 bg-sand/60 px-4 py-3">
          <p className="text-[11px] tracking-[0.16em] text-sage-deep">پاسخ فروشگاه</p>
          <p className="mt-1 text-sm leading-7 text-muted-foreground">{review.seller_reply}</p>
        </div>
      )}
    </li>
  );
}

/**
 * Rating summary (average + distribution), the published review list, and a
 * write/edit form wired to `GET/POST /products/{id}/reviews`. The backend keeps
 * one review per customer per product (`ON CONFLICT … DO UPDATE`), so the form
 * pre-fills the signed-in customer's existing review.
 */
export function ReviewsSection({
  productId,
  fallbackAverage,
  fallbackCount,
}: {
  productId: string;
  fallbackAverage: number | null;
  fallbackCount: number;
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const reviews = useQuery(reviewsQuery(productId));
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);

  const list = reviews.data?.reviews ?? [];
  const average = reviews.data?.average ?? fallbackAverage;
  const count = reviews.data?.count ?? fallbackCount;
  const distribution = reviews.data?.distribution ?? {};
  const mine = user ? list.find((review) => review.user_id === user.id) : undefined;

  // untitled state falls back to the customer's own review, then to an empty form
  const form: Draft =
    draft ??
    (mine
      ? { rating: mine.rating, title: mine.title, body: mine.body }
      : { rating: 0, title: "", body: "" });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["product", productId, "reviews"] });
    void queryClient.invalidateQueries({ queryKey: ["product", productId] });
    void queryClient.invalidateQueries({ queryKey: ["catalog"] });
  };

  const submit = useMutation({
    mutationFn: (payload: Draft) => api.createReview(productId, payload),
    onSuccess: () => {
      toast.success("نظر شما ثبت شد");
      setOpen(false);
      setDraft(null);
      refresh();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "ثبت نظر انجام نشد"),
  });

  const remove = useMutation({
    mutationFn: (reviewId: string) => api.deleteReview(reviewId),
    onSuccess: () => {
      toast.success("نظر شما حذف شد");
      setOpen(false);
      setDraft(null);
      refresh();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "حذف نظر انجام نشد"),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (form.rating < 1) {
      toast.error("ابتدا امتیاز را انتخاب کنید");
      return;
    }
    submit.mutate({ rating: form.rating, title: form.title.trim(), body: form.body.trim() });
  };

  return (
    <section className="mt-20">
      <h2 className="text-2xl">نظرات و امتیازها</h2>

      <div className="mt-6 grid gap-10 md:grid-cols-[300px_1fr]">
        <div>
          <div className="rounded-[1.25rem] bg-sand p-6">
            {count > 0 && average != null ? (
              <>
                <p className="flex items-baseline gap-2">
                  <span className="font-display text-4xl">{toFa(average.toFixed(1))}</span>
                  <span className="text-xs text-muted-foreground">از ۵</span>
                </p>
                <Stars value={average} className="mt-2" />
                <p className="mt-2 text-xs text-muted-foreground">از {toFa(count)} نظر ثبت‌شده</p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                هنوز امتیازی ثبت نشده؛ اولین نفر باشید.
              </p>
            )}

            {count > 0 && (
              <ul className="mt-5 space-y-2">
                {STARS.map((star) => {
                  const value = distribution[String(star)] ?? 0;
                  const percent = count ? Math.round((value / count) * 100) : 0;
                  return (
                    <li key={star} className="flex items-center gap-3 text-xs">
                      <span className="w-10 shrink-0 text-muted-foreground">
                        {toFa(star)} ستاره
                      </span>
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-clay">
                        <span
                          className="block h-full rounded-full bg-terracotta"
                          style={{ width: `${percent}%` }}
                        />
                      </span>
                      <span className="w-6 shrink-0 text-muted-foreground">{toFa(value)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="mt-6">
            {!user ? (
              <p className="text-sm text-muted-foreground">
                برای ثبت نظر{" "}
                <Link
                  to="/auth"
                  search={{ redirect: `/product/${productId}` }}
                  className="text-terracotta hover:underline"
                >
                  وارد حساب کاربری
                </Link>{" "}
                شوید.
              </p>
            ) : !open ? (
              <Button
                type="button"
                variant="outline"
                className="w-full rounded-none"
                onClick={() => setOpen(true)}
              >
                {mine ? "ویرایش نظر شما" : "نوشتن نظر"}
              </Button>
            ) : (
              <form
                onSubmit={handleSubmit}
                className="space-y-4 rounded-[1.25rem] border border-border p-5"
              >
                <div>
                  <p className="text-xs tracking-[0.2em] text-muted-foreground">امتیاز شما</p>
                  <div className="mt-2 flex items-center gap-1">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        aria-label={`${toFa(n)} ستاره`}
                        aria-pressed={form.rating === n}
                        onClick={() => setDraft({ ...form, rating: n })}
                        className="p-1"
                      >
                        <Star
                          className={cn(
                            "size-6 transition-colors",
                            n <= form.rating ? "fill-gold text-gold" : "text-muted-foreground/40",
                          )}
                        />
                      </button>
                    ))}
                  </div>
                </div>

                <Input
                  value={form.title}
                  maxLength={120}
                  onChange={(event) => setDraft({ ...form, title: event.target.value })}
                  placeholder="عنوان نظر (اختیاری)"
                  aria-label="عنوان نظر"
                  className="bg-sand"
                />
                <Textarea
                  value={form.body}
                  maxLength={2000}
                  rows={4}
                  onChange={(event) => setDraft({ ...form, body: event.target.value })}
                  placeholder="تجربه‌تان از جنس، اندازه و کیفیت این محصول…"
                  aria-label="متن نظر"
                  className="bg-sand"
                />

                <div className="flex flex-wrap gap-3">
                  <Button type="submit" className="rounded-none" disabled={submit.isPending}>
                    {mine ? "ذخیره‌ی ویرایش" : "ثبت نظر"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="rounded-none"
                    onClick={() => {
                      setOpen(false);
                      setDraft(null);
                    }}
                  >
                    انصراف
                  </Button>
                  {mine && (
                    <Button
                      type="button"
                      variant="ghost"
                      className="rounded-none text-destructive"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(mine.id)}
                    >
                      <Trash2 className="size-4" />
                      حذف نظر
                    </Button>
                  )}
                </div>
              </form>
            )}
          </div>
        </div>

        <div>
          {reviews.isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 2 }).map((_, index) => (
                <div key={index} className="h-24 animate-pulse rounded-[1.25rem] bg-clay" />
              ))}
            </div>
          ) : reviews.isError ? (
            <p className="text-sm text-muted-foreground">خواندن نظرات انجام نشد.</p>
          ) : list.length === 0 ? (
            <p className="text-sm text-muted-foreground">هنوز نظری برای این محصول ثبت نشده است.</p>
          ) : (
            <ul>
              {list.map((review) => (
                <ReviewCard key={review.id} review={review} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
