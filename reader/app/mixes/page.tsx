import Link from "next/link";
import { listMixes } from "@/lib/mixes";
import { ThemeToggle } from "@/components/theme-toggle";

export const dynamic = "force-dynamic";

export default async function MixesPage() {
  const mixes = await listMixes();

  return (
    <div className="min-h-screen">
      <header className="max-w-3xl mx-auto px-6 pt-4 pb-12">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] mb-3">
              <Link href="/" className="hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] transition-colors">
                ← Lessons
              </Link>
              <span className="mx-2">·</span>
              Crates
            </p>
            <h1 className="font-display text-5xl md:text-6xl tracking-tight leading-[0.95] text-[var(--color-ink)] dark:text-[var(--color-night-ink)]">
              Mixes
            </h1>
            <p className="mt-5 text-base text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] leading-relaxed max-w-md italic">
              {mixes.length === 0
                ? "No mixes yet."
                : `${mixes.length} ${mixes.length === 1 ? "mix" : "mixes"} in progress. Each one a curated lane of tracks waiting to be sourced.`}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <div className="mt-10 h-px w-full bg-[var(--color-rule)] dark:bg-[var(--color-night-rule)]" />
      </header>

      <main className="max-w-3xl mx-auto px-6 pb-32">
        {mixes.length === 0 ? (
          <div className="text-center py-24">
            <p className="font-display text-2xl text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)]">
              No crates dug yet.
            </p>
          </div>
        ) : (
          <ol className="-ml-px animate-fade-up">
            {mixes.map((mix) => (
              <li key={mix.mix_id}>
                <Link
                  href={`/mixes/${mix.mix_id}`}
                  className="group block relative pl-7 pr-4 py-6 border-l border-[var(--color-rule)] hover:border-[var(--color-accent)] dark:border-[var(--color-night-rule)] dark:hover:border-[var(--color-night-accent)] transition-colors"
                >
                  <span
                    aria-hidden
                    className="absolute left-[-5px] top-7 h-2.5 w-2.5 rounded-full bg-[var(--color-paper)] dark:bg-[var(--color-night)] border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] group-hover:bg-[var(--color-accent)] group-hover:border-[var(--color-accent)] dark:group-hover:bg-[var(--color-night-accent)] dark:group-hover:border-[var(--color-night-accent)] transition-colors"
                  />
                  <div className="flex items-baseline justify-between gap-4 mb-2">
                    <span className="text-xs uppercase tracking-[0.18em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]">
                      {mix.created ?? ""}
                    </span>
                    <span className="shrink-0 text-[10px] uppercase tracking-[0.15em] font-semibold px-2 py-0.5 rounded-full text-[var(--color-accent)] bg-[var(--color-accent-soft)] dark:text-[var(--color-night-accent)] dark:bg-[var(--color-night-accent-soft)]">
                      {mix.total_tracks} tracks
                    </span>
                  </div>
                  <h2 className="font-display text-2xl md:text-[1.65rem] leading-tight tracking-tight text-[var(--color-ink)] dark:text-[var(--color-night-ink)] group-hover:text-[var(--color-accent)] dark:group-hover:text-[var(--color-night-accent)] transition-colors">
                    {mix.title}
                  </h2>
                  {mix.description && (
                    <p className="mt-2 text-sm text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] leading-relaxed line-clamp-2">
                      {mix.description}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ol>
        )}
      </main>
    </div>
  );
}
