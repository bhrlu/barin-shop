-- roles
CREATE TYPE public.app_role AS ENUM ('admin', 'customer');

CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT,
  phone TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  UNIQUE (user_id, role)
);
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role public.app_role)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role)
$$;

CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT TO authenticated
  USING (auth.uid() = id OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE TO authenticated
  USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

CREATE POLICY "user_roles_select_own" ON public.user_roles FOR SELECT TO authenticated
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));

-- auto profile + default role on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, phone)
  VALUES (NEW.id, NEW.raw_user_meta_data ->> 'full_name', NEW.raw_user_meta_data ->> 'phone')
  ON CONFLICT (id) DO NOTHING;
  INSERT INTO public.user_roles (user_id, role) VALUES (NEW.id, 'customer')
  ON CONFLICT (user_id, role) DO NOTHING;
  RETURN NEW;
END;
$$;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- products
CREATE TABLE public.products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price INTEGER NOT NULL,
  old_price INTEGER,
  sizes TEXT[] NOT NULL DEFAULT '{}',
  colors JSONB NOT NULL DEFAULT '[]',
  images TEXT[] NOT NULL DEFAULT '{}',
  material TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  is_new BOOLEAN NOT NULL DEFAULT false,
  stock INTEGER NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT ON public.products TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.products TO authenticated;
GRANT ALL ON public.products TO service_role;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "products_public_read" ON public.products FOR SELECT TO anon, authenticated
  USING (active OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "products_admin_write" ON public.products FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin')) WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;
CREATE TRIGGER products_updated_at BEFORE UPDATE ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- addresses
CREATE TABLE public.addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'خانه',
  receiver TEXT NOT NULL,
  phone TEXT NOT NULL,
  province TEXT NOT NULL,
  city TEXT NOT NULL,
  postal_code TEXT,
  line TEXT NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.addresses TO authenticated;
GRANT ALL ON public.addresses TO service_role;
ALTER TABLE public.addresses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "addresses_own" ON public.addresses FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- favorites
CREATE TABLE public.favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, product_id)
);
GRANT SELECT, INSERT, DELETE ON public.favorites TO authenticated;
GRANT ALL ON public.favorites TO service_role;
ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;
CREATE POLICY "favorites_own" ON public.favorites FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- orders
CREATE TABLE public.orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number TEXT NOT NULL UNIQUE DEFAULT to_char(now(), 'YYMMDD') || lpad((floor(random() * 100000))::text, 5, '0'),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending',
  payment_status TEXT NOT NULL DEFAULT 'unpaid',
  payment_method TEXT NOT NULL DEFAULT 'online',
  subtotal INTEGER NOT NULL DEFAULT 0,
  discount INTEGER NOT NULL DEFAULT 0,
  shipping INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL DEFAULT 0,
  shipping_address JSONB NOT NULL DEFAULT '{}',
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.orders TO authenticated;
GRANT ALL ON public.orders TO service_role;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "orders_select" ON public.orders FOR SELECT TO authenticated
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "orders_insert_own" ON public.orders FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "orders_update_admin" ON public.orders FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(), 'admin')) WITH CHECK (public.has_role(auth.uid(), 'admin'));
CREATE TRIGGER orders_updated_at BEFORE UPDATE ON public.orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  product_id TEXT REFERENCES public.products(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  size TEXT,
  color TEXT,
  image TEXT,
  quantity INTEGER NOT NULL DEFAULT 1
);
GRANT SELECT, INSERT ON public.order_items TO authenticated;
GRANT ALL ON public.order_items TO service_role;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "order_items_select" ON public.order_items FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.orders o WHERE o.id = order_id
    AND (o.user_id = auth.uid() OR public.has_role(auth.uid(), 'admin'))));
CREATE POLICY "order_items_insert_own" ON public.order_items FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM public.orders o WHERE o.id = order_id AND o.user_id = auth.uid()));

CREATE TABLE public.payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,
  method TEXT NOT NULL DEFAULT 'online',
  status TEXT NOT NULL DEFAULT 'pending',
  reference TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.payments TO authenticated;
GRANT ALL ON public.payments TO service_role;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "payments_select" ON public.payments FOR SELECT TO authenticated
  USING (auth.uid() = user_id OR public.has_role(auth.uid(), 'admin'));
CREATE POLICY "payments_insert_own" ON public.payments FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX orders_user_idx ON public.orders(user_id, created_at DESC);
CREATE INDEX order_items_order_idx ON public.order_items(order_id);
CREATE INDEX favorites_user_idx ON public.favorites(user_id);

INSERT INTO public.products (id, name, category, price, old_price, sizes, colors, images, material, description, is_new, stock, active) VALUES
('tshirt-1', 'تی‌شرت اورسایز پنبه‌ای مینا', 'tshirt', 690000, 890000, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"سفید شکسته","hex":"#faf8f5"},{"name":"شنی","hex":"#c9b99a"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['model-tshirt','cat-tshirt']::text[], '۱۰۰٪ پنبه پنبه‌ریز، گرماژ ۱۸۰', 'برشی آزاد و افتاده با یقه گرد دوخت‌دوبل؛ انتخابی آرام برای هر روز که فرم خود را پس از شست‌وشو حفظ می‌کند.', true, 25, true),
('tshirt-2', 'تی‌شرت جادار روزمره نارین', 'tshirt', 540000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"}]'::jsonb, ARRAY['cat-tshirt','model-tshirt']::text[], 'پنبه و ویسکوز، لطیف و خنک', 'پارچه‌ای سبک با درز کناری تمیز؛ زیر کت و بلیزر عالی می‌نشیند و در تنه کشیدگی ندارد.', false, 25, true),
('tshirt-3', 'تی‌شرت یقه‌گرد کلاسیک ورا', 'tshirt', 620000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"سفید شکسته","hex":"#faf8f5"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['model-tshirt','cat-tshirt']::text[], 'پنبه شانه‌زده', 'خط شانه‌ی دقیق و آستین کوتاه استاندارد؛ پایه‌ای که هر فصل به کار می‌آید.', false, 25, true),
('tshirt-4', 'تی‌شرت آستین‌کوتاه ریب لینا', 'tshirt', 580000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"کرم","hex":"#f0ebe3"}]'::jsonb, ARRAY['cat-tshirt','model-crop']::text[], 'ریب پنبه‌ای کشی', 'بافت ریب باریک با کشش ملایم که بدن را نرم قالب می‌گیرد.', false, 25, true),
('crop-5', 'کراپ‌تاپ بافت ریب آوا', 'crop', 720000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['model-crop','cat-crop']::text[], 'بافت ریب با نخ ویسکوز', 'قد کوتاه با لبه‌ی کشی؛ روی شورت فاق‌بلند و دامن ماکسی هر دو خوش می‌نشیند.', true, 25, true),
('crop-6', 'کراپ‌تاپ آستین‌پفی رها', 'crop', 780000, 950000, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"سفید شکسته","hex":"#faf8f5"},{"name":"شنی","hex":"#c9b99a"}]'::jsonb, ARRAY['cat-crop','model-crop']::text[], 'پنبه استرچ', 'آستین حجم‌دار کوتاه و یقه‌ی قاشقی؛ جزئیاتی کلاسیک با فرم امروزی.', false, 25, true),
('crop-7', 'کراپ‌تاپ بندی نیلا', 'crop', 640000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"قهوه‌ای روشن","hex":"#8b7355"},{"name":"کرم","hex":"#f0ebe3"}]'::jsonb, ARRAY['cat-crop','model-crop']::text[], 'جرسی پنبه‌ای', 'بندهای قابل تنظیم و پشت ساده؛ سبک برای روزهای گرم.', false, 25, true),
('crop-8', 'کراپ‌تاپ یقه‌قایقی سانا', 'crop', 690000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['model-crop','cat-crop']::text[], 'ریب نرم', 'یقه‌ی باز افقی که خط شانه را کشیده نشان می‌دهد.', false, 25, true),
('shorts-9', 'شورت کتان پیلی‌دار هلیا', 'shorts', 980000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"کرم","hex":"#f0ebe3"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-shorts','model-crop']::text[], 'کتان و پنبه، آستر ندارد', 'فاق بلند با دو پیلی جلو و جیب مورب؛ خطی رسمی با راحتی پارچه‌ی نفس‌گیر.', true, 25, true),
('shorts-10', 'شورت راحتی کشی سوگل', 'shorts', 620000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"}]'::jsonb, ARRAY['cat-shorts','cat-set']::text[], 'پنبه‌ی حلقوی', 'کمر کشی با بند تنظیم؛ برای خانه و پیاده‌روی‌های کوتاه.', false, 25, true),
('shorts-11', 'شورت جین کوتاه بهار', 'shorts', 1120000, 1350000, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-shorts','model-crop']::text[], 'دنیم سبک ۱۱ اونس', 'برش صاف با لبه‌ی تاشو و دوخت متضاد؛ کلاسیکی که کهنه نمی‌شود.', false, 25, true),
('shorts-12', 'شورت کتان بغل‌چاک آرمیتا', 'shorts', 890000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"شنی","hex":"#c9b99a"}]'::jsonb, ARRAY['cat-shorts','cat-set']::text[], 'کتان خالص', 'چاک کوتاه کناری برای آزادی حرکت و افت بهتر پارچه.', false, 25, true),
('socks-13', 'جوراب نخی ساق‌کوتاه (سه‌جفت)', 'socks', 320000, NULL, ARRAY['36-38','39-41','42-44']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"شنی","hex":"#c9b99a"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-socks','cat-socks']::text[], '۸۰٪ پنبه، ۱۷٪ پلی‌آمید، ۳٪ الاستان', 'کف حوله‌ای نرم و لبه‌ی بدون اثر؛ بسته‌ی سه‌جفتی در رنگ‌های خنثی.', false, 25, true),
('socks-14', 'جوراب ساق‌بلند ریب مه', 'socks', 240000, NULL, ARRAY['36-38','39-41','42-44']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"}]'::jsonb, ARRAY['cat-socks','cat-socks']::text[], 'پنبه ریب', 'ساق تا نیمه‌ی ساق پا با کشی ملایم که پایین نمی‌آید.', true, 25, true),
('socks-15', 'جوراب مچی نامرئی (پنج‌جفت)', 'socks', 380000, 450000, ARRAY['36-38','39-41','42-44']::text[], '[{"name":"سفید شکسته","hex":"#faf8f5"},{"name":"شنی","hex":"#c9b99a"}]'::jsonb, ARRAY['cat-socks','cat-socks']::text[], 'پنبه با سیلیکون پاشنه', 'زیر کفش‌های تخت دیده نمی‌شود و پاشنه‌ی سیلیکونی سرنمی‌خورد.', false, 25, true),
('socks-16', 'جوراب پشمی گرم زمستان', 'socks', 430000, NULL, ARRAY['36-38','39-41','42-44']::text[], '[{"name":"قهوه‌ای روشن","hex":"#8b7355"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-socks','cat-socks']::text[], 'مرینوس و پنبه', 'بافت ضخیم و گرم بدون خارش؛ برای روزهای سرد خانه.', false, 25, true),
('set-17', 'ست کراپ و شورت شنی', 'set', 1650000, 1980000, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"کرم","hex":"#f0ebe3"}]'::jsonb, ARRAY['cat-set','model-crop']::text[], 'ویسکوز و کتان', 'ست دوتکه‌ی هم‌رنگ؛ با هم یا جدا از هم قابل استایل کردن.', true, 25, true),
('set-18', 'ست تی‌شرت و شورت خانه', 'set', 1380000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"}]'::jsonb, ARRAY['cat-set','cat-tshirt']::text[], 'پنبه‌ی نرم', 'دوتکه‌ی راحت با دوخت تمیز؛ سبک و خنک برای خانه.', false, 25, true),
('set-19', 'ست لانژ آستین‌بلند نسیم', 'set', 1890000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-set','model-tshirt']::text[], 'ویسکوز مات', 'پیراهن یقه‌برگردان و شلوار کمر کشی با افت روان.', false, 25, true),
('set-20', 'ست بافت ریب دوتکه رزا', 'set', 1740000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"شنی","hex":"#c9b99a"}]'::jsonb, ARRAY['cat-set','cat-crop']::text[], 'ریب کشباف', 'کراپ ریب همراه شورت هم‌بافت؛ ترکیبی مدرن با حس کلاسیک.', false, 25, true)
ON CONFLICT (id) DO NOTHING;