"""Seed the 20-product starter catalog (idempotent).

The catalog is the same 20 products as `infra/initdb/02-public-schema.sql`, which
is the schema the compose stack creates; `vogue-vintage-vibes/src/data/products.ts`
still mirrors it on the frontend. Keeping this as a backend seed (rather than only
in the initdb SQL) means a database that was not created by the compose initdb —
e.g. one pointed at directly via `DATABASE_URL` — still gets the same catalog.

Run from backend/:
    python -m app.seed_products
Requires DATABASE_URL only. Re-runnable: existing ids are left untouched except
that rows with no `tags` yet get the tags below backfilled (so a database seeded
before tags existed starts matching `GET /search?q=<tag>`).
"""

import asyncio
import json

from sqlalchemy import text

from app.db import engine, startup_ddl

TSHIRT_SIZES = ["XS", "S", "M", "L", "XL"]
SOCK_SIZES = ["36-38", "39-41", "42-44"]

_CREAM = {"name": "کرم", "hex": "#f0ebe3"}
_SAND = {"name": "شنی", "hex": "#c9b99a"}
_TAUPE = {"name": "قهوه‌ای روشن", "hex": "#8b7355"}
_CHARCOAL = {"name": "زغالی", "hex": "#3a352f"}
_OFFWHITE = {"name": "سفید شکسته", "hex": "#faf8f5"}

PRODUCTS: list[dict] = [
    {
        "id": "tshirt-1",
        "name": "تی‌شرت اورسایز پنبه‌ای مینا",
        "tags": ["اورسایز", "پنبه", "روزمره"],
        "category": "tshirt",
        "price": 690_000,
        "old_price": 890_000,
        "colors": [_OFFWHITE, _SAND, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["model-tshirt", "cat-tshirt"],
        "material": "۱۰۰٪ پنبه پنبه‌ریز، گرماژ ۱۸۰",
        "description": (
            "برشی آزاد و افتاده با یقه گرد دوخت‌دوبل؛ انتخابی آرام برای هر روز که "
            "فرم خود را پس از شست‌وشو حفظ می‌کند."
        ),
        "is_new": True,
    },
    {
        "id": "tshirt-2",
        "name": "تی‌شرت جادار روزمره نارین",
        "tags": ["جادار", "ویسکوز", "روزمره"],
        "category": "tshirt",
        "price": 540_000,
        "old_price": None,
        "colors": [_CREAM, _TAUPE],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-tshirt", "model-tshirt"],
        "material": "پنبه و ویسکوز، لطیف و خنک",
        "description": (
            "پارچه‌ای سبک با درز کناری تمیز؛ زیر کت و بلیزر عالی می‌نشیند و در تنه "
            "کشیدگی ندارد."
        ),
        "is_new": False,
    },
    {
        "id": "tshirt-3",
        "name": "تی‌شرت یقه‌گرد کلاسیک ورا",
        "tags": ["کلاسیک", "پنبه", "روزمره"],
        "category": "tshirt",
        "price": 620_000,
        "old_price": None,
        "colors": [_OFFWHITE, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["model-tshirt", "cat-tshirt"],
        "material": "پنبه شانه‌زده",
        "description": "خط شانه‌ی دقیق و آستین کوتاه استاندارد؛ پایه‌ای که هر فصل به کار می‌آید.",
        "is_new": False,
    },
    {
        "id": "tshirt-4",
        "tags": ["ریب", "پنبه", "روزمره"],
        "name": "تی‌شرت آستین‌کوتاه ریب لینا",
        "category": "tshirt",
        "price": 580_000,
        "old_price": None,
        "colors": [_SAND, _CREAM],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-tshirt", "model-crop"],
        "material": "ریب پنبه‌ای کشی",
        "description": "بافت ریب باریک با کشش ملایم که بدن را نرم قالب می‌گیرد.",
        "is_new": False,
    },
    {
        "id": "crop-5",
        "name": "کراپ‌تاپ بافت ریب آوا",
        "tags": ["ریب", "تابستانی", "روزمره"],
        "category": "crop",
        "price": 720_000,
        "old_price": None,
        "colors": [_CREAM, _TAUPE, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["model-crop", "cat-crop"],
        "material": "بافت ریب با نخ ویسکوز",
        "description": "قد کوتاه با لبه‌ی کشی؛ روی شورت فاق‌بلند و دامن ماکسی هر دو خوش می‌نشیند.",
        "is_new": True,
    },
    {
        "id": "crop-6",
        "name": "کراپ‌تاپ آستین‌پفی رها",
        "tags": ["پفی", "مجلسی", "تابستانی"],
        "category": "crop",
        "price": 780_000,
        "old_price": 950_000,
        "colors": [_OFFWHITE, _SAND],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-crop", "model-crop"],
        "material": "پنبه استرچ",
        "description": "آستین حجم‌دار کوتاه و یقه‌ی قاشقی؛ جزئیاتی کلاسیک با فرم امروزی.",
        "is_new": False,
    },
    {
        "id": "crop-7",
        "name": "کراپ‌تاپ بندی نیلا",
        "tags": ["بنددار", "تابستانی", "روزمره"],
        "category": "crop",
        "price": 640_000,
        "old_price": None,
        "colors": [_TAUPE, _CREAM],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-crop", "model-crop"],
        "material": "جرسی پنبه‌ای",
        "description": "بندهای قابل تنظیم و پشت ساده؛ سبک برای روزهای گرم.",
        "is_new": False,
    },
    {
        "id": "crop-8",
        "name": "کراپ‌تاپ یقه‌قایقی سانا",
        "tags": ["کلاسیک", "مجلسی"],
        "category": "crop",
        "price": 690_000,
        "old_price": None,
        "colors": [_CREAM, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["model-crop", "cat-crop"],
        "material": "ریب نرم",
        "description": "یقه‌ی باز افقی که خط شانه را کشیده نشان می‌دهد.",
        "is_new": False,
    },
    {
        "id": "shorts-9",
        "name": "شورت کتان پیلی‌دار هلیا",
        "tags": ["کتان", "پیلی‌دار", "مجلسی"],
        "category": "shorts",
        "price": 980_000,
        "old_price": None,
        "colors": [_SAND, _CREAM, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-shorts", "model-crop"],
        "material": "کتان و پنبه، آستر ندارد",
        "description": "فاق بلند با دو پیلی جلو و جیب مورب؛ خطی رسمی با راحتی پارچه‌ی نفس‌گیر.",
        "is_new": True,
    },
    {
        "id": "shorts-10",
        "name": "شورت راحتی کشی سوگل",
        "tags": ["خانگی", "پنبه", "روزمره"],
        "category": "shorts",
        "price": 620_000,
        "old_price": None,
        "colors": [_CREAM, _TAUPE],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-shorts", "cat-set"],
        "material": "پنبه‌ی حلقوی",
        "description": "کمر کشی با بند تنظیم؛ برای خانه و پیاده‌روی‌های کوتاه.",
        "is_new": False,
    },
    {
        "id": "shorts-11",
        "name": "شورت جین کوتاه بهار",
        "tags": ["دنیم", "تابستانی", "کلاسیک"],
        "category": "shorts",
        "price": 1_120_000,
        "old_price": 1_350_000,
        "colors": [_SAND, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-shorts", "model-crop"],
        "material": "دنیم سبک ۱۱ اونس",
        "description": "برش صاف با لبه‌ی تاشو و دوخت متضاد؛ کلاسیکی که کهنه نمی‌شود.",
        "is_new": False,
    },
    {
        "id": "shorts-12",
        "name": "شورت کتان بغل‌چاک آرمیتا",
        "tags": ["کتان", "تابستانی", "ساحلی"],
        "category": "shorts",
        "price": 890_000,
        "old_price": None,
        "colors": [_CREAM, _SAND],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-shorts", "cat-set"],
        "material": "کتان خالص",
        "description": "چاک کوتاه کناری برای آزادی حرکت و افت بهتر پارچه.",
        "is_new": False,
    },
    {
        "id": "socks-13",
        "name": "جوراب نخی ساق‌کوتاه (سه‌جفت)",
        "tags": ["پنبه", "روزمره"],
        "category": "socks",
        "price": 320_000,
        "old_price": None,
        "colors": [_CREAM, _SAND, _CHARCOAL],
        "sizes": SOCK_SIZES,
        "images": ["cat-socks", "cat-socks"],
        "material": "۸۰٪ پنبه، ۱۷٪ پلی‌آمید، ۳٪ الاستان",
        "description": "کف حوله‌ای نرم و لبه‌ی بدون اثر؛ بسته‌ی سه‌جفتی در رنگ‌های خنثی.",
        "is_new": False,
    },
    {
        "id": "socks-14",
        "name": "جوراب ساق‌بلند ریب مه",
        "tags": ["ریب", "پنبه", "روزمره"],
        "category": "socks",
        "price": 240_000,
        "old_price": None,
        "colors": [_CREAM, _TAUPE],
        "sizes": SOCK_SIZES,
        "images": ["cat-socks", "cat-socks"],
        "material": "پنبه ریب",
        "description": "ساق تا نیمه‌ی ساق پا با کشی ملایم که پایین نمی‌آید.",
        "is_new": True,
    },
    {
        "id": "socks-15",
        "name": "جوراب مچی نامرئی (پنج‌جفت)",
        "tags": ["پنبه", "نامرئی", "تابستانی"],
        "category": "socks",
        "price": 380_000,
        "old_price": 450_000,
        "colors": [_OFFWHITE, _SAND],
        "sizes": SOCK_SIZES,
        "images": ["cat-socks", "cat-socks"],
        "material": "پنبه با سیلیکون پاشنه",
        "description": "زیر کفش‌های تخت دیده نمی‌شود و پاشنه‌ی سیلیکونی سرنمی‌خورد.",
        "is_new": False,
    },
    {
        "id": "socks-16",
        "name": "جوراب پشمی گرم زمستان",
        "tags": ["پشمی", "مرینوس", "زمستانی"],
        "category": "socks",
        "price": 430_000,
        "old_price": None,
        "colors": [_TAUPE, _CHARCOAL],
        "sizes": SOCK_SIZES,
        "images": ["cat-socks", "cat-socks"],
        "material": "مرینوس و پنبه",
        "description": "بافت ضخیم و گرم بدون خارش؛ برای روزهای سرد خانه.",
        "is_new": False,
    },
    {
        "id": "set-17",
        "name": "ست کراپ و شورت شنی",
        "tags": ["کتان", "ویسکوز", "تابستانی"],
        "category": "set",
        "price": 1_650_000,
        "old_price": 1_980_000,
        "colors": [_SAND, _CREAM],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-set", "model-crop"],
        "material": "ویسکوز و کتان",
        "description": "ست دوتکه‌ی هم‌رنگ؛ با هم یا جدا از هم قابل استایل کردن.",
        "is_new": True,
    },
    {
        "id": "set-18",
        "name": "ست تی‌شرت و شورت خانه",
        "tags": ["خانگی", "پنبه", "روزمره"],
        "category": "set",
        "price": 1_380_000,
        "old_price": None,
        "colors": [_CREAM, _TAUPE],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-set", "cat-tshirt"],
        "material": "پنبه‌ی نرم",
        "description": "دوتکه‌ی راحت با دوخت تمیز؛ سبک و خنک برای خانه.",
        "is_new": False,
    },
    {
        "id": "set-19",
        "name": "ست لانژ آستین‌بلند نسیم",
        "tags": ["لانژ", "ویسکوز", "خانگی"],
        "category": "set",
        "price": 1_890_000,
        "old_price": None,
        "colors": [_SAND, _CHARCOAL],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-set", "model-tshirt"],
        "material": "ویسکوز مات",
        "description": "پیراهن یقه‌برگردان و شلوار کمر کشی با افت روان.",
        "is_new": False,
    },
    {
        "id": "set-20",
        "name": "ست بافت ریب دوتکه رزا",
        "tags": ["ریب", "کلاسیک", "روزمره"],
        "category": "set",
        "price": 1_740_000,
        "old_price": None,
        "colors": [_CREAM, _SAND],
        "sizes": TSHIRT_SIZES,
        "images": ["cat-set", "cat-crop"],
        "material": "ریب کشباف",
        "description": "کراپ ریب همراه شورت هم‌بافت؛ ترکیبی مدرن با حس کلاسیک.",
        "is_new": False,
    },
]

_INSERT = text(
    "INSERT INTO public.products "
    "(id, name, category, price, old_price, sizes, colors, images, "
    " material, description, is_new, stock, active, tags) "
    "VALUES (:id, :name, :category, :price, :old_price, CAST(:sizes AS text[]), "
    "        CAST(:colors AS jsonb), CAST(:images AS text[]), :material, "
    "        :description, :is_new, 25, true, CAST(:tags AS text[])) "
    # Backfill tags only where the row has none, so an admin's own tags survive a re-run.
    "ON CONFLICT (id) DO UPDATE SET tags = EXCLUDED.tags "
    "WHERE public.products.tags = '{}'::text[]"
)


async def main() -> None:
    # `tags` is an additive column owned by the startup DDL, not by infra/initdb.
    await startup_ddl()
    async with engine.begin() as conn:
        for product in PRODUCTS:
            await conn.execute(
                _INSERT,
                {
                    **product,
                    "sizes": product["sizes"],
                    "colors": json.dumps(product["colors"], ensure_ascii=False),
                    "images": product["images"],
                    "tags": product["tags"],
                },
            )
    print(
        f"seeded: {len(PRODUCTS)} starter products "
        "(existing ids untouched, tags backfilled where empty)"
    )


if __name__ == "__main__":
    asyncio.run(main())
