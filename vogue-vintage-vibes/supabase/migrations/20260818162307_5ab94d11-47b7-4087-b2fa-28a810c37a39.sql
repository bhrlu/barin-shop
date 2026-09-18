CREATE TABLE public.refund_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount integer NOT NULL,
  reason text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'requested',
  admin_note text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  UNIQUE (order_id)
);

GRANT SELECT, INSERT ON public.refund_requests TO authenticated;
GRANT ALL ON public.refund_requests TO service_role;

ALTER TABLE public.refund_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY refund_requests_select ON public.refund_requests FOR SELECT TO authenticated
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

CREATE POLICY refund_requests_insert_own ON public.refund_requests FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id AND EXISTS (
    SELECT 1 FROM public.orders o
    WHERE o.id = order_id AND o.user_id = auth.uid()
      AND o.status = 'cancelled' AND o.payment_status = 'paid'
  ));

CREATE TRIGGER refund_requests_updated_at BEFORE UPDATE ON public.refund_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();