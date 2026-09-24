import { api, type Product as ApiProduct } from "@/lib/api";

/**
 * Guest «recently viewed» (F3.4b, decision D7(c)): guests build a small local
 * history in `localStorage`; when they sign in it merges deterministically with
 * the per-customer `recently_viewed` table, which stays authoritative.
 *
 * Contract (D7(c)): maximum 8 entries · dedupe by product id · newest view wins
 * · server history is authoritative after the merge · no new backend endpoint
 * (the merge replays the existing `POST /products/{id}/view`).
 */

const STORAGE_KEY = "sande.recently-viewed";
export const RECENTLY_VIEWED_LIMIT = 8;

export type RecentlyViewedEntry = {
  /** Stored product id; entries the catalogue no longer knows are dropped. */
  id: string;
  /** Epoch milliseconds of the most recent view; newest wins. */
  viewedAt: number;
};

/** Read the guest history; anything unparsable or stale-shaped resets it. */
export function readGuestHistory(): RecentlyViewedEntry[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (entry): entry is RecentlyViewedEntry =>
          typeof entry === "object" &&
          entry !== null &&
          typeof (entry as RecentlyViewedEntry).id === "string" &&
          typeof (entry as RecentlyViewedEntry).viewedAt === "number" &&
          Number.isFinite((entry as RecentlyViewedEntry).viewedAt),
      )
      .sort((a, b) => b.viewedAt - a.viewedAt)
      .slice(0, RECENTLY_VIEWED_LIMIT);
  } catch {
    return [];
  }
}

function writeGuestHistory(entries: RecentlyViewedEntry[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // private mode / quota: the guest history is best-effort by definition
  }
}

/** Record one guest view: dedupe by id, newest wins, capped at 8 (D7(c)). */
export function recordGuestView(productId: string): void {
  const entry: RecentlyViewedEntry = { id: productId, viewedAt: Date.now() };
  const next = [entry, ...readGuestHistory().filter((e) => e.id !== productId)].slice(
    0,
    RECENTLY_VIEWED_LIMIT,
  );
  writeGuestHistory(next);
}

/**
 * Deterministic merge for sign-in (D7(c)): up to 8 most recent guest ids are
 * replayed through the canonical `POST /products/{id}/view` (oldest first, so
 * the newest guest view is written last and wins in the server table too).
 * Unknown product ids 404 and are dropped silently. The server history then is
 * authoritative; the local guest list is cleared either way.
 */
export async function mergeGuestHistoryOnSignIn(): Promise<void> {
  const guest = readGuestHistory();
  if (guest.length === 0) return;
  for (const entry of [...guest].reverse()) {
    await api.recordProductView(entry.id).catch(() => {});
  }
  writeGuestHistory([]);
}

/** Resolve the guest ids to rail products through the catalogue (guests only;
 * exported for the rail's query — the hook lives with its consumer). */
export async function guestHistoryProducts(limit: number): Promise<ApiProduct[]> {
  const all = (await api.products()) as ApiProduct[];
  const byId = new Map(all.map((product) => [product.id, product]));
  return readGuestHistory()
    .map((entry) => byId.get(entry.id))
    .filter((product): product is ApiProduct => product !== undefined)
    .slice(0, limit);
}
