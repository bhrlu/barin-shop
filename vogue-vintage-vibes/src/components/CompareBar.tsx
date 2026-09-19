import { Link } from "@tanstack/react-router";
import { GitCompareArrows } from "lucide-react";
import { useCompare } from "@/lib/compare";
import { toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";

/** Sticky footer bar with the comparison basket; hidden while it is empty. */
export function CompareBar() {
  const { count, clear } = useCompare();
  if (count === 0) return null;

  return (
    <div className="sticky bottom-0 z-40 border-t border-terracotta/30 bg-background/92 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <p className="flex items-center gap-2 text-sm">
          <GitCompareArrows className="size-4 text-terracotta" />
          {toFa(count)} محصول برای مقایسه انتخاب شده
        </p>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={clear}>
            پاک کردن
          </Button>
          <Button asChild size="sm" className="rounded-none">
            <Link to="/compare">مقایسه</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
