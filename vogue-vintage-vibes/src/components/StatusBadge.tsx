import { ORDER_STATUS, PAYMENT_STATUS, REFUND_STATUS } from "@/lib/orders";
import { cn } from "@/lib/utils";

/** Token recipes per DESIGN_SYSTEM §2.3 — no raw palette classes. */
const TONES = {
  positive: "border-sage/40 bg-sage/20 text-sage-deep",
  progress: "border-gold/50 bg-gold/15 text-foreground",
  waiting: "border-border bg-sand text-foreground",
  negative: "border-destructive/30 bg-destructive/10 text-destructive",
  meta: "border-terracotta/30 bg-terracotta/10 text-terracotta",
} as const;

/** status → tone, per the §2.3 semantics table. Unknown values render as
 * «meta» (brand) — the raw string always shows through the label. */
const STATUS_TONE: Record<string, keyof typeof TONES> = {
  delivered: "positive",
  paid: "positive",
  approved: "positive",
  refunded: "positive",
  succeeded: "positive",
  processing: "progress",
  shipped: "progress",
  pending: "waiting",
  unpaid: "waiting",
  new: "waiting",
  cancelled: "negative",
  rejected: "negative",
  failed: "negative",
};

const LABELS: Record<string, string> = {
  ...ORDER_STATUS,
  ...PAYMENT_STATUS,
  ...REFUND_STATUS,
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const tone = TONES[STATUS_TONE[status] ?? "meta"];
  const label = LABELS[status] ?? status;
  return (
    <span
      title={status}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        tone,
        className,
      )}
    >
      {label}
    </span>
  );
}
