import { Link } from "@tanstack/react-router";
import { categories } from "@/data/products";

export function SiteFooter() {
  return (
    <footer className="surface-courtyard mt-24 border-t-2 border-terracotta/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-3">
        <div>
          <p className="font-display text-2xl tracking-[0.22em] text-terracotta">SÂNDÉ</p>
          <p className="mt-3 max-w-xs text-sm leading-7 text-muted-foreground">
            لباس‌های ساده و بادوام برای روزهای معمولی؛ رنگ‌های خنثی، پارچه‌های طبیعی و برش‌هایی
            که کهنه نمی‌شوند.
          </p>
        </div>

        <div className="text-sm">
          <p className="mb-4 text-xs tracking-[0.2em] text-sage-deep">دسته‌ها</p>
          <ul className="space-y-2">
            {categories.map((c) => (
              <li key={c.id}>
                <Link
                  to="/shop"
                  search={{ category: c.id }}
                  className="text-foreground/80 transition-colors hover:text-terracotta"
                >
                  {c.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="text-sm">
          <p className="mb-4 text-xs tracking-[0.2em] text-sage-deep">راهنما</p>
          <ul className="space-y-2 text-foreground/80">
            <li>
              <Link to="/about" className="hover:text-terracotta">
                درباره ما
              </Link>
            </li>
            <li>
              <Link to="/contact" className="hover:text-terracotta">
                تماس با ما
              </Link>
            </li>
            <li>ارسال رایگان برای خرید بالای ۲٫۰۰۰٫۰۰۰ تومان</li>
            <li>۷ روز مهلت تعویض سایز</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border/70 py-5 text-center text-xs text-muted-foreground">
        © ۱۴۰۵ ساندِه — تمام حقوق محفوظ است.
      </div>
    </footer>
  );
}