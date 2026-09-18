import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, Star, Trash2, Upload } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { PRODUCT_BUCKET, resolveImageUrls } from "@/lib/catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = {
  value: string[];
  onChange: (images: string[]) => void;
};

export function ProductImageManager({ value, onChange }: Props) {
  const [previews, setPreviews] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    resolveImageUrls(value)
      .then((urls) => {
        if (alive) setPreviews(urls);
      })
      .catch(() => {
        if (alive) setPreviews([]);
      });
    return () => {
      alive = false;
    };
  }, [value.join("|")]);

  const move = (index: number, delta: number) => {
    const next = [...value];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item!);
    onChange(next);
  };

  const upload = async (files: FileList) => {
    setUploading(true);
    const added: string[] = [];
    try {
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) {
          toast.error(`${file.name} تصویر نیست`);
          continue;
        }
        if (file.size > 5 * 1024 * 1024) {
          toast.error(`${file.name} بزرگ‌تر از ۵ مگابایت است`);
          continue;
        }
        const extension = file.name.split(".").pop()?.toLowerCase() || "jpg";
        const path = `uploads/${crypto.randomUUID()}.${extension}`;
        const { error } = await supabase.storage
          .from(PRODUCT_BUCKET)
          .upload(path, file, { contentType: file.type, upsert: false });
        if (error) throw error;
        added.push(path);
      }
      if (added.length) {
        onChange([...value, ...added]);
        toast.success("تصویر آپلود شد");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "آپلود انجام نشد");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {value.map((reference, index) => (
          <div
            key={`${reference}-${index}`}
            className="relative w-28 overflow-hidden rounded-2xl border border-border bg-background"
          >
            <img
              src={previews[index]}
              alt=""
              className="h-32 w-full object-cover"
              loading="lazy"
            />
            {index === 0 && (
              <span className="absolute top-1 right-1 flex items-center gap-1 rounded-full bg-terracotta px-2 py-0.5 text-[10px] text-background">
                <Star className="size-3" /> اصلی
              </span>
            )}
            <div className="flex items-center justify-between border-t border-border px-1 py-1">
              <button
                type="button"
                aria-label="جابه‌جایی به راست"
                onClick={() => move(index, -1)}
                className="p-1 text-muted-foreground hover:text-foreground"
              >
                <ChevronRight className="size-4" />
              </button>
              <button
                type="button"
                aria-label="حذف تصویر"
                onClick={() => onChange(value.filter((_, i) => i !== index))}
                className="p-1 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="size-4" />
              </button>
              <button
                type="button"
                aria-label="جابه‌جایی به چپ"
                onClick={() => move(index, 1)}
                className="p-1 text-muted-foreground hover:text-foreground"
              >
                <ChevronLeft className="size-4" />
              </button>
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="flex h-[164px] w-28 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border text-xs text-muted-foreground transition-colors hover:border-terracotta hover:text-terracotta"
        >
          <Upload className="size-5" />
          {uploading ? "در حال آپلود…" : "آپلود تصویر"}
        </button>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(event) => {
          const files = event.target.files;
          if (files && files.length) void upload(files);
        }}
      />

      <div className="flex gap-2">
        <Input
          dir="ltr"
          value={urlDraft}
          onChange={(event) => setUrlDraft(event.target.value)}
          placeholder="یا نشانی تصویر را وارد کنید"
          className="bg-background"
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            const reference = urlDraft.trim();
            if (!reference) return;
            onChange([...value, reference]);
            setUrlDraft("");
          }}
        >
          افزودن
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        اولین تصویر، تصویر اصلی محصول است. تصویر دوم روی کارت محصول با حرکت موس نمایش داده
        می‌شود.
      </p>
    </div>
  );
}
