import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";

export function CancelOrderButton({ orderId }: { orderId: string }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.cancelOrder(orderId),
    onSuccess: () => {
      toast.success("سفارش لغو شد");
      queryClient.invalidateQueries({ queryKey: ["my-orders"] });
      queryClient.invalidateQueries({ queryKey: ["order-status", orderId] });
      queryClient.invalidateQueries({ queryKey: ["my-payments"] });
    },
    onError: (error: Error) => toast.error(error.message || "لغو سفارش انجام نشد"),
  });

  return (
    <button
      type="button"
      disabled={mutation.isPending}
      onClick={() => {
        if (window.confirm("از لغو این سفارش مطمئن هستید؟")) mutation.mutate();
      }}
      className="rounded-full border border-terracotta px-5 py-2 text-xs text-terracotta transition-colors hover:bg-terracotta hover:text-background disabled:opacity-50"
    >
      {mutation.isPending ? "در حال لغو…" : "لغو سفارش"}
    </button>
  );
}
