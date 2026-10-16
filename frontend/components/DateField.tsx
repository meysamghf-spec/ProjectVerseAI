"use client";

import { useEffect, useState } from "react";

import { isoToJalali, jalaliToIso, toPersianDigits } from "@/lib/jalali";
import { useI18n } from "@/lib/i18n";

/**
 * Date input that always stores ISO (Gregorian) YYYY-MM-DD.
 * English: the browser's native date picker. Persian: a Jalali text field (accepts Persian or Latin digits).
 */
export function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (iso: string) => void;
}) {
  const { locale, t } = useI18n();
  const [text, setText] = useState(() => toPersianDigits(isoToJalali(value)));
  const [invalid, setInvalid] = useState(false);

  useEffect(() => {
    setText(toPersianDigits(isoToJalali(value)));
    setInvalid(false);
  }, [value, locale]);

  if (locale !== "fa") {
    return (
      <label className="text-sm">
        {label}
        <input className="field mt-1" type="date" value={value} onChange={(event) => onChange(event.target.value)} />
      </label>
    );
  }
  return (
    <label className="text-sm">
      {label}
      <input
        className="field mt-1"
        dir="ltr"
        inputMode="numeric"
        placeholder="۱۴۰۵/۰۷/۲۴"
        aria-invalid={invalid}
        title={t("date.jalaliHint")}
        value={text}
        onChange={(event) => {
          const raw = event.target.value;
          setText(raw);
          if (!raw.trim()) {
            setInvalid(false);
            onChange("");
            return;
          }
          const iso = jalaliToIso(raw);
          setInvalid(iso === null);
          if (iso) onChange(iso);
        }}
      />
      <span className={`mt-1 block text-xs ${invalid ? "text-coral" : "text-muted"}`}>
        {invalid ? t("date.invalid") : value ? `= ${value}` : t("date.jalaliHint")}
      </span>
    </label>
  );
}
