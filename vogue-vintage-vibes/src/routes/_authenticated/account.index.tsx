import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/account/")({
  component: ProfileTab,
});

function ProfileTab() {
  const { user, profile } = useAuth();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFullName(profile?.full_name ?? "");
    setPhone(profile?.phone ?? "");
  }, [profile]);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    const { error } = await supabase
      .from("profiles")
      .upsert({ id: user.id, full_name: fullName, phone });
    setBusy(false);
    if (error) {
      toast.error("ذخیره نشد");
      return;
    }
    queryClient.invalidateQueries({ queryKey: ["me"] });
    toast.success("پروفایل ذخیره شد");
  };

  return (
    <form onSubmit={save} className="max-w-lg space-y-4 rounded-3xl bg-sand p-6">
      <div>
        <Label htmlFor="name">نام و نام خانوادگی</Label>
        <Input
          id="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="mt-2 bg-background"
        />
      </div>
      <div>
        <Label htmlFor="phone">شماره تماس</Label>
        <Input
          id="phone"
          dir="ltr"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="mt-2 bg-background"
        />
      </div>
      <div>
        <Label>ایمیل</Label>
        <p dir="ltr" className="mt-2 text-sm text-muted-foreground">
          {user?.email}
        </p>
      </div>
      <Button type="submit" disabled={busy}>
        ذخیره تغییرات
      </Button>
    </form>
  );
}