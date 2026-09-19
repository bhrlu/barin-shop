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
