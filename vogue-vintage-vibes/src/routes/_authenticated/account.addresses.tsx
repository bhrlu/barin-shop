import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
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

function AddressesTab() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(empty);

  const { data } = useQuery({
    queryKey: ["addresses"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("addresses")
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("no user");
      const { error } = await supabase.from("addresses").insert({ ...form, user_id: user.id });
      if (error) throw error;
    },
    onSuccess: () => {
      setForm(empty);
      queryClient.invalidateQueries({ queryKey: ["addresses"] });
      toast.success("آدرس اضافه شد");
    },
    onError: () => toast.error("ثبت آدرس ناموفق بود"),
  });

  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from("addresses").delete().eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["addresses"] }),
  });

  const field = (key: keyof typeof empty, label: string, required = true) => (
    <div>
      <Label htmlFor={key}>{label}</Label>
      <Input
        id={key}
        value={form[key]}
        required={required}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="mt-2 bg-background"
      />
    </div>
  );

  return (
    <div className="grid gap-8 md:grid-cols-[1fr_360px]">
      <ul className="space-y-4">
        {(data ?? []).map((address) => (
          <li key={address.id} className="rounded-3xl border border-border p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm">{address.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {address.province}، {address.city} — {address.line}
                </p>
                <p className="mt-1 text-xs text-muted-foreground" dir="ltr">
                  {address.receiver} · {address.phone}
                  {address.postal_code ? ` · ${address.postal_code}` : ""}
                </p>
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
        ))}
        {!data?.length && (
          <li className="rounded-3xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
            هنوز آدرسی ثبت نشده است.
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
        {field("title", "عنوان")}
        {field("receiver", "نام گیرنده")}
        {field("phone", "شماره تماس")}
        {field("province", "استان")}
        {field("city", "شهر")}
        {field("postal_code", "کد پستی", false)}
        {field("line", "نشانی کامل")}
        <Button type="submit" disabled={create.isPending} className="w-full">
          ثبت آدرس
        </Button>
      </form>
    </div>
  );
}