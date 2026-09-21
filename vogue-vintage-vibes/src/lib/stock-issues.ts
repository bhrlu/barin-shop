/**
 * Persian copy for a rejected cart line.
 *
 * `POST /stock/check` and `POST /checkout` share the same closed set of reasons
 * (`StockIssueReason`), so both the cart line note and the checkout toast read
 * from here instead of each keeping its own message map.
 */

import type { Availability, StockIssue, StockIssueReason } from "@/lib/api";
import { toFa } from "@/lib/format";

/** Short forms — toasts, where several issues may be listed at once. */
const SHORT: Record<Exclude<StockIssueReason, "insufficient_stock">, string> = {
  not_found: "دیگر در فروشگاه نیست",
  inactive: "غیرفعال شده است",
  not_available: "فعلاً قابل سفارش نیست",
  size_invalid: "این سایز را ندارد",
};

function remaining(issue: StockIssue): string | null {
  return issue.available && issue.available > 0 ? toFa(issue.available) : null;
}

/** `«کرم — فقط ۳ عدد موجود است»`-style clause for one issue. */
export function stockIssueLabel(issue: StockIssue): string {
  if (issue.reason === "insufficient_stock") {
    const left = remaining(issue);
    return left ? `فقط ${left} عدد موجود است` : "موجودی تمام شده است";
  }
  return SHORT[issue.reason];
}

/**
 * Full sentence shown next to the cart line itself.
 *
 * `not_available` covers both `coming_soon` and `preorder` (the API reports one
 * reason), so the product's own merchandising state — available from the
 * catalog — is what keeps the copy specific.
 */
export function stockIssueMessage(
  issue: StockIssue,
  product?: { availability?: Availability },
): string {
  switch (issue.reason) {
    case "not_found":
      return "این محصول دیگر در فروشگاه نیست؛ آن را از سبد حذف کنید.";
    case "inactive":
      return "این ترکیب سایز و رنگ غیرفعال شده است؛ ترکیب دیگری انتخاب کنید.";
    case "not_available":
      return product?.availability === "preorder"
        ? "این محصول پیش‌فروش است و فعلاً قابل سفارش نیست."
        : "این محصول هنوز عرضه نشده و قابل سفارش نیست.";
    case "size_invalid":
      return "این سایز برای این محصول عرضه نمی‌شود؛ سایز دیگری انتخاب کنید.";
    case "insufficient_stock": {
      const left = remaining(issue);
      return left ? `فقط ${left} عدد از این ترکیب موجود است.` : "موجودی این ترکیب تمام شده است.";
    }
  }
}
