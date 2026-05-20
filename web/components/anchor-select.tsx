"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";

import type { Institution } from "@/types/db";

type Props = {
  institutions: Institution[];
  anchorCert: number;
};

export function AnchorSelect({ institutions, anchorCert }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  function onChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value;
    const params = new URLSearchParams(searchParams);
    params.set("anchor", next);
    startTransition(() => {
      router.replace(`?${params.toString()}`, { scroll: false });
    });
  }

  return (
    <label className="inline-flex items-center gap-2 text-[length:var(--text-body)] text-[color:var(--color-text-secondary)]">
      Anchor
      <select
        value={String(anchorCert)}
        onChange={onChange}
        className="rounded-sm border border-[color:var(--color-border)] bg-[color:var(--color-surface)] px-2 py-1 text-[length:var(--text-body)] text-[color:var(--color-text)] focus:border-[color:var(--color-accent)] focus:outline-hidden"
      >
        {institutions.map((inst) => (
          <option key={inst.cert} value={String(inst.cert)}>
            {inst.name} ({inst.cert})
          </option>
        ))}
      </select>
    </label>
  );
}
