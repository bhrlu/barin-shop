import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type SizeProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BadgeCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toFa } from "@/lib/format";

export const Route = createFileRoute("/_authenticated/account/")({
  component: ProfileTab,
});

const EMPTY_SIZE: SizeProfile = {
  height_cm: null,
  weight_kg: null,
  chest_cm: null,
  waist_cm: null,
  hip_cm: null,
  preferred_top_size: null,
  preferred_bottom_size: null,
  preferred_shoe_size: null,
  fit_preference: null,
  updated_at: null,
};

const GENDER_LABELS = {
  male: "مرد",
  female: "زن",
  other: "سایر",
} as const;

const FIT_LABELS = {
  slim: "انداز (چسبان)",
  regular: "معمولی",
  relaxed: "رحت",
} as const;

/** Persian digits only look right on the body measurements; an empty box stays empty. */
const fa = (value: number | null) => (value == null ? "" : toFa(value));

function ProfileTab() {
  const { user, profile, refresh } = useAuth();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // personal + contact + identity
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<string>("");
  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");

  // size profile (kept in one form of its own)
  const [size, setSize] = useState<SizeProfile>(EMPTY_SIZE);
  const [sizeDraft, setSizeDraft] = useState<SizeDraft>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [me, sizeProfile] = await Promise.all([
          api.me(),
          api.sizeProfile().catch(() => EMPTY_SIZE),
        ]);
        if (cancelled) return;
        setFirstName(me.first_name ?? "");
        setLastName(me.last_name ?? "");
        setBirthDate(me.birth_date ?? "");
        setGender(me.gender ?? "");
        setNationalId(me.national_id ?? "");
        setPhone(me.phone ?? "");
        setSize(sizeProfile);
        setSizeDraft(draftFrom(sizeProfile));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      // the server's response is the canonical state (F5.20: no optimistic writes)
      const saved = await api.updateMe({
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        birth_date: birthDate || null,
        gender: gender === "" ? null : (gender as "male" | "female" | "other"),
        national_id: nationalId.trim() === "" ? "" : nationalId.trim(),
        phone,
      });
      setFirstName(saved.first_name ?? "");
      setLastName(saved.last_name ?? "");
      setBirthDate(saved.birth_date ?? "");
      setGender(saved.gender ?? "");
      setNationalId(saved.national_id ?? "");
      setPhone(saved.phone ?? "");
      await refresh();
      toast.success("پروفایل ذخیره شد");
    } catch (err) {
      toast.error("ذخیره نشد");
      setError(err instanceof Error ? err.message : "");
    } finally {
      setBusy(false);
    }
  };

  const saveSize = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const num = (key: keyof SizeProfile) => {
        const raw = (sizeDraft[key] ?? "").replace(/[۰-۹]/g, (d) =>
          String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)),
        );
        return raw === "" ? null : Number(raw);
      };
      const saved = await api.updateSizeProfile({
        height_cm: num("height_cm"),
        weight_kg: num("weight_kg"),
        chest_cm: num("chest_cm"),
        waist_cm: num("waist_cm"),
        hip_cm: num("hip_cm"),
        preferred_top_size: sizeDraft["preferred_top_size"] || null,
        preferred_bottom_size: sizeDraft["preferred_bottom_size"] || null,
        preferred_shoe_size: sizeDraft["preferred_shoe_size"] || null,
        fit_preference: (sizeDraft["fit_preference"] || null) as
          "slim" | "regular" | "relaxed" | null,
      });
      setSize(saved);
      setSizeDraft(draftFrom(saved));
      await refresh();
      toast.success("سایزها ذخیره شد");
    } catch (err) {
      toast.error("ذخیره نشد");
      setError(err instanceof Error ? err.message : "");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl space-y-3">
        <div className="h-40 animate-pulse rounded-3xl bg-clay" />
        <div className="h-64 animate-pulse rounded-3xl bg-clay" />
      </div>
    );
  }

  const verified = (at: string | null) =>
    at ? (
      <span className="inline-flex items-center gap-1 text-xs text-sage-deep">
        <BadgeCheck className="size-3.5" /> تأیید شده
      </span>
    ) : (
      <span className="text-xs text-muted-foreground">تأیید نشده</span>
    );

  return (
    <div className="max-w-2xl space-y-8">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <form onSubmit={saveProfile} className="space-y-6 rounded-3xl bg-sand p-6">
        <section className="space-y-4">
          <h2 className="text-lg">اطلاعات شخصی</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="first-name">نام</Label>
              <Input
                id="first-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                maxLength={60}
                className="mt-2 bg-background"
              />
            </div>
            <div>
              <Label htmlFor="last-name">نام خانوادگی</Label>
              <Input
                id="last-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                maxLength={60}
                className="mt-2 bg-background"
              />
            </div>
            <div>
              <Label htmlFor="birth-date">تاریخ تولد</Label>
              <Input
                id="birth-date"
                type="date"
                dir="ltr"
                max="2026-12-31"
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)}
                className="mt-2 bg-background"
              />
            </div>
            <div>
              <Label>جنسیت</Label>
              <Select value={gender} onValueChange={setGender}>
                <SelectTrigger className="mt-2 w-full bg-background">
                  <SelectValue placeholder="انتخاب کنید (اختیاری)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="female">زن</SelectItem>
                  <SelectItem value="male">مرد</SelectItem>
                  <SelectItem value="other">سایر</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </section>

        <section className="space-y-4 border-t border-border pt-6">
          <h2 className="text-lg">اطلاعات تماس</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="phone">شماره تماس</Label>
              <Input
                id="phone"
                dir="ltr"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="mt-2 bg-background"
              />
              <div className="mt-1">
                {verified(profile?.phone ? (user?.phone_verified_at ?? null) : null)}
              </div>
            </div>
            <div>
              <Label>ایمیل</Label>
              <p dir="ltr" className="mt-2 text-sm text-muted-foreground">
                {user?.email}
              </p>
              <div className="mt-1">{verified(user?.email_verified_at ?? null)}</div>
            </div>
          </div>
        </section>

        <section className="space-y-2 border-t border-border pt-6">
          <h2 className="text-lg">اطلاعات هویتی</h2>
          <div>
            <Label htmlFor="national-id">کد ملی (اختیاری)</Label>
            <Input
              id="national-id"
              dir="ltr"
              inputMode="numeric"
              value={nationalId}
              onChange={(e) => setNationalId(toLatin(e.target.value))}
              placeholder="۱۰ رقم"
              maxLength={12}
              className="mt-2 bg-background"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              فقط برای سفارش‌هایی که به آن نیاز دارند؛ با اطمینان نگهداری می‌شود.
            </p>
          </div>
        </section>

        <Button type="submit" disabled={busy}>
          {busy ? "در حال ذخیره…" : "ذخیره تغییرات"}
        </Button>
      </form>

      <form onSubmit={saveSize} className="space-y-6 rounded-3xl bg-sand p-6">
        <section className="space-y-4">
          <h2 className="text-lg">سایز من</h2>
          <p className="text-xs text-muted-foreground">
            اندازه‌ها بر حسب سانتی‌متر و وزن بر حسب کیلوگرم؛ همه اختیاری.
          </p>
          <div className="grid gap-4 sm:grid-cols-3">
            <SizeField
              id="height_cm"
              label="قد (سانتی‌متر)"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="weight_kg"
              label="وزن (کیلوگرم)"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="chest_cm"
              label="دور سینه (سانتی‌متر)"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="waist_cm"
              label="دور کمر (سانتی‌متر)"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="hip_cm"
              label="دور باسن (سانتی‌متر)"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="preferred_top_size"
              label="سایز بالاتنه"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="preferred_bottom_size"
              label="سایز پایین‌تنه"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <SizeField
              id="preferred_shoe_size"
              label="سایز کفش"
              draft={sizeDraft}
              onChange={setSizeDraft}
            />
            <div>
              <Label>نوع انداز</Label>
              <Select
                value={sizeDraft["fit_preference"] ?? ""}
                onValueChange={(v) => setSizeDraft((d) => ({ ...d, fit_preference: v }))}
              >
                <SelectTrigger className="mt-2 w-full bg-background">
                  <SelectValue placeholder="انتخاب کنید (اختیاری)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="slim">{FIT_LABELS.slim}</SelectItem>
                  <SelectItem value="regular">{FIT_LABELS.regular}</SelectItem>
                  <SelectItem value="relaxed">{FIT_LABELS.relaxed}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {size.updated_at ? (
            <p className="text-xs text-muted-foreground">آخرین به‌روزرسانی ثبت شد.</p>
          ) : null}
        </section>
        <Button type="submit" disabled={busy}>
          {busy ? "در حال ذخیره…" : "ذخیره سایزها"}
        </Button>
      </form>
    </div>
  );
}

/** The editable text behind each size field; keys mirror `SizeProfile`. */
type SizeDraft = Partial<Record<keyof SizeProfile, string>>;

function draftFrom(profile: SizeProfile): SizeDraft {
  return {
    height_cm: fa(profile.height_cm),
    weight_kg: fa(profile.weight_kg),
    chest_cm: fa(profile.chest_cm),
    waist_cm: fa(profile.waist_cm),
    hip_cm: fa(profile.hip_cm),
    preferred_top_size: profile.preferred_top_size ?? "",
    preferred_bottom_size: profile.preferred_bottom_size ?? "",
    preferred_shoe_size: profile.preferred_shoe_size ?? "",
    fit_preference: profile.fit_preference ?? "",
  };
}

function SizeField({
  id,
  label,
  draft,
  onChange,
}: {
  id: keyof SizeProfile;
  label: string;
  draft: SizeDraft;
  onChange: (next: SizeDraft) => void;
}) {
  return (
    <div>
      <Label htmlFor={`size-${id}`}>{label}</Label>
      <Input
        id={`size-${id}`}
        dir="ltr"
        inputMode="numeric"
        value={draft[id] ?? ""}
        onChange={(e) => onChange({ ...draft, [id]: toLatin(e.target.value) })}
        className="mt-2 bg-background"
      />
    </div>
  );
}

/** Persian/Arabic digits → Latin so the backend receives canonical numbers. */
function toLatin(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
}
