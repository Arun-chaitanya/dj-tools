"use client";

import { useState, useTransition } from "react";
import { MarkdownView } from "@/components/markdown-view";
import { setPrimaryVariantAction } from "@/lib/actions";
import type { Variant, LessonMeta } from "@/lib/lessons";

const VARIANTS: Variant[] = ["short", "medium", "long"];

export function ReaderControls({
  meta,
  variants,
}: {
  meta: LessonMeta;
  variants: Record<Variant, string>;
}) {
  const [selected, setSelected] = useState<Variant>(meta.primary_variant);
  const [primary, setPrimary] = useState<Variant>(meta.primary_variant);
  const [pending, startTransition] = useTransition();
  const [savedFlash, setSavedFlash] = useState(false);

  const isPrimary = selected === primary;

  const handleSetPrimary = () => {
    startTransition(async () => {
      await setPrimaryVariantAction(meta.slug, selected);
      setPrimary(selected);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1600);
    });
  };

  return (
    <>
      <div className="variant-toolbar">
        <div className="variant-switcher" role="tablist" aria-label="Variant length">
          {VARIANTS.map((v) => {
            const active = v === selected;
            const isCurrentPrimary = v === primary;
            return (
              <button
                key={v}
                type="button"
                role="tab"
                onClick={() => setSelected(v)}
                className={["variant-pill", active ? "is-active" : ""].join(" ")}
                aria-pressed={active}
              >
                <span className="variant-pill-label">{v}</span>
                {isCurrentPrimary && (
                  <span className="variant-pill-star" aria-label="primary variant">
                    ★
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {!isPrimary && !savedFlash && (
          <button
            type="button"
            onClick={handleSetPrimary}
            disabled={pending}
            className="set-primary-btn"
          >
            {pending ? "Saving…" : "Set as primary"}
          </button>
        )}

        {savedFlash && (
          <span className="set-primary-flash">★ Set as primary</span>
        )}
      </div>

      <div key={selected} className="animate-fade-up">
        <MarkdownView markdown={variants[selected] || "*Empty.*"} />
      </div>
    </>
  );
}
