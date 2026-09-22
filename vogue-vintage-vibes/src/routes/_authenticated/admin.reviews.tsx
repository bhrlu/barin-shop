import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, toPage, type Review } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { formatFaDate, toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Pager } from "@/components/Pager";

export const Route = createFileRoute("/_authenticated/admin/reviews")({
  component: AdminReviews,
});

/** Rows per page for the moderation list (F2.5). */
const PAGE_SIZE = 20;

const FILTERS = [
  { value: "", label: "همه" },
  { value: "published", label: "منتشرشده" },
  { value: "hidden", label: "پنهان" },
] as const;

type Filter = (typeof FILTERS)[number]["value"];

/**
 * Review moderation: publish/hide (`PATCH /reviews/{id}`) and the seller reply,
 * both against `GET /admin/reviews`. Hiding a review changes the product's
 * average, so the catalog and the storefront review list are invalidated too.
 */
function AdminReviews() {
  const queryClient = useQueryClient();
  const { byId } = useCatalog();
  const [filter, setFilter] = useState<Filter>("");
  const [replying, setReplying] = useState<string | null>(null);
  const [reply, setReply] = useState("");

  const [page, setPage] = useState(1);

  const reviews = useQuery({
    queryKey: ["admin-reviews", filter, page],
    queryFn: () =>
      toPage(api.adminReviews(filter === "" ? undefined : filter, page, PAGE_SIZE)),
  });

  const refresh = (review?: Review) => {
    void queryClient.invalidateQueries({ queryKey: ["admin-reviews"] });
    void queryClient.invalidateQueries({ queryKey: ["catalog"] });
    if (review) {
      void queryClient.invalidateQueries({ queryKey: ["product", review.product_id] });
      void queryClient.invalidateQueries({ queryKey: ["product", review.product_id, "reviews"] });
    }
  };

  const moderate = useMutation({
    mutationFn: (input: { id: string; status: "published" | "hidden" }) =>
      api.moderateReview(input.id, input.status),
    onSuccess: (review) => {
      refresh(review);
      toast.success("وضعیت نظر تغییر کرد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "تغییر وضعیت انجام نشد"),
  });

  const replyMutation = useMutation({
    mutationFn: (input: { id: string; text: string }) => api.replyToReview(input.id, input.text),
    onSuccess: (review) => {
      refresh(review);
      setReplying(null);
      setReply("");
      toast.success("پاسخ ثبت شد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "ثبت پاسخ انجام نشد"),
  });

  const list = reviews.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-lg">نظرات {list.length ? `(${toFa(list.length)})` : ""}</h2>
        <div className="flex gap-2">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setFilter(option.value)}
              aria-pressed={filter === option.value}
              className={
                filter === option.value
                  ? "rounded-full border border-terracotta bg-terracotta/10 px-4 py-2 text-xs text-terracotta"
                  : "rounded-full border border-border px-4 py-2 text-xs text-muted-foreground hover:text-foreground"
              }
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {reviews.isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-3xl bg-clay" />
          ))}
        </div>
      ) : reviews.isError ? (
        <p className="text-sm text-terracotta">خواندن نظرات انجام نشد.</p>
      ) : list.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">
          نظری با این وضعیت وجود ندارد.
        </div>
      ) : (
        <ul className="space-y-4">
          {list.map((review) => {
            const product = byId(review.product_id);
            const hidden = review.status !== "published";
            return (
              <li key={review.id} className="rounded-3xl border border-border p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm">
                      {review.author_name ?? "کاربر ساندِه"}{" "}
                      <span className="text-xs text-muted-foreground">
                        · ★ {toFa(review.rating)} از ۵
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {product ? (
                        <Link
                          to="/product/$id"
                          params={{ id: review.product_id }}
                          className="hover:text-terracotta"
                        >
                          {product.name}
                        </Link>
                      ) : (
                        "محصول حذف‌شده"
                      )}{" "}
                      · {formatFaDate(review.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={
                        hidden
                          ? "rounded-full bg-sand px-3 py-1 text-xs text-muted-foreground"
                          : "rounded-full bg-sage/25 px-3 py-1 text-xs text-sage-deep"
                      }
                    >
                      {hidden ? "پنهان" : "منتشرشده"}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-none"
                      disabled={moderate.isPending}
                      onClick={() =>
                        moderate.mutate({
                          id: review.id,
                          status: hidden ? "published" : "hidden",
                        })
                      }
                    >
                      {hidden ? "انتشار" : "پنهان کردن"}
                    </Button>
                  </div>
                </div>

                {review.title && <p className="mt-3 font-display text-lg">{review.title}</p>}
                {review.body && (
                  <p className="mt-2 text-sm leading-7 text-muted-foreground">{review.body}</p>
                )}

                {review.seller_reply && replying !== review.id && (
                  <div className="mt-4 border-r-2 border-terracotta/40 bg-sand/60 px-4 py-3">
                    <p className="text-[11px] tracking-[0.16em] text-sage-deep">پاسخ فروشگاه</p>
                    <p className="mt-1 text-sm leading-7 text-muted-foreground">
                      {review.seller_reply}
                    </p>
                  </div>
                )}

                {replying === review.id ? (
                  <form
                    className="mt-4 space-y-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const text = reply.trim();
                      if (!text) {
                        toast.error("متن پاسخ را بنویسید");
                        return;
                      }
                      replyMutation.mutate({ id: review.id, text });
                    }}
                  >
                    <Textarea
                      rows={3}
                      maxLength={2000}
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                      placeholder="پاسخ فروشگاه…"
                      aria-label="پاسخ فروشگاه"
                      className="bg-sand"
                    />
                    <div className="flex gap-2">
                      <Button
                        type="submit"
                        size="sm"
                        className="rounded-none"
                        disabled={replyMutation.isPending}
                      >
                        ثبت پاسخ
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="rounded-none"
                        onClick={() => {
                          setReplying(null);
                          setReply("");
                        }}
                      >
                        انصراف
                      </Button>
                    </div>
                  </form>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setReplying(review.id);
                      setReply(review.seller_reply ?? "");
                    }}
                    className="mt-3 text-xs text-terracotta hover:underline"
                  >
                    {review.seller_reply ? "ویرایش پاسخ فروشگاه" : "نوشتن پاسخ فروشگاه"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {list.length > 0 && (
        <Pager
          className="mt-6"
          page={reviews.data?.page ?? page}
          pages={reviews.data?.pages ?? 1}
          total={reviews.data?.total}
          onChange={setPage}
        />
      )}
    </div>
  );
}
