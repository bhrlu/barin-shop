import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const cancelInput = z.object({ orderId: z.string().uuid() });

/** Customer-initiated cancellation, allowed only before the order ships. */
export const cancelOrder = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) => cancelInput.parse(input))
  .handler(async ({ data, context }) => {
    const { data: order, error } = await context.supabase
      .from("orders")
      .select("id, order_number, status, payment_status, total")
      .eq("id", data.orderId)
      .eq("user_id", context.userId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!order) throw new Error("سفارش پیدا نشد");
    if (order.status === "cancelled") {
      return { ok: true, orderNumber: order.order_number };
    }
    if (["shipped", "delivered"].includes(order.status)) {
      throw new Error("سفارش ارسال شده و امکان لغو ندارد");
    }

    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { error: updateError } = await supabaseAdmin
      .from("orders")
      .update({ status: "cancelled" })
      .eq("id", order.id);
    if (updateError) throw new Error(updateError.message);

    return {
      ok: true,
      orderNumber: order.order_number,
      refundEligible: order.payment_status === "paid",
    };
  });

/** Customer submits a refund request for a cancelled, paid order. */
export const requestRefund = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    cancelInput.extend({ reason: z.string().trim().max(500).default("") }).parse(input),
  )
  .handler(async ({ data, context }) => {
    const { data: order, error } = await context.supabase
      .from("orders")
      .select("id, order_number, status, payment_status, total")
      .eq("id", data.orderId)
      .eq("user_id", context.userId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!order) throw new Error("سفارش پیدا نشد");
    if (order.status !== "cancelled" || order.payment_status !== "paid") {
      throw new Error("فقط برای سفارش‌های لغوشده و پرداخت‌شده می‌توان بازپرداخت درخواست کرد");
    }

    const { error: insertError } = await context.supabase.from("refund_requests").insert({
      order_id: order.id,
      user_id: context.userId,
      amount: order.total,
      reason: data.reason,
      status: "requested",
    });
    if (insertError) {
      if (insertError.code === "23505" || insertError.code === "23405" || insertError.code === "23000" || insertError.message.includes("duplicate")) {
        throw new Error("برای این سفارش قبلاً درخواست بازپرداخت ثبت شده است");
      }
      throw new Error(insertError.message);
    }
    return { ok: true, orderNumber: order.order_number };
  });

/** Admin resolves a refund request; approving marks the order refunded. */
export const resolveRefundRequest = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((input: unknown) =>
    z
      .object({
        requestId: z.string().uuid(),
        status: z.enum(["approved", "rejected", "refunded"]),
        adminNote: z.string().trim().max(500).optional(),
      })
      .parse(input),
  )
  .handler(async ({ data, context }) => {
    const { data: isAdmin, error: roleError } = await context.supabase.rpc("has_role", {
      _user_id: context.userId,
      _role: "admin",
    });
    if (roleError) throw new Error(roleError.message);
    if (!isAdmin) throw new Error("دسترسی مجاز نیست");

    const { supabaseAdmin } = await import("@/integrations/supabase/client.server");
    const { data: request, error } = await supabaseAdmin
      .from("refund_requests")
      .update({ status: data.status, admin_note: data.adminNote ?? null })
      .eq("id", data.requestId)
      .select("id, order_id, user_id, amount")
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!request) throw new Error("درخواست پیدا نشد");

    if (data.status === "refunded") {
      const { error: orderError } = await supabaseAdmin
        .from("orders")
        .update({ payment_status: "refunded" })
        .eq("id", request.order_id);
      if (orderError) throw new Error(orderError.message);
      const { error: paymentError } = await supabaseAdmin.from("payments").insert({
        order_id: request.order_id,
        user_id: request.user_id,
        amount: request.amount,
        method: "refund",
        status: "refunded",
        reference: `RFD-${request.id.slice(0, 8).toUpperCase()}`,
      });
      if (paymentError) throw new Error(paymentError.message);
    }

    return { ok: true };
  });