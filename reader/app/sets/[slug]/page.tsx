import Link from "next/link";
import { notFound } from "next/navigation";
import { getSet } from "@/lib/sets";
import { ThemeToggle } from "@/components/theme-toggle";

export const dynamic = "force-dynamic";

function formatDuration(sec: number | null | undefined): string {
  if (sec == null || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default async function SetDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const set = await getSet(slug);
  if (!set) notFound();

  const { set: meta, tracks } = set;

  // Sort by sequence (nulls last), then by original index
  const ordered = tracks
    .map((t, i) => ({ t, i }))
    .sort((a, b) => {
      const sa = a.t.sequence ?? Number.POSITIVE_INFINITY;
      const sb = b.t.sequence ?? Number.POSITIVE_INFINITY;
      if (sa !== sb) return sa - sb;
      return a.i - b.i;
    });

  const totalDurationSec = tracks.reduce((sum, t) => sum + (t.duration_sec ?? 0), 0);
  const placed = tracks.filter((t) => t.sequence != null).length;

  return (
    <div className="min-h-screen">
      <header className="max-w-6xl mx-auto px-6 pt-4 pb-10">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] mb-3">
              <Link
                href="/sets"
                className="hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] transition-colors"
              >
                ← Sets
              </Link>
            </p>
            <h1 className="font-display text-4xl md:text-5xl tracking-tight leading-[0.95] text-[var(--color-ink)] dark:text-[var(--color-night-ink)]">
              {meta.title}
            </h1>
            {meta.description && (
              <p className="mt-4 text-base text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] leading-relaxed max-w-2xl italic">
                {meta.description}
              </p>
            )}
            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]">
              {placed} / {tracks.length} placed
              {meta.target_duration_min ? ` · target ${meta.target_duration_min} min` : ""}
              {totalDurationSec > 0 && ` · pool ${Math.round(totalDurationSec / 60)} min`}
              {meta.lane && ` · ${meta.lane}`}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <div className="mt-8 h-px w-full bg-[var(--color-rule)] dark:bg-[var(--color-night-rule)]" />
      </header>

      <main className="max-w-6xl mx-auto px-6 pb-32">
        {tracks.length === 0 ? (
          <p className="py-16 text-center text-sm text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] italic">
            No tracks in this set yet.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-[var(--color-rule)] dark:border-[var(--color-night-rule)]">
            <table className="w-full text-sm">
              <thead className="text-[10px] uppercase tracking-[0.15em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] bg-[var(--color-paper-2)] dark:bg-[var(--color-night-2)]">
                <tr>
                  <th className="px-3 py-3 text-left w-16">Seq</th>
                  <th className="px-3 py-3 text-left">Title / Artist</th>
                  <th className="px-3 py-3 text-left w-20">BPM</th>
                  <th className="px-3 py-3 text-left w-16">Key</th>
                  <th className="px-3 py-3 text-left w-20">Length</th>
                  <th className="px-3 py-3 text-left">Comment</th>
                </tr>
              </thead>
              <tbody>
                {ordered.map(({ t }) => (
                  <tr
                    key={t.track_id}
                    className="border-t border-[var(--color-rule)] dark:border-[var(--color-night-rule)] align-top"
                  >
                    <td className="px-3 py-3">
                      {t.sequence != null ? (
                        <span className="font-mono text-[var(--color-accent)] dark:text-[var(--color-night-accent)]">
                          {t.sequence}
                        </span>
                      ) : (
                        <span className="text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-display text-[var(--color-ink)] dark:text-[var(--color-night-ink)] leading-tight">
                        {t.title}
                      </div>
                      {t.artists && (
                        <div className="text-xs text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] mt-0.5">
                          {t.artists}
                          {t.film ? ` · ${t.film}` : ""}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 font-mono text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)]">
                      {t.bpm ?? "—"}
                    </td>
                    <td className="px-3 py-3 font-mono text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)]">
                      {t.key ?? "—"}
                    </td>
                    <td className="px-3 py-3 font-mono text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)]">
                      {formatDuration(t.duration_sec)}
                    </td>
                    <td className="px-3 py-3 text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] whitespace-pre-wrap">
                      {t.comment || (
                        <span className="text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] italic">
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
