import type { CustomerTier } from "@/lib/api";

/** D7b customer-tier labels — the semantics live server-side
 * (`backend/app/services/tiers.py`); this is display copy only. */
export const TIER_LABELS: Record<CustomerTier, string> = {
  new: "جدید",
  vip: "وفادار",
  wholesale: "همکار",
};
