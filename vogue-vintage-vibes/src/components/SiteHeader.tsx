import { Link } from "@tanstack/react-router";
import { Menu, Search, ShoppingBag, User, X } from "lucide-react";
import { useState } from "react";
import { useCart } from "@/lib/cart";
import { toFa } from "@/lib/format";
import { categories } from "@/data/products";

const navLinks = [
  { to: "/", label: "خانه" },
  { to: "/shop", label: "فروشگاه" },
  { to: "/about", label: "درباره ما" },
  { to: "/contact", label: "تماس" },
] as const;

export function SiteHeader() {
  const { count } = useCart();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-terracotta/25 bg-background/85 backdrop-blur-md">
      <div className="surface-warm h-1 w-full" />
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label="فهرست"
          className="text-foreground/70 transition-colors hover:text-foreground md:hidden"
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>

        <Link to="/" className="font-display text-2xl tracking-[0.22em] text-terracotta">
          SÂNDÉ
        </Link>

        <nav className="hidden items-center gap-8 text-sm md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              activeOptions={{ exact: link.to === "/" }}
              className="text-muted-foreground transition-colors hover:text-terracotta"
              activeProps={{ className: "text-terracotta" }}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-4">
          <Link
            to="/shop"
            aria-label="جستجو در محصولات"
            className="text-foreground/70 transition-colors hover:text-foreground"
          >
            <Search className="size-5" />
          </Link>
          <Link
            to="/account"
            aria-label="حساب کاربری"
            className="text-foreground/70 transition-colors hover:text-foreground"
          >
            <User className="size-5" />
          </Link>
          <Link
            to="/cart"
            aria-label="سبد خرید"
            className="relative text-foreground/70 transition-colors hover:text-foreground"
          >
            <ShoppingBag className="size-5" />
            {count > 0 && (
              <span className="absolute -top-2 -left-2 flex size-4.5 items-center justify-center rounded-full bg-primary text-[10px] text-primary-foreground">
                {toFa(count)}
              </span>
            )}
          </Link>
        </div>
      </div>

      {open && (
        <div className="border-t border-border/70 bg-background px-4 pb-5 pt-3 md:hidden">
          <nav className="flex flex-col gap-3 text-sm">
            {navLinks.map((link) => (
              <Link key={link.to} to={link.to} onClick={() => setOpen(false)}>
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="mt-4 flex flex-wrap gap-2">
            {categories.map((c) => (
              <Link
                key={c.id}
                to="/shop"
                search={{ category: c.id }}
                onClick={() => setOpen(false)}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground"
              >
                {c.title}
              </Link>
            ))}
          </div>
        </div>
      )}
    </header>
  );
}