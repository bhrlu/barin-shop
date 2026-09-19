import { useNavigate } from "@tanstack/react-router";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Search, Tag, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { toast } from "sonner";
import { api, type SearchHistoryEntry, type SearchSuggestion } from "@/lib/api";
import { resolveImageMap } from "@/lib/catalog";
import { useAuth } from "@/lib/auth";
import { categories, type CategoryId } from "@/data/products";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type Row =
  | { type: "submit"; key: string }
  | { type: "suggestion"; key: string; suggestion: SearchSuggestion }
  | { type: "history"; key: string; entry: SearchHistoryEntry };

const KIND_HINTS: Record<SearchSuggestion["kind"], string> = {
  query: "جستجوی پیشین",
  category: "دسته‌بندی",
  tag: "برچسب",
  product: "محصول",
};

/**
 * Header search: debounced `GET /search/suggest` dropdown with product images,
 * categories, tags and the signed-in customer's recent queries (deletable).
 * Submitting goes to `/shop?q=…`, which runs the full `GET /search`.
 */
export function HeaderSearch() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [debounced, setDebounced] = useState("");
  const [active, setActive] = useState(-1);

  // debounce the input so /search/suggest is not hit on every keystroke
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value.trim()), 250);
    return () => window.clearTimeout(id);
  }, [value]);

  const suggesting = debounced.length > 0;

  const suggestions = useQuery({
    queryKey: ["search", "suggest", debounced],
    queryFn: async () => {
      const items = await api.searchSuggest(debounced);
      const images = await resolveImageMap(items.map((item) => item.image));
      return items.map((item) => ({
        ...item,
        image: item.image ? (images.get(item.image) ?? null) : null,
      }));
    },
    enabled: open && suggesting,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const history = useQuery({
    queryKey: ["search", "history"],
    queryFn: () => api.searchHistory(8),
    enabled: open && Boolean(user) && !suggesting,
    staleTime: 30_000,
  });

  const refreshHistory = () => queryClient.invalidateQueries({ queryKey: ["search", "history"] });

  const clearHistory = useMutation({
    mutationFn: () => api.clearSearchHistory(),
    onSuccess: () => void refreshHistory(),
    onError: () => toast.error("پاک کردن تاریخچه انجام نشد"),
  });

  const removeHistory = useMutation({
    mutationFn: (id: string) => api.deleteSearchHistory(id),
    onSuccess: () => void refreshHistory(),
    onError: () => toast.error("حذف مورد انجام نشد"),
  });

  const close = () => setOpen(false);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      setValue("");
      setActive(-1);
    }
  };

  const submit = (raw: string) => {
    const q = raw.trim();
    if (!q) return;
    close();
    void navigate({ to: "/shop", search: { q } });
  };

  const pick = (item: SearchSuggestion) => {
    if (item.kind === "product" && item.id) {
      close();
      void navigate({ to: "/product/$id", params: { id: item.id } });
      return;
    }
    if (item.kind === "category" && categories.some((c) => c.id === item.label)) {
      close();
      void navigate({ to: "/shop", search: { category: item.label as CategoryId } });
      return;
    }
    submit(item.label);
  };

  const rows = useMemo<Row[]>(() => {
    if (!suggesting) {
      return (history.data ?? []).map((entry) => ({
        type: "history" as const,
        key: entry.id,
        entry,
      }));
    }
    const list: Row[] = [{ type: "submit", key: "__submit__" }];
    (suggestions.data ?? []).forEach((suggestion, index) => {
      list.push({
        type: "suggestion",
        key: `${suggestion.kind}:${suggestion.label}:${index}`,
        suggestion,
      });
    });
    return list;
  }, [suggesting, history.data, suggestions.data]);

  // a new query or a fresh result list invalidates the highlighted row
  useEffect(() => {
    setActive(-1);
  }, [suggesting, rows.length]);

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (rows.length ? (index + 1) % rows.length : -1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (rows.length ? (index - 1 + rows.length) % rows.length : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const row = rows[active];
      if (!row || row.type === "submit") submit(value);
      else if (row.type === "suggestion") pick(row.suggestion);
      else submit(row.entry.query);
    }
  };

  const historyEntries = history.data ?? [];

  const historyBlock = !user ? (
    <p className="px-2 py-6 text-center text-xs text-muted-foreground">
      برای دیدن جستجوهای اخیر وارد حساب کاربری شوید.
    </p>
  ) : history.isLoading ? (
    <div className="space-y-2 p-1">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="h-8 animate-pulse rounded-md bg-clay" />
      ))}
    </div>
  ) : historyEntries.length === 0 ? (
    <p className="px-2 py-6 text-center text-xs text-muted-foreground">
      عبارتی بنویسید تا در محصولات، دسته‌ها و برچسب‌ها جستجو کنیم.
    </p>
  ) : (
    <div>
      <div className="flex items-center justify-between px-2 pb-1">
        <span className="text-[11px] tracking-[0.16em] text-sage-deep">جستجوهای اخیر</span>
        <button
          type="button"
          disabled={clearHistory.isPending}
          onClick={() => clearHistory.mutate()}
          className="text-[11px] text-muted-foreground transition-colors hover:text-terracotta disabled:opacity-50"
        >
          پاک کردن همه
        </button>
      </div>
      {rows.map((row, index) =>
        row.type === "history" ? (
          <div
            key={row.key}
            className={cn("flex items-center rounded-md", active === index && "bg-sand")}
          >
            <button
              type="button"
              onClick={() => submit(row.entry.query)}
              onMouseEnter={() => setActive(index)}
              className="flex flex-1 items-center gap-2 px-2 py-2 text-right text-sm"
            >
              <Clock className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{row.entry.query}</span>
            </button>
            <button
              type="button"
              aria-label={`حذف ${row.entry.query}`}
              disabled={removeHistory.isPending}
              onClick={() => removeHistory.mutate(row.entry.id)}
              className="p-2 text-muted-foreground transition-colors hover:text-terracotta disabled:opacity-50"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ) : null,
      )}
    </div>
  );

  const suggestionsList = suggestions.data ?? [];

  const suggestionsBlock = (
    <div>
      <button
        type="button"
        onClick={() => submit(value)}
        onMouseEnter={() => setActive(0)}
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-2 text-right text-sm",
          active === 0 && "bg-sand",
        )}
      >
        <Search className="size-3.5 shrink-0 text-terracotta" />
        <span className="truncate">جستجوی «{value.trim()}»</span>
      </button>

      {suggestions.isFetching && suggestionsList.length === 0 ? (
        <div className="space-y-2 p-1">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-8 animate-pulse rounded-md bg-clay" />
          ))}
        </div>
      ) : suggestions.isError ? (
        <p className="px-2 py-4 text-center text-xs text-muted-foreground">
          جستجو انجام نشد. دوباره تلاش کنید.
        </p>
      ) : suggestionsList.length === 0 ? (
        <p className="px-2 py-4 text-center text-xs text-muted-foreground">نتیجه‌ای پیدا نشد.</p>
      ) : (
        suggestionsList.map((item, index) => (
          <button
            key={`${item.kind}-${item.label}-${index}`}
            type="button"
            onClick={() => pick(item)}
            onMouseEnter={() => setActive(index + 1)}
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-2 py-2 text-right text-sm",
              active === index + 1 && "bg-sand",
            )}
          >
            {item.image ? (
              <img
                src={item.image}
                alt=""
                aria-hidden="true"
                className="size-8 shrink-0 rounded-md object-cover"
              />
            ) : (
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sand text-muted-foreground">
                {item.kind === "tag" ? (
                  <Tag className="size-3.5" />
                ) : item.kind === "query" ? (
                  <Clock className="size-3.5" />
                ) : (
                  <Search className="size-3.5" />
                )}
              </span>
            )}
            <span className="flex-1 truncate">{item.label}</span>
            <span className="shrink-0 text-[11px] text-muted-foreground">
              {KIND_HINTS[item.kind]}
            </span>
          </button>
        ))
      )}
    </div>
  );

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="جستجو در محصولات"
          className="text-foreground/70 transition-colors hover:text-foreground"
        >
          <Search className="size-5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="center" className="w-[min(24rem,calc(100vw-2rem))] p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="جستجوی محصول، دسته یا برچسب…"
            aria-label="عبارت جستجو"
            className="bg-sand pr-9"
          />
          {value && (
            <button
              type="button"
              aria-label="پاک کردن عبارت"
              onClick={() => {
                setValue("");
                inputRef.current?.focus();
              }}
              className="absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground transition-colors hover:text-terracotta"
            >
              <X className="size-4" />
            </button>
          )}
        </div>

        <div className="mt-2 max-h-[60vh] overflow-y-auto">
          {suggesting ? suggestionsBlock : historyBlock}
        </div>
      </PopoverContent>
    </Popover>
  );
}
