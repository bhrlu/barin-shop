import { useEffect, useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  ImageOff,
  RotateCcw,
  Star,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { resolveImageMap } from "@/lib/catalog";
import { toFa } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = {
  value: string[];
  onChange: (images: string[]) => void;
  /** true while a file is queued or uploading — the form should not save yet */
  onBusyChange?: (busy: boolean) => void;
};

/** A file on its way to storage; it joins `value` only once the upload succeeded. */
type PendingUpload = {
  id: number;
  file: File;
  preview: string; // object URL of the local file
  progress: number; // 0–1
  status: "queued" | "uploading" | "error";
  error?: string | undefined;
};

const MAX_BYTES = 5 * 1024 * 1024;
// what `POST /storage/upload-url` accepts (jpg/jpeg/png/webp/gif/avif)
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"];
const REORDER_TYPE = "application/x-sande-image-index";

/**
 * Product gallery (AB-FE-04): drop or pick files, watch each upload's progress, retry a
 * failed one, drag tiles (or use the arrows) to reorder, and pick the primary image —
 * always `value[0]`. Uploads go straight to MinIO via `api.uploadImage`; the product
 * row changes only when the form is saved.
 */
export function ProductImageManager({ value, onChange, onBusyChange }: Props) {
  // signed/resolved URL per reference, so a reorder neither re-signs nor flashes
  const [urls, setUrls] = useState<Map<string, string>>(() => new Map());
  const [broken, setBroken] = useState<Set<string>>(() => new Set());
  const [pending, setPending] = useState<PendingUpload[]>([]);
  const [dropActive, setDropActive] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [urlDraft, setUrlDraft] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const nextId = useRef(1);
  const objectUrls = useRef<Set<string>>(new Set());
  // an upload finishes long after the render that started it: append to the latest list
  const latest = useRef({ value, onChange });
  useEffect(() => {
    latest.current = { value, onChange };
  });

  useEffect(() => {
    const missing = value.filter((reference) => !urls.has(reference));
    if (!missing.length) return;
    let alive = true;
    resolveImageMap(missing)
      .then((map) => {
        if (alive) setUrls((previous) => new Map([...previous, ...map]));
      })
      .catch(() => {
        if (alive) setBroken((previous) => new Set([...previous, ...missing]));
      });
    return () => {
      alive = false;
    };
  }, [value, urls]);

  useEffect(() => {
    const created = objectUrls.current;
    return () => created.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const busy = pending.some((item) => item.status !== "error");
  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  // one upload at a time, in the order the files were added
  useEffect(() => {
    if (pending.some((item) => item.status === "uploading")) return;
    const next = pending.find((item) => item.status === "queued");
    if (!next) return;
    const update = (patch: Partial<PendingUpload>) =>
      setPending((items) =>
        items.map((item) => (item.id === next.id ? { ...item, ...patch } : item)),
      );
    update({ status: "uploading", progress: 0, error: undefined });
    api
      .uploadImage(next.file, (progress) => update({ progress }))
      .then((path) => {
        setUrls((previous) => new Map(previous).set(path, next.preview));
        latest.current.onChange([...latest.current.value, path]);
        setPending((items) => items.filter((item) => item.id !== next.id));
      })
      .catch((error: unknown) =>
        update({
          status: "error",
          error: error instanceof Error && error.message ? error.message : "آپلود انجام نشد",
        }),
      );
  }, [pending]);

  const addFiles = (files: File[]) => {
    const accepted: PendingUpload[] = [];
    for (const file of files) {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        toast.error(`${file.name}: فقط JPG، PNG، WEBP، GIF یا AVIF`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        toast.error(`${file.name} بزرگ‌تر از ۵ مگابایت است`);
        continue;
      }
      const preview = URL.createObjectURL(file);
      objectUrls.current.add(preview);
      accepted.push({ id: nextId.current++, file, preview, progress: 0, status: "queued" });
    }
    if (accepted.length) setPending((items) => [...items, ...accepted]);
  };

  const retry = (id: number) =>
    setPending((items) =>
      items.map((item) =>
        item.id === id ? { ...item, status: "queued", progress: 0, error: undefined } : item,
      ),
    );
  const dismiss = (id: number) => setPending((items) => items.filter((item) => item.id !== id));

  const moveTo = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= value.length || to >= value.length) return;
    const next = [...value];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item!);
    onChange(next);
  };

  const isFileDrag = (event: DragEvent) => event.dataTransfer.types.includes("Files");
  const isTileDrag = (event: DragEvent) => event.dataTransfer.types.includes(REORDER_TYPE);
  const endDrag = () => {
    setDragIndex(null);
    setOverIndex(null);
  };

  return (
    <div className="space-y-4">
      <div
        role="list"
        aria-label="تصاویر محصول"
        onDragOver={(event) => {
          if (!isFileDrag(event)) return;
          event.preventDefault();
          event.dataTransfer.dropEffect = "copy";
          setDropActive(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setDropActive(false);
          }
        }}
        onDrop={(event) => {
          if (!isFileDrag(event)) return;
          event.preventDefault();
          setDropActive(false);
          addFiles(Array.from(event.dataTransfer.files));
        }}
        className={`flex flex-wrap gap-3 rounded-2xl p-1 transition-colors ${
          dropActive
            ? "bg-terracotta/5 outline-dashed outline-2 outline-offset-2 outline-terracotta/60"
            : ""
        }`}
      >
        {value.map((reference, index) => (
          <div
            key={`${reference}-${index}`}
            role="listitem"
            aria-label={index === 0 ? "تصویر اصلی" : `تصویر ${toFa(index + 1)}`}
            draggable
            onDragStart={(event) => {
              event.dataTransfer.setData(REORDER_TYPE, String(index));
              event.dataTransfer.effectAllowed = "move";
              setDragIndex(index);
            }}
            onDragOver={(event) => {
              if (!isTileDrag(event)) return;
              event.preventDefault();
              event.dataTransfer.dropEffect = "move";
              setOverIndex(index);
            }}
            onDrop={(event) => {
              if (!isTileDrag(event)) return;
              event.preventDefault();
              event.stopPropagation();
              moveTo(Number(event.dataTransfer.getData(REORDER_TYPE)), index);
              endDrag();
            }}
            onDragEnd={endDrag}
            className={`relative w-28 cursor-grab overflow-hidden rounded-2xl border bg-background transition ${
              overIndex === index && dragIndex !== index
                ? "border-terracotta ring-2 ring-terracotta/40"
                : "border-border"
            } ${dragIndex === index ? "opacity-40" : ""}`}
          >
            {broken.has(reference) || !urls.has(reference) ? (
              <div className="flex h-32 w-full flex-col items-center justify-center gap-1 bg-secondary/50 text-[10px] text-muted-foreground">
                {broken.has(reference) ? (
                  <>
                    <ImageOff className="size-5" aria-hidden />
                    پیش‌نمایش در دسترس نیست
                  </>
                ) : (
                  <span className="h-full w-full animate-pulse bg-clay" />
                )}
              </div>
            ) : (
              <img
                src={urls.get(reference)}
                alt=""
                draggable={false}
                onError={() => setBroken((previous) => new Set(previous).add(reference))}
                className="h-32 w-full object-cover"
                loading="lazy"
              />
            )}
            {index === 0 && (
              <span className="absolute top-1 right-1 flex items-center gap-1 rounded-full bg-terracotta px-2 py-0.5 text-[10px] text-background">
                <Star className="size-3" /> اصلی
              </span>
            )}
            <div className="flex items-center justify-between border-t border-border px-1 py-1">
              <button
                type="button"
                aria-label="جابه‌جایی به راست"
                onClick={() => moveTo(index, index - 1)}
                disabled={index === 0}
                className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
              >
                <ChevronRight className="size-4" />
              </button>
              {index > 0 ? (
                <button
                  type="button"
                  aria-label="انتخاب به‌عنوان تصویر اصلی"
                  title="تصویر اصلی شود"
                  onClick={() => moveTo(index, 0)}
                  className="p-1 text-muted-foreground hover:text-terracotta"
                >
                  <Star className="size-4" />
                </button>
              ) : null}
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
                onClick={() => moveTo(index, index + 1)}
                disabled={index === value.length - 1}
                className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-30"
              >
                <ChevronLeft className="size-4" />
              </button>
            </div>
          </div>
        ))}

        {pending.map((item) => (
          <div
            key={item.id}
            role="listitem"
            aria-label={`آپلود ${item.file.name}`}
            data-upload-status={item.status}
            className={`relative w-28 overflow-hidden rounded-2xl border bg-background ${
              item.status === "error" ? "border-destructive/60" : "border-border"
            }`}
          >
            <img
              src={item.preview}
              alt=""
              draggable={false}
              className="h-32 w-full object-cover opacity-60"
            />
            {item.status === "error" ? (
              <div className="absolute inset-x-0 top-0 flex h-32 flex-col items-center justify-center gap-1 bg-background/80 p-2 text-center text-[10px] text-destructive">
                <span role="alert">{item.error}</span>
              </div>
            ) : (
              <div className="absolute inset-x-0 top-0 flex h-32 flex-col items-center justify-end gap-1 p-2">
                <span className="rounded-full bg-background/90 px-2 py-0.5 text-[10px] text-foreground">
                  {item.status === "queued" ? "در صف" : `${toFa(Math.round(item.progress * 100))}٪`}
                </span>
                <div
                  role="progressbar"
                  aria-label={`پیشرفت آپلود ${item.file.name}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(item.progress * 100)}
                  className="h-1.5 w-full overflow-hidden rounded-full bg-background/80"
                >
                  <div
                    className="h-full rounded-full bg-terracotta transition-[width]"
                    style={{ width: `${Math.round(item.progress * 100)}%` }}
                  />
                </div>
              </div>
            )}
            <div className="flex items-center justify-center gap-2 border-t border-border px-1 py-1">
              {item.status === "error" ? (
                <>
                  <button
                    type="button"
                    aria-label="تلاش دوباره"
                    title="تلاش دوباره"
                    onClick={() => retry(item.id)}
                    className="p-1 text-muted-foreground hover:text-terracotta"
                  >
                    <RotateCcw className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="کنار گذاشتن"
                    title="کنار گذاشتن"
                    onClick={() => dismiss(item.id)}
                    className="p-1 text-muted-foreground hover:text-destructive"
                  >
                    <X className="size-4" />
                  </button>
                </>
              ) : (
                <span className="py-1 text-[10px] text-muted-foreground">در حال آپلود…</span>
              )}
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className={`flex h-[164px] w-28 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-2 text-center text-xs transition-colors ${
            dropActive
              ? "border-terracotta text-terracotta"
              : "border-border text-muted-foreground hover:border-terracotta hover:text-terracotta"
          }`}
        >
          <Upload className="size-5" />
          {dropActive ? "رها کنید" : "آپلود تصویر"}
          <span className="text-[10px] opacity-80">یا فایل را اینجا بکشید</span>
        </button>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        multiple
        hidden
        onChange={(event) => {
          const files = event.target.files;
          if (files && files.length) addFiles(Array.from(files));
          event.target.value = "";
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
        اولین تصویر، تصویر اصلی محصول است (با ستاره هر تصویر را اصلی کنید). تصویر دوم روی کارت محصول
        با حرکت موس نمایش داده می‌شود. برای تغییر ترتیب، کاشی‌ها را بکشید یا از فلش‌ها استفاده کنید.
        تغییرات با «ذخیره محصول» ثبت می‌شوند.
      </p>
    </div>
  );
}
