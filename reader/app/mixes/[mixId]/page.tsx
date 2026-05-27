import Link from "next/link";
import { notFound } from "next/navigation";
import { getMix } from "@/lib/mixes";
import { MixTrackGrid } from "@/components/mix-track-grid";
import { ThemeToggle } from "@/components/theme-toggle";

export const dynamic = "force-dynamic";

export default async function MixDetailPage({
  params,
}: {
  params: Promise<{ mixId: string }>;
}) {
  const { mixId } = await params;
  const mix = await getMix(mixId);
  if (!mix) notFound();

  const { mix: meta, tracks } = mix;
  const withThumb = tracks.filter((t) => t.video_id).length;

  return (
    <div className="min-h-screen">
      <header className="max-w-7xl mx-auto px-6 pt-4 pb-10">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] mb-3">
              <Link
                href="/mixes"
                className="hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] transition-colors"
              >
                ← Mixes
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
              {tracks.length} tracks
              {withThumb < tracks.length && (
                <span> · {withThumb} with thumbnails</span>
              )}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <div className="mt-8 h-px w-full bg-[var(--color-rule)] dark:bg-[var(--color-night-rule)]" />
      </header>

      <main className="max-w-7xl mx-auto px-6 pb-32">
        <MixTrackGrid tracks={tracks} />
      </main>
    </div>
  );
}
