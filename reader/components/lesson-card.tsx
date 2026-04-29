import Link from "next/link";
import type { LessonMeta } from "@/lib/lessons";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

const variantLabel: Record<string, string> = {
  short: "Short",
  medium: "Medium",
  long: "Long",
};

export function LessonCard({ meta }: { meta: LessonMeta }) {
  return (
    <Link
      href={`/lessons/${meta.slug}`}
      className="group block relative pl-7 pr-4 py-6 border-l border-[var(--color-rule)] hover:border-[var(--color-accent)] dark:border-[var(--color-night-rule)] dark:hover:border-[var(--color-night-accent)] transition-colors"
    >
      <span
        aria-hidden
        className="absolute left-[-5px] top-7 h-2.5 w-2.5 rounded-full bg-[var(--color-paper)] dark:bg-[var(--color-night)] border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] group-hover:bg-[var(--color-accent)] group-hover:border-[var(--color-accent)] dark:group-hover:bg-[var(--color-night-accent)] dark:group-hover:border-[var(--color-night-accent)] transition-colors"
      />

      <div className="flex items-baseline justify-between gap-4 mb-2">
        <time
          dateTime={meta.created}
          className="text-xs uppercase tracking-[0.18em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]"
        >
          {formatDate(meta.created)}
        </time>
        <span className="shrink-0 text-[10px] uppercase tracking-[0.15em] font-semibold px-2 py-0.5 rounded-full text-[var(--color-accent)] bg-[var(--color-accent-soft)] dark:text-[var(--color-night-accent)] dark:bg-[var(--color-night-accent-soft)]">
          {variantLabel[meta.primary_variant] ?? meta.primary_variant}
        </span>
      </div>

      <h2 className="font-display text-2xl md:text-[1.65rem] leading-tight tracking-tight text-[var(--color-ink)] dark:text-[var(--color-night-ink)] group-hover:text-[var(--color-accent)] dark:group-hover:text-[var(--color-night-accent)] transition-colors">
        {meta.title}
      </h2>

      {meta.tags.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {meta.tags.map((tag) => (
            <li
              key={tag}
              className="text-[11px] uppercase tracking-wider px-2 py-0.5 text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] rounded-full"
            >
              {tag}
            </li>
          ))}
        </ul>
      )}
    </Link>
  );
}
