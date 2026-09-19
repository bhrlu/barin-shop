import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Product } from "@/data/products";
import { ProductCard } from "@/components/ProductCard";
import { Button } from "@/components/ui/button";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  type CarouselApi,
} from "@/components/ui/carousel";

/** Horizontal product rail ("محصولات مرتبط" / "پیشنهاد برای شما") built on the shadcn carousel. */
export function ProductRail({
  title,
  eyebrow,
  products,
}: {
  title: string;
  eyebrow?: string;
  products: Product[];
}) {
  const [api, setApi] = useState<CarouselApi>();
  const [scrollable, setScrollable] = useState({ prev: false, next: false });

  useEffect(() => {
    if (!api) return;
    const update = () => setScrollable({ prev: api.canScrollPrev(), next: api.canScrollNext() });
    update();
    api.on("select", update);
    api.on("reInit", update);
    return () => {
      api.off("select", update);
      api.off("reInit", update);
    };
  }, [api]);

  if (products.length === 0) return null;

  return (
    <section className="mt-20">
      <div className="flex items-end justify-between gap-4">
        <div>
          {eyebrow && <p className="text-[11px] tracking-[0.2em] text-sage-deep">{eyebrow}</p>}
          <h2 className="mt-1 text-2xl">{title}</h2>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label="محصول قبلی"
            disabled={!scrollable.prev}
            onClick={() => api?.scrollPrev()}
          >
            <ChevronRight className="size-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label="محصول بعدی"
            disabled={!scrollable.next}
            onClick={() => api?.scrollNext()}
          >
            <ChevronLeft className="size-4" />
          </Button>
        </div>
      </div>

      <Carousel
        className="mt-6"
        opts={{ direction: "rtl", align: "start", containScroll: "trimSnaps" }}
        setApi={setApi}
      >
        {/* the primitive pads items on the left; in RTL the strip needs its gutter on the right */}
        <CarouselContent className="ml-0 -mr-4">
          {products.map((product) => (
            <CarouselItem key={product.id} className="basis-1/2 lg:basis-1/3">
              <ProductCard product={product} />
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>
    </section>
  );
}
