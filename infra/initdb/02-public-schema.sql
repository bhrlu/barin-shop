-- Local schema for the SÂNDÉ store. The backend (FastAPI) owns auth now:
-- `public.users` is a real table with bcrypt password hashes. All FKs that
-- previously pointed at Supabase's auth.users point at public.users.
-- RLS policies/grants from the Supabase era are intentionally gone —
-- authorization is enforced by the API, not the database.

CREATE TYPE public.app_role AS ENUM ('admin', 'customer');

-- Own users (replaces Supabase auth.users)
CREATE TABLE public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  full_name TEXT,
  phone TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  UNIQUE (user_id, role)
);

CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role public.app_role)
RETURNS BOOLEAN LANGUAGE sql STABLE SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role)
$$;

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

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;
CREATE TRIGGER products_updated_at BEFORE UPDATE ON public.products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- addresses
CREATE TABLE public.addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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

-- favorites
CREATE TABLE public.favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, product_id)
);

-- orders
CREATE TABLE public.orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number TEXT NOT NULL UNIQUE DEFAULT to_char(now(), 'YYMMDD') || lpad((floor(random() * 100000))::text, 5, '0'),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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

CREATE TABLE public.payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,
  method TEXT NOT NULL DEFAULT 'online',
  status TEXT NOT NULL DEFAULT 'pending',
  reference TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX orders_user_idx ON public.orders(user_id, created_at DESC);
CREATE INDEX order_items_order_idx ON public.order_items(order_id);
CREATE INDEX favorites_user_idx ON public.favorites(user_id);

-- refund requests
CREATE TABLE public.refund_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  amount integer NOT NULL,
  reason text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'requested',
  admin_note text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  UNIQUE (order_id)
);
CREATE TRIGGER refund_requests_updated_at BEFORE UPDATE ON public.refund_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- starter catalog (same 20 products as before)
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
('socks-16', 'جوراب پشمی گرم زمستان', 'socks', 430000, NULL, ARRAY['36-38','39-41','42-44']::text[], '[{"name":"قهوه‌ای روشن","hex":"#8b7355"},{"name":"کرم","hex":"#f0ebe3"}]'::jsonb, ARRAY['cat-socks','cat-socks']::text[], 'مرینوس و پنبه', 'بافت ضخیم و گرم بدون خارش؛ برای روزهای سرد خانه.', false, 25, true),
('set-17', 'ست کراپ و شورت شنی', 'set', 1650000, 1980000, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"کرم","hex":"#f0ebe3"}]'::jsonb, ARRAY['cat-set','model-crop']::text[], 'ویسکوز و کتان', 'ست دوتکه‌ی هم‌رنگ؛ با هم یا جدا از هم قابل استایل کردن.', true, 25, true),
('set-18', 'ست تی‌شرت و شورت خانه', 'set', 1380000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"قهوه‌ای روشن","hex":"#8b7355"}]'::jsonb, ARRAY['cat-set','cat-tshirt']::text[], 'پنبه‌ی نرم', 'دوتکه‌ی راحت با دوخت تمیز؛ سبک و خنک برای خانه.', false, 25, true),
('set-19', 'ست لانژ آستین‌بلند نسیم', 'set', 1890000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"شنی","hex":"#c9b99a"},{"name":"زغالی","hex":"#3a352f"}]'::jsonb, ARRAY['cat-set','model-tshirt']::text[], 'ویسکوز مات', 'پیراهن یقه‌برگردان و شلوار کمر کشی با افت روان.', false, 25, true),
('set-20', 'ست بافت ریب دوتکه رزا', 'set', 1740000, NULL, ARRAY['XS','S','M','L','XL']::text[], '[{"name":"کرم","hex":"#f0ebe3"},{"name":"شنی","hex":"#c9b99a"}]'::jsonb, ARRAY['cat-set','cat-crop']::text[], 'ریب کشباف', 'کراپ ریب همراه شورت هم‌بافت؛ ترکیبی مدرن با حس کلاسیک.', false, 25, true)
ON CONFLICT (id) DO NOTHING;
