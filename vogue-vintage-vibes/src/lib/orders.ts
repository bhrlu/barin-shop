export const ORDER_STATUS: Record<string, string> = {
  pending: "در انتظار تأیید",
  processing: "در حال پردازش",
  shipped: "ارسال شده",
  delivered: "تحویل شده",
  cancelled: "لغو شده",
};

export const PAYMENT_STATUS: Record<string, string> = {
  unpaid: "پرداخت نشده",
  paid: "پرداخت شده",
  refunded: "بازگشت داده شده",
};

/** Refund-request states. The backend DDL defaults to `requested`; everything
 * else comes from `PATCH /refunds/{id}` (approved / rejected / refunded).
 * Existing rows keep whatever they store — unknown values fall back to the raw
 * string in the UI. */
export const REFUND_STATUS: Record<string, string> = {
  requested: "ثبت‌شده",
  pending: "در انتظار بررسی",
  approved: "تأییدشده",
  rejected: "ردشده",
  refunded: "بازپرداخت‌شده",
};
