import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Copy, Eye } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError, toPage, type AdminOrderListParams, type Order } from "@/lib/api";
import { formatFaDate, formatToman, toFa, toLatinDigits } from "@/lib/format";
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { OrderDetailDrawer } from "@/components/admin/OrderDetailDrawer";
import { OrdersExportPanel } from "@/components/admin/ExportControls";
import { AdminDataTable, CopyValue } from "@/components/admin/AdminDataTable";

/** Rows per page for the fulfilment list (F2.5). */
const PAGE_SIZE = 20;

export const Route = createFileRoute("/_authenticated/admin/orders")({
  component: AdminOrders,
});

/** Table sort → `GET /admin/orders?sort=` (F4.3). */
function toSort(sorting: SortingState): NonNullable<AdminOrderListParams["sort"]> {
  const [first] = sorting;
  if (first?.id === "total") return first.desc ? "total_desc" : "total_asc";
  return first && !first.desc ? "old" : "new";
}

/** The receiver as checkout stores it (`full_name`); `receiver` on older rows. */
const receiverOf = (order: Order) =>
  order.shipping_address["full_name"] || order.shipping_address["receiver"] || "—";

async function copyAddress(address: Record<string, string>) {
  const text = [
    address["full_name"] || address["receiver"],
    address["phone"],
    [address["province"], address["city"]].filter(Boolean).join("، "),
    address["line"],
    address["postal_code"] ? `کد پستی: ${address["postal_code"]}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  try {
    await navigator.clipboard.writeText(text);
    toast.success("آدرس گیرنده کپی شد");
  } catch {
    toast.error("کپی انجام نشد");
  }
}

const selectClass = "h-8 rounded-md border border-input bg-background px-2 text-xs";

function AdminOrders() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Order | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [statuses, setStatuses] = useState<string[]>([]);
  const [payment, setPayment] = useState<string[]>([]);
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const [bulkStatus, setBulkStatus] = useState("processing");

  // every filter change goes back to the first page
  const refilter =
    <V,>(set: (value: V) => void) =>
    (value: V) => {
      set(value);
      setPage(1);
    };

  const params: AdminOrderListParams = {
    page,
    pageSize: PAGE_SIZE,
    q: toLatinDigits(q),
    status: statuses,
    ...(payment[0] ? { payment_status: payment[0] } : {}),
    sort: toSort(sorting),
  };
  const orders = useQuery({
    queryKey: ["admin-orders", params],
    queryFn: () => toPage(api.adminOrders(params)),
    placeholderData: keepPreviousData,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-kpis"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "kpis"] });
  };

  const update = useMutation({
    mutationFn: (input: { id: string; patch: { status?: string; payment_status?: string } }) =>
      api.patchOrder(input.id, input.patch),
    onSuccess: () => {
      invalidate();
      toast.success("سفارش به‌روزرسانی شد");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "به‌روزرسانی ناموفق بود"),
  });

  /** One `PATCH /orders/{id}` per order — the same canonical transition the row uses,
   * so the server still refuses a move the state machine does not allow. */
  const bulk = useMutation({
    mutationFn: async (input: { ids: string[]; status: string }) => {
      let ok = 0;
      const failed: string[] = [];
      for (const id of input.ids) {
        try {
          await api.patchOrder(id, { status: input.status });
          ok += 1;
        } catch (error) {
          failed.push(error instanceof ApiError ? error.message : "ناموفق");
        }
      }
      return { ok, failed };
    },
    onSuccess: ({ ok, failed }, input) => {
      invalidate();
      const label = ORDER_STATUS[input.status] ?? input.status;
      if (ok) toast.success(`${toFa(ok)} سفارش به «${label}» رفت`);
      if (failed.length)
        toast.error(`${toFa(failed.length)} سفارش تغییر نکرد: ${[...new Set(failed)].join("، ")}`);
    },
  });

  const columns: ColumnDef<Order>[] = [
    {
      id: "order_number",
      header: "سفارش",
      enableSorting: false,
      cell: ({ row }) => <CopyValue value={row.original.order_number} label="شماره سفارش" />,
    },
    {
      id: "customer",
      header: "گیرنده",
      enableSorting: false,
      cell: ({ row }) => {
        const address = row.original.shipping_address;
        return (
          <div className="min-w-40">
            <p className="flex items-center gap-1.5">
              {receiverOf(row.original)}
              {address["line"] ? (
                <button
                  type="button"
                  onClick={() => void copyAddress(address)}
                  aria-label="کپی آدرس گیرنده"
                  title="کپی آدرس گیرنده"
                  className="text-muted-foreground hover:text-foreground"
                >
                  <Copy className="size-3.5" />
                </button>
              ) : null}
            </p>
            <div className="text-xs text-muted-foreground">
              <CopyValue value={address["phone"]} label="تلفن" />
            </div>
          </div>
        );
      },
    },
    {
      // sortable: react-table only sorts columns with an accessor
      accessorKey: "created_at",
      header: "تاریخ",
      cell: ({ row }) => (
        <span className="whitespace-nowrap text-xs">{formatFaDate(row.original.created_at)}</span>
      ),
    },
    {
      // sortable: react-table only sorts columns with an accessor
      accessorKey: "total",
      header: "مبلغ",
      cell: ({ row }) => (
        <span className="whitespace-nowrap">{formatToman(Number(row.original.total))} تومان</span>
      ),
    },
    {
      id: "status",
      header: "وضعیت",
      enableSorting: false,
      cell: ({ row }) => (
        <select
          aria-label={`وضعیت سفارش ${row.original.order_number}`}
          value={row.original.status}
          onChange={(e) =>
            update.mutate({ id: row.original.id, patch: { status: e.target.value } })
          }
          className={selectClass}
        >
          {Object.entries(ORDER_STATUS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      ),
    },
    {
      id: "payment_status",
      header: "پرداخت",
      enableSorting: false,
      cell: ({ row }) => (
        <select
          aria-label={`وضعیت پرداخت سفارش ${row.original.order_number}`}
          value={row.original.payment_status}
          onChange={(e) =>
            update.mutate({ id: row.original.id, patch: { payment_status: e.target.value } })
          }
          className={selectClass}
        >
          {Object.entries(PAYMENT_STATUS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      ),
    },
    {
      id: "tracking_code",
      header: "کد رهگیری",
      enableSorting: false,
      cell: ({ row }) => <CopyValue value={row.original.tracking_code} label="کد رهگیری" />,
    },
    {
      id: "actions",
      header: () => <span className="sr-only">اقدام</span>,
      enableSorting: false,
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => setSelected(row.original)}
          className="flex items-center gap-1.5 whitespace-nowrap rounded-full bg-terracotta px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-terracotta/90"
        >
          <Eye className="size-3.5" />
          مشاهده و پردازش
        </button>
      ),
    },
  ];

  const items = orders.data?.items ?? [];
  // keep the drawer's order object fresh after mutations invalidate the list
  const selectedFresh = selected ? (items.find((order) => order.id === selected.id) ?? null) : null;

  return (
    <>
      <OrdersExportPanel className="mb-6" />
      <AdminDataTable
        caption="سفارش‌ها"
        columns={columns}
        data={items}
        getRowId={(order) => order.id}
        page={orders.data?.page ?? page}
        pages={orders.data?.pages ?? 1}
        total={orders.data?.total}
        onPageChange={setPage}
        sorting={sorting}
        onSortingChange={refilter(setSorting)}
        search={{
          value: q,
          onChange: refilter(setQ),
          placeholder: "جست‌وجو: شماره سفارش، نام، تلفن، ایمیل یا کد رهگیری",
        }}
        filters={[
          {
            id: "status",
            label: "وضعیت",
            options: Object.entries(ORDER_STATUS).map(([value, label]) => ({ value, label })),
            selected: statuses,
            onChange: refilter(setStatuses),
          },
          {
            id: "payment",
            label: "پرداخت",
            multiple: false,
            options: Object.entries(PAYMENT_STATUS).map(([value, label]) => ({ value, label })),
            selected: payment,
            onChange: refilter(setPayment),
          },
        ]}
        bulkActions={(ids, clear) => (
          <>
            <select
              aria-label="وضعیت تازه برای سفارش‌های انتخاب‌شده"
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
              className="h-8 rounded-md border border-background/30 bg-foreground px-2 text-xs text-background"
            >
              {Object.entries(ORDER_STATUS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={bulk.isPending}
              onClick={() => bulk.mutate({ ids, status: bulkStatus }, { onSuccess: clear })}
              className="rounded-full bg-terracotta px-3 py-1.5 text-xs font-medium text-white hover:bg-terracotta/90 disabled:opacity-50"
            >
              {bulk.isPending ? "در حال اعمال…" : "تغییر وضعیت"}
            </button>
          </>
        )}
        isLoading={orders.isLoading}
        isFetching={orders.isFetching}
        isError={orders.isError}
        onRetry={() => void orders.refetch()}
        emptyMessage={
          q || statuses.length || payment.length
            ? "سفارشی با این جست‌وجو یا فیلترها پیدا نشد."
            : "سفارشی ثبت نشده است."
        }
      />
      <OrderDetailDrawer order={selectedFresh} onClose={() => setSelected(null)} />
    </>
  );
}
