import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/account/")({
  component: ProfileTab,
});

function ProfileTab() {
  const { user, profile, refresh } = useAuth();
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
    try {
      await api.updateMe({ full_name: fullName, phone });
      await refresh();
      toast.success("پروفایل ذخیره شد");
    } catch {
      toast.error("ذخیره نشد");
    } finally {
      setBusy(false);
    }
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
