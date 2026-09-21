import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, type Address } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/account/addresses")({
  component: AddressesTab,
});

const empty = {
  title: "خانه",
  receiver: "",
  phone: "",
  province: "",
  city: "",
  postal_code: "",
  line: "",
};

type Draft = typeof empty;

const draftOf = (address: Address): Draft => ({
  title: address.title,
  receiver: address.receiver,
  phone: address.phone,
  province: address.province,
  city: address.city,
  postal_code: address.postal_code ?? "",
  line: address.line,
});

/**
 * The shared field set for the "new address" form and the inline edit form.
 * `prefix` keeps the label/input ids unique when both are on screen at once.
 */
function AddressFields({
  prefix,
  values,
  onChange,
}: {
  prefix: string;
  values: Draft;
  onChange: (values: Draft) => void;
}) {
  const field = (key: keyof Draft, label: string, required = true) => (
    <div>
      <Label htmlFor={`${prefix}-${key}`}>{label}</Label>
      <Input
        id={`${prefix}-${key}`}
        value={values[key]}
        required={required}
        onChange={(e) => onChange({ ...values, [key]: e.target.value })}
        className="mt-2 bg-background"
      />
    </div>
  );

  return (
    <>
      {field("title", "عنوان")}
      {field("receiver", "نام گیرنده")}
      {field("phone", "شماره تماس")}
      {field("province", "استان")}
      {field("city", "شهر")}
      {field("postal_code", "کد پستی", false)}
      {field("line", "نشانی کامل")}
    </>
  );
}

function AddressesTab() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(empty);
  const [makeDefault, setMakeDefault] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState(empty);

  const { data } = useQuery({
    queryKey: ["addresses"],
    queryFn: () => api.addresses(),
  });

  // the default address is what the checkout page pre-fills, so any change that
  // can move the flag must invalidate the cache the checkout reads
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["addresses"] });

  const create = useMutation({
    mutationFn: async () => api.createAddress({ ...form, is_default: makeDefault }),
    onSuccess: (address) => {
      setForm(empty);
      setMakeDefault(false);
      invalidate();
      toast.success(address.is_default ? "آدرس ثبت شد و پیش‌فرض شد" : "آدرس اضافه شد");
    },
    onError: () => toast.error("ثبت آدرس ناموفق بود"),
  });

  const edit = useMutation({
    // fields only: the patch carries no `is_default`, so saving an edit never
    // moves (or clears) the flag — that stays an explicit action below
    mutationFn: async () => {
      if (!editingId) throw new Error("آدرسی در حال ویرایش نیست");
      return api.updateAddress(editingId, draft);
    },
    onSuccess: () => {
      setEditingId(null);
      invalidate();
      toast.success("آدرس به‌روزرسانی شد");
    },
    onError: () => toast.error("ویرایش آدرس ناموفق بود"),
  });

  const setDefault = useMutation({
    mutationFn: async (id: string) => api.updateAddress(id, { is_default: true }),
    onSuccess: () => {
      invalidate();
      toast.success("آدرس پیش‌فرض تغییر کرد");
    },
    onError: () => toast.error("تغییر آدرس پیش‌فرض ناموفق بود"),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => api.deleteAddress(id),
    onSuccess: () => {
      setEditingId(null);
      invalidate();
    },
    onError: () => toast.error("حذف آدرس ناموفق بود"),
  });

  const startEdit = (address: Address) => {
    setEditingId(address.id);
    setDraft(draftOf(address));
  };

  return (
    <div className="grid gap-8 md:grid-cols-[1fr_360px]">
      <ul className="space-y-4">
        {(data ?? []).map((address) =>
          editingId === address.id ? (
            <li key={address.id} className="rounded-3xl border border-border p-5">
              <form
                className="space-y-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  edit.mutate();
                }}
              >
                <h2 className="flex items-center gap-2 text-sm">
                  ویرایش «{address.title}»
                  {address.is_default && (
                    <span className="bg-sand px-2 py-0.5 text-[11px] text-terracotta">پیش‌فرض</span>
                  )}
                </h2>
                <AddressFields prefix={address.id} values={draft} onChange={setDraft} />
                <div className="flex gap-2 pt-1">
                  <Button type="submit" disabled={edit.isPending} className="h-9 text-xs">
                    {edit.isPending ? "در حال ذخیره…" : "ذخیره تغییرات"}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setEditingId(null)}
                    className="h-9 text-xs"
                  >
                    انصراف
                  </Button>
                </div>
              </form>
            </li>
          ) : (
            <li key={address.id} className="rounded-3xl border border-border p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="flex items-center gap-2 text-sm">
                    {address.title}
                    {address.is_default && (
                      <span className="bg-sand px-2 py-0.5 text-[11px] text-terracotta">
                        پیش‌فرض
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {address.province}، {address.city} — {address.line}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
                    {address.receiver} · {address.phone}
                    {address.postal_code ? ` · ${address.postal_code}` : ""}
                  </p>
                  <div className="mt-3 flex items-center gap-4">
                    {!address.is_default && (
                      <button
                        type="button"
                        onClick={() => setDefault.mutate(address.id)}
                        disabled={setDefault.isPending}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                      >
                        <Star className="size-3.5" />
                        انتخاب به‌عنوان پیش‌فرض
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => startEdit(address)}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <Pencil className="size-3.5" />
                      ویرایش
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => remove.mutate(address.id)}
                  aria-label="حذف آدرس"
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            </li>
          ),
        )}
        {!data?.length && (
          <li className="rounded-3xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
            هنوز آدرسی ثبت نشده است. اولین آدرس به‌طور خودکار پیش‌فرض می‌شود.
          </li>
        )}
      </ul>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
        className="h-fit space-y-3 rounded-3xl bg-sand p-6"
      >
        <h2 className="text-lg">آدرس جدید</h2>
        <AddressFields prefix="new" values={form} onChange={setForm} />
        <label className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={makeDefault}
            onChange={(e) => setMakeDefault(e.target.checked)}
            className="size-4 accent-primary"
          />
          این آدرس پیش‌فرض باشد
        </label>
        <Button type="submit" disabled={create.isPending} className="w-full">
          ثبت آدرس
        </Button>
      </form>
    </div>
  );
}
