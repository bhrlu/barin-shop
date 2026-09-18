import { supabase } from "@/integrations/supabase/client";
import type { CartLine } from "@/lib/cart";
import type { AdminProduct } from "@/lib/catalog";

export type ShippingInfo = {
  receiver: string;
  phone: string;
  province: string;
  city: string;
  postal_code: string;
  line: string;
};

export const ORDER_STATUS: Record<string, string> = {
  pending: "در انتظار تأیید",
  processing: "در حال پردازش",
  shipped: "ارسال شده",
  delivered: "تحویل شده",
  cancelled: "لغو شده",
};

export const PAYMENT_STATUS: Record<string, string> = {
  unpaid: "پرداخت نشده",
  paid: "پرداخت شده",
  refunded: "بازگشت داده شده",
};

export async function placeOrder(input: {
  userId: string;
  lines: CartLine[];
  products: (AdminProduct | undefined)[];
  subtotal: number;
  discount: number;
  shipping: number;
  paymentMethod: "online" | "cod";
  address: ShippingInfo;
  note?: string | undefined;
}) {
  const total = Math.max(0, input.subtotal - input.discount) + input.shipping;
  const { data: order, error } = await supabase
    .from("orders")
    .insert({
      user_id: input.userId,
      subtotal: input.subtotal,
      discount: input.discount,
      shipping: input.shipping,
      total,
      payment_method: input.paymentMethod,
      payment_status: "unpaid",
      status: "pending",
      shipping_address: input.address,
      note: input.note ?? null,
    })
    .select("id, order_number, total")
    .single();
  if (error) throw error;

  const items = input.lines.flatMap((line, index) => {
    const product = input.products[index];
    if (!product) return [];
    return [
      {
        order_id: order.id,
        product_id: product.id,
        name: product.name,
        price: product.price,
        size: line.size,
        color: line.color,
        image: product.images[0] ?? null,
        quantity: line.quantity,
      },
    ];
  });
  const { error: itemsError } = await supabase.from("order_items").insert(items);
  if (itemsError) throw itemsError;

  return order;
}