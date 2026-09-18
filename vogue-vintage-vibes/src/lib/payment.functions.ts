import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const orderInput = z.object({ orderId: z.string().uuid() });

/** Gateway session details for a pending order (simulated PSP). */
export const getPaymentSession = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => orderInput.parse(input))
  .handler(async ({ data, context }) => {
    const { data: order, error } = await context.supabase
      .from("orders")
      .select("id, order_number, total, payment_status, status")
      .eq("id", data.orderId)
      .eq("user_id", context.userId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!order) throw new Error("سفارش پیدا نشد");
    return {
      orderId: order.id,
      orderNumber: order.order_number,
      total: order.total,
      paymentStatus: order.payment_status,
      trackingCode: `SND-${order.order_number}-${order.id.slice(0, 6).toUpperCase()}`,
    };
  });

/** Simulated gateway callback: mark the order paid or failed. */
export const completePayment = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    orderInput.extend({ outcome: z.enum(["success", "failure"]) }).parse(input),
  )
  .handler(async ({ data, context }) => {
    const { data: order, error } = await context.supabase
      .from("orders")
      .select("id, order_number, total, payment_status")
      .eq("id", data.orderId)
      .eq("user_id", context.userId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!order) throw new Error("سفارش پیدا نشد");
    if (order.payment_status === "paid") {
      return { ok: true, orderNumber: order.order_number, reference: null as string | null };
    }

    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const paid = data.outcome === "success";
    const reference = `SND-${order.order_number}-${Math.floor(Math.random() * 900000 + 100000)}`;

    const { error: orderError } = await supabaseAdmin
      .from("orders")
      .update({
        payment_status: paid ? "paid" : "unpaid",
        status: paid ? "processing" : "pending",
      })
      .eq("id", order.id);
    if (orderError) throw new Error(orderError.message);

    const { error: paymentError } = await supabaseAdmin.from("payments").insert({
      order_id: order.id,
      user_id: context.userId,
      amount: order.total,
      method: "online",
      status: paid ? "succeeded" : "failed",
      reference,
    });
    if (paymentError) throw new Error(paymentError.message);

    return { ok: paid, orderNumber: order.order_number, reference };
  });
