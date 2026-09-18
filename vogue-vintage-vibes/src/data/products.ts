
export type CategoryId = "tshirt" | "crop" | "shorts" | "socks" | "set";

export type Product = {
  id: string;
  name: string;
  category: CategoryId;
  price: number;
  oldPrice?: number;
  colors: { name: string; hex: string }[];
  sizes: string[];
  images: string[];
  material: string;
  description: string;
  isNew?: boolean;
};

export const categories: { id: CategoryId; title: string; image: string }[] = [
  { id: "tshirt", title: "تی‌شرت", image: "cat-tshirt" },
  { id: "crop", title: "کراپ‌تاپ", image: "cat-crop" },
  { id: "shorts", title: "شورت", image: "cat-shorts" },
  { id: "socks", title: "جوراب", image: "cat-socks" },
  { id: "set", title: "ست", image: "cat-set" },
];

export const categoryTitle = (id: CategoryId) =>
  categories.find((c) => c.id === id)?.title ?? "";

const palette = {
  cream: { name: "کرم", hex: "#f0ebe3" },
  sand: { name: "شنی", hex: "#c9b99a" },
  taupe: { name: "قهوه‌ای روشن", hex: "#8b7355" },
  charcoal: { name: "زغالی", hex: "#3a352f" },
  offwhite: { name: "سفید شکسته", hex: "#faf8f5" },
};

const clothingSizes = ["XS", "S", "M", "L", "XL"];
const sockSizes = ["36-38", "39-41", "42-44"];

type Seed = Omit<Product, "id">;

const seeds: Seed[] = [
  {
    name: "تی‌شرت اورسایز پنبه‌ای مینا",
    category: "tshirt",
    price: 690000,
    oldPrice: 890000,
    colors: [palette.offwhite, palette.sand, palette.charcoal],
    sizes: clothingSizes,
    images: ["model-tshirt", "cat-tshirt"],
    material: "۱۰۰٪ پنبه پنبه‌ریز، گرماژ ۱۸۰",
    description:
      "برشی آزاد و افتاده با یقه گرد دوخت‌دوبل؛ انتخابی آرام برای هر روز که فرم خود را پس از شست‌وشو حفظ می‌کند.",
    isNew: true,
  },
  {
    name: "تی‌شرت جادار روزمره نارین",
    category: "tshirt",
    price: 540000,
    colors: [palette.cream, palette.taupe],
    sizes: clothingSizes,
    images: ["cat-tshirt", "model-tshirt"],
    material: "پنبه و ویسکوز، لطیف و خنک",
    description:
      "پارچه‌ای سبک با درز کناری تمیز؛ زیر کت و بلیزر عالی می‌نشیند و در تنه کشیدگی ندارد.",
  },
  {
    name: "تی‌شرت یقه‌گرد کلاسیک ورا",
    category: "tshirt",
    price: 620000,
    colors: [palette.offwhite, palette.charcoal],
    sizes: clothingSizes,
    images: ["model-tshirt", "cat-tshirt"],
    material: "پنبه شانه‌زده",
    description: "خط شانه‌ی دقیق و آستین کوتاه استاندارد؛ پایه‌ای که هر فصل به کار می‌آید.",
  },
  {
    name: "تی‌شرت آستین‌کوتاه ریب لینا",
    category: "tshirt",
    price: 580000,
    colors: [palette.sand, palette.cream],
    sizes: clothingSizes,
    images: ["cat-tshirt", "model-crop"],
    material: "ریب پنبه‌ای کشی",
    description: "بافت ریب باریک با کشش ملایم که بدن را نرم قالب می‌گیرد.",
  },
  {
    name: "کراپ‌تاپ بافت ریب آوا",
    category: "crop",
    price: 720000,
    colors: [palette.cream, palette.taupe, palette.charcoal],
    sizes: clothingSizes,
    images: ["model-crop", "cat-crop"],
    material: "بافت ریب با نخ ویسکوز",
    description:
      "قد کوتاه با لبه‌ی کشی؛ روی شورت فاق‌بلند و دامن ماکسی هر دو خوش می‌نشیند.",
    isNew: true,
  },
  {
    name: "کراپ‌تاپ آستین‌پفی رها",
    category: "crop",
    price: 780000,
    oldPrice: 950000,
    colors: [palette.offwhite, palette.sand],
    sizes: clothingSizes,
    images: ["cat-crop", "model-crop"],
    material: "پنبه استرچ",
    description: "آستین حجم‌دار کوتاه و یقه‌ی قاشقی؛ جزئیاتی کلاسیک با فرم امروزی.",
  },
  {
    name: "کراپ‌تاپ بندی نیلا",
    category: "crop",
    price: 640000,
    colors: [palette.taupe, palette.cream],
    sizes: clothingSizes,
    images: ["cat-crop", "model-crop"],
    material: "جرسی پنبه‌ای",
    description: "بندهای قابل تنظیم و پشت ساده؛ سبک برای روزهای گرم.",
  },
  {
    name: "کراپ‌تاپ یقه‌قایقی سانا",
    category: "crop",
    price: 690000,
    colors: [palette.cream, palette.charcoal],
    sizes: clothingSizes,
    images: ["model-crop", "cat-crop"],
    material: "ریب نرم",
    description: "یقه‌ی باز افقی که خط شانه را کشیده نشان می‌دهد.",
  },
  {
    name: "شورت کتان پیلی‌دار هلیا",
    category: "shorts",
    price: 980000,
    colors: [palette.sand, palette.cream, palette.charcoal],
    sizes: clothingSizes,
    images: ["cat-shorts", "model-crop"],
    material: "کتان و پنبه، آستر ندارد",
    description:
      "فاق بلند با دو پیلی جلو و جیب مورب؛ خطی رسمی با راحتی پارچه‌ی نفس‌گیر.",
    isNew: true,
  },
  {
    name: "شورت راحتی کشی سوگل",
    category: "shorts",
    price: 620000,
    colors: [palette.cream, palette.taupe],
    sizes: clothingSizes,
    images: ["cat-shorts", "cat-set"],
    material: "پنبه‌ی حلقوی",
    description: "کمر کشی با بند تنظیم؛ برای خانه و پیاده‌روی‌های کوتاه.",
  },
  {
    name: "شورت جین کوتاه بهار",
    category: "shorts",
    price: 1120000,
    oldPrice: 1350000,
    colors: [palette.sand, palette.charcoal],
    sizes: clothingSizes,
    images: ["cat-shorts", "model-crop"],
    material: "دنیم سبک ۱۱ اونس",
    description: "برش صاف با لبه‌ی تاشو و دوخت متضاد؛ کلاسیکی که کهنه نمی‌شود.",
  },
  {
    name: "شورت کتان بغل‌چاک آرمیتا",
    category: "shorts",
    price: 890000,
    colors: [palette.cream, palette.sand],
    sizes: clothingSizes,
    images: ["cat-shorts", "cat-set"],
    material: "کتان خالص",
    description: "چاک کوتاه کناری برای آزادی حرکت و افت بهتر پارچه.",
  },
  {
    name: "جوراب نخی ساق‌کوتاه (سه‌جفت)",
    category: "socks",
    price: 320000,
    colors: [palette.cream, palette.sand, palette.charcoal],
    sizes: sockSizes,
    images: ["cat-socks", "cat-socks"],
    material: "۸۰٪ پنبه، ۱۷٪ پلی‌آمید، ۳٪ الاستان",
    description: "کف حوله‌ای نرم و لبه‌ی بدون اثر؛ بسته‌ی سه‌جفتی در رنگ‌های خنثی.",
  },
  {
    name: "جوراب ساق‌بلند ریب مه",
    category: "socks",
    price: 240000,
    colors: [palette.cream, palette.taupe],
    sizes: sockSizes,
    images: ["cat-socks", "cat-socks"],
    material: "پنبه ریب",
    description: "ساق تا نیمه‌ی ساق پا با کشی ملایم که پایین نمی‌آید.",
    isNew: true,
  },
  {
    name: "جوراب مچی نامرئی (پنج‌جفت)",
    category: "socks",
    price: 380000,
    oldPrice: 450000,
    colors: [palette.offwhite, palette.sand],
    sizes: sockSizes,
    images: ["cat-socks", "cat-socks"],
    material: "پنبه با سیلیکون پاشنه",
    description: "زیر کفش‌های تخت دیده نمی‌شود و پاشنه‌ی سیلیکونی سرنمی‌خورد.",
  },
  {
    name: "جوراب پشمی گرم زمستان",
    category: "socks",
    price: 430000,
    colors: [palette.taupe, palette.charcoal],
    sizes: sockSizes,
    images: ["cat-socks", "cat-socks"],
    material: "مرینوس و پنبه",
    description: "بافت ضخیم و گرم بدون خارش؛ برای روزهای سرد خانه.",
  },
  {
    name: "ست کراپ و شورت شنی",
    category: "set",
    price: 1650000,
    oldPrice: 1980000,
    colors: [palette.sand, palette.cream],
    sizes: clothingSizes,
    images: ["cat-set", "model-crop"],
    material: "ویسکوز و کتان",
    description: "ست دوتکه‌ی هم‌رنگ؛ با هم یا جدا از هم قابل استایل کردن.",
    isNew: true,
  },
  {
    name: "ست تی‌شرت و شورت خانه",
    category: "set",
    price: 1380000,
    colors: [palette.cream, palette.taupe],
    sizes: clothingSizes,
    images: ["cat-set", "cat-tshirt"],
    material: "پنبه‌ی نرم",
    description: "دوتکه‌ی راحت با دوخت تمیز؛ سبک و خنک برای خانه.",
  },
  {
    name: "ست لانژ آستین‌بلند نسیم",
    category: "set",
    price: 1890000,
    colors: [palette.sand, palette.charcoal],
    sizes: clothingSizes,
    images: ["cat-set", "model-tshirt"],
    material: "ویسکوز مات",
    description: "پیراهن یقه‌برگردان و شلوار کمر کشی با افت روان.",
  },
  {
    name: "ست بافت ریب دوتکه رزا",
    category: "set",
    price: 1740000,
    colors: [palette.cream, palette.sand],
    sizes: clothingSizes,
    images: ["cat-set", "cat-crop"],
    material: "ریب کشباف",
    description: "کراپ ریب همراه شورت هم‌بافت؛ ترکیبی مدرن با حس کلاسیک.",
  },
];

export const products: Product[] = seeds.map((seed, index) => ({
  ...seed,
  id: `${seed.category}-${index + 1}`,
}));

export const getProduct = (id: string) => products.find((p) => p.id === id);

export const allSizes = Array.from(new Set(products.flatMap((p) => p.sizes)));

export const allColors = Array.from(
  new Map(products.flatMap((p) => p.colors).map((c) => [c.name, c])).values(),
);

export const priceBounds = {
  min: Math.min(...products.map((p) => p.price)),
  max: Math.max(...products.map((p) => p.price)),
};