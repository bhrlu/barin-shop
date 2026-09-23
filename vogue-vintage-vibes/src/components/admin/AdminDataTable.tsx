import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type OnChangeFn,
  type RowSelectionState,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Copy, Search, X } from "lucide-react";
import { toast } from "sonner";
import { toFa } from "@/lib/format";
import { Checkbox } from "@/components/ui/checkbox";
import { Pager } from "@/components/Pager";

/**
 * The canonical admin data table (F4.3, spec [FE-02], decision D8): `@tanstack/react-table`
 * with every piece of state controlled by the screen — search, filter chips, sort,
 * server-side page and the row selection that drives a floating bulk-action bar.
 * The table never filters, sorts or pages rows itself; the screen maps its state to the
 * API query. No second table abstraction should be created.
 */

export type FilterChipGroup = {
  id: string;
  label: string;
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** several options at once (default) or exactly one / none */
  multiple?: boolean;
};

export type AdminDataTableProps<T> = {
  /** read by screen readers; also names the table for tests */
  caption: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- mixed value types per column
  columns: ColumnDef<T, any>[];
  data: T[];
  getRowId: (row: T) => string;
  page: number;
  pages: number;
  total?: number | undefined;
  onPageChange: (page: number) => void;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  search?: { value: string; onChange: (value: string) => void; placeholder: string };
  filters?: FilterChipGroup[];
  /** e.g. export buttons, on the far side of the toolbar */
  toolbarEnd?: ReactNode;
  /** enables row checkboxes; rendered in the floating bar while rows are selected */
  bulkActions?: (selectedIds: string[], clearSelection: () => void) => ReactNode;
  isLoading: boolean;
  isFetching?: boolean;
  isError: boolean;
  onRetry?: () => void;
  emptyMessage: string;
};

/** Search box that reports after a short pause, and follows outside resets. */
function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState(value);
  const latest = useRef(onChange);
  useEffect(() => {
    latest.current = onChange;
  });
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (draft === value) return;
    const timer = window.setTimeout(() => latest.current(draft), 300);
    return () => window.clearTimeout(timer);
  }, [draft, value]);
  return (
    <label className="relative block w-full sm:max-w-xs">
      <span className="sr-only">{placeholder}</span>
      <Search
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <input
        type="search"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-full border border-border bg-card pr-9 pl-4 text-sm outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-terracotta"
      />
    </label>
  );
}

function Chips({ group }: { group: FilterChipGroup }) {
  const multiple = group.multiple ?? true;
  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-xs transition-colors ${
      active
        ? "border-terracotta bg-terracotta/10 text-terracotta"
        : "border-border text-muted-foreground hover:text-foreground"
    }`;
  return (
    <div role="group" aria-label={group.label} className="flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-muted-foreground">{group.label}:</span>
      <button
        type="button"
        aria-pressed={group.selected.length === 0}
        onClick={() => group.onChange([])}
        className={chip(group.selected.length === 0)}
      >
        همه
      </button>
      {group.options.map((option) => {
        const active = group.selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() =>
              group.onChange(
                multiple
                  ? active
                    ? group.selected.filter((value) => value !== option.value)
                    : [...group.selected, option.value]
                  : active
                    ? []
                    : [option.value],
              )
            }
            className={chip(active)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/** One-click copy for identifiers (tracking codes, phones, order numbers). */
export function CopyValue({
  value,
  label,
  mono = true,
}: {
  value: string | null | undefined;
  label: string;
  mono?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-muted-foreground">—</span>;
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          toast.success(`${label} کپی شد`);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          toast.error("کپی انجام نشد");
        }
      }}
      title={`کپی ${label}`}
      aria-label={`کپی ${label} ${value}`}
      className={`inline-flex items-center gap-1.5 rounded-md px-1 text-foreground transition-colors hover:bg-terracotta/5 hover:text-terracotta ${
        mono ? "font-mono tracking-wider" : ""
      }`}
      dir="ltr"
    >
      {value}
      {copied ? (
        <Check className="size-3.5 text-sage-deep" aria-hidden />
      ) : (
        <Copy className="size-3.5 opacity-50" aria-hidden />
      )}
    </button>
  );
}

export function AdminDataTable<T>({
  caption,
  columns,
  data,
  getRowId,
  page,
  pages,
  total,
  onPageChange,
  sorting,
  onSortingChange,
  search,
  filters,
  toolbarEnd,
  bulkActions,
  isLoading,
  isFetching,
  isError,
  onRetry,
  emptyMessage,
}: AdminDataTableProps<T>) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectable = Boolean(bulkActions);

  // the selection belongs to the rows on screen: a new page, search, filter or sort
  // starts from none, so a bulk action never reaches rows the admin cannot see
  const resetKey = JSON.stringify([
    page,
    search?.value,
    filters?.map((group) => group.selected),
    sorting,
  ]);
  useEffect(() => setRowSelection({}), [resetKey]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- see `columns`
  const selectColumn: ColumnDef<T, any> = {
    id: "__select",
    enableSorting: false,
    header: ({ table }) => (
      <Checkbox
        aria-label="انتخاب همهٔ ردیف‌های این صفحه"
        checked={
          table.getIsAllPageRowsSelected()
            ? true
            : table.getIsSomePageRowsSelected()
              ? "indeterminate"
              : false
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(value === true)}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        aria-label="انتخاب ردیف"
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(value === true)}
      />
    ),
  };

  const table = useReactTable({
    data,
    columns: selectable ? [selectColumn, ...columns] : columns,
    getRowId,
    state: { sorting: sorting ?? [], rowSelection },
    ...(onSortingChange ? { onSortingChange } : {}),
    onRowSelectionChange: setRowSelection,
    enableRowSelection: selectable,
    enableSortingRemoval: false,
    manualSorting: true,
    manualPagination: true,
    manualFiltering: true,
    pageCount: pages,
    getCoreRowModel: getCoreRowModel(),
  });

  const selectedIds = Object.keys(rowSelection).filter((id) => rowSelection[id]);
  const clearSelection = () => setRowSelection({});
  const columnCount = table.getVisibleLeafColumns().length;

  return (
    <div className="space-y-4">
      {(search || filters?.length || toolbarEnd) && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            {search ? <SearchBox {...search} /> : null}
            {filters?.map((group) => (
              <Chips key={group.id} group={group} />
            ))}
          </div>
          {toolbarEnd ? <div className="shrink-0">{toolbarEnd}</div> : null}
        </div>
      )}

      {/* `relative`: absolutely positioned bits (the sr-only caption, the checkboxes'
          hidden inputs) must be clipped by this scroller, not widen the page */}
      <div className="relative overflow-x-auto rounded-2xl border border-border">
        <table
          className={`w-full min-w-[720px] text-sm transition-opacity ${
            isFetching && !isLoading ? "opacity-60" : ""
          }`}
        >
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-muted/30 text-xs text-muted-foreground">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const canSort = header.column.getCanSort();
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={
                        sorted === "asc"
                          ? "ascending"
                          : sorted === "desc"
                            ? "descending"
                            : undefined
                      }
                      className="px-3 py-2.5 text-right font-medium whitespace-nowrap"
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 hover:text-foreground"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === "asc" ? (
                            <ArrowUp className="size-3.5" aria-hidden />
                          ) : sorted === "desc" ? (
                            <ArrowDown className="size-3.5" aria-hidden />
                          ) : (
                            <ArrowUpDown className="size-3.5 opacity-40" aria-hidden />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, index) => (
                <tr key={index} aria-hidden>
                  <td colSpan={columnCount} className="px-3 py-3">
                    <div className="h-5 animate-pulse rounded bg-clay/70" />
                  </td>
                </tr>
              ))
            ) : isError ? (
              <tr>
                <td colSpan={columnCount} className="px-3 py-10 text-center">
                  <p role="alert" className="text-sm text-terracotta">
                    خواندن فهرست انجام نشد.
                  </p>
                  {onRetry ? (
                    <button
                      type="button"
                      onClick={onRetry}
                      className="mt-3 rounded-full border border-border px-4 py-1.5 text-xs hover:border-terracotta hover:text-terracotta"
                    >
                      تلاش دوباره
                    </button>
                  ) : null}
                </td>
              </tr>
            ) : table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columnCount}
                  className="px-3 py-10 text-center text-sm text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  className="align-middle transition-colors hover:bg-muted/20 data-[state=selected]:bg-terracotta/5"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pager page={page} pages={Math.max(1, pages)} total={total} onChange={onPageChange} />

      {selectable && selectedIds.length > 0 ? (
        <div
          role="region"
          aria-label="اقدام گروهی"
          className="fixed inset-x-4 bottom-6 z-40 mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-3 rounded-2xl bg-foreground px-4 py-3 text-sm text-background shadow-xl sm:inset-x-0"
        >
          <span>{toFa(selectedIds.length)} مورد انتخاب شده</span>
          <div className="flex flex-wrap items-center gap-2">
            {bulkActions?.(selectedIds, clearSelection)}
            <button
              type="button"
              onClick={clearSelection}
              aria-label="لغو انتخاب"
              className="rounded-full p-1.5 text-background/70 hover:text-background"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
