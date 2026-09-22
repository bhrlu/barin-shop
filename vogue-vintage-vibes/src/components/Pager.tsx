import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

function faDigits(n: number): string {
  return n.toLocaleString("fa-IR");
}

/** Shared pagination control (F2.5). Renders nothing when there is a single
 * page. RTL: «قبلی» advances to the right visually (lower page), matching the
 * reading direction used elsewhere in the shop. */
export function Pager({
  page,
  pages,
  total,
  onChange,
  className = "",
}: {
  page: number;
  pages: number;
  total?: number | undefined;
  onChange: (page: number) => void;
  className?: string;
}) {
  if (pages <= 1) return null;

  const window = 2; // pages shown on each side of the current one
  const numbers: number[] = [];
  const from = Math.max(1, page - window);
  const to = Math.min(pages, page + window);
  for (let i = from; i <= to; i++) numbers.push(i);

  const btn =
    "h-9 min-w-9 px-2 rounded-lg border text-sm font-medium transition-colors select-none";

  return (
    <nav
      className={`flex flex-wrap items-center justify-center gap-2 ${className}`}
      aria-label="صفحه‌بندی"
    >
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className={`${btn} ${page <= 1 ? "opacity-40 cursor-not-allowed" : "hover:bg-secondary"}`}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
      {from > 1 && (
        <>
          <button type="button" onClick={() => onChange(1)} className={`${btn} hover:bg-secondary`}>
            {faDigits(1)}
          </button>
          {from > 2 && <span className="text-sm text-muted-foreground px-1">…</span>}
        </>
      )}
      {numbers.map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          aria-current={n === page ? "page" : undefined}
          className={`${btn} ${
            n === page ? "bg-terracotta text-white border-terracotta" : "hover:bg-secondary"
          }`}
        >
          {faDigits(n)}
        </button>
      ))}
      {to < pages && (
        <>
          {to < pages - 1 && <span className="text-sm text-muted-foreground px-1">…</span>}
          <button
            type="button"
            onClick={() => onChange(pages)}
            className={`${btn} hover:bg-secondary`}
          >
            {faDigits(pages)}
          </button>
        </>
      )}
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
        className={`${btn} ${
          page >= pages ? "opacity-40 cursor-not-allowed" : "hover:bg-secondary"
        }`}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {total != null && (
        <span className="text-sm text-muted-foreground mr-2">{faDigits(total)} مورد</span>
      )}
    </nav>
  );
}
