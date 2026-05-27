import type { Track } from "@/lib/mixes";

function formatViews(n: number | null | undefined): string | null {
  if (!n || n <= 0) return null;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K views`;
  return `${n} views`;
}

export function TrackCard({ track, index }: { track: Track; index: number }) {
  const thumbUrl = track.video_id
    ? `https://i.ytimg.com/vi/${track.video_id}/mqdefault.jpg`
    : null;
  const href = track.video_id
    ? `https://www.youtube.com/watch?v=${track.video_id}`
    : null;

  const meta = [track.film, track.year ? String(track.year) : null]
    .filter(Boolean)
    .join(" · ");

  const card = (
    <div className="group block overflow-hidden rounded-lg border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] bg-[var(--color-paper-2)] dark:bg-[var(--color-night-2)] hover:border-[var(--color-accent)] dark:hover:border-[var(--color-night-accent)] transition-colors h-full">
      <div className="relative aspect-video bg-[var(--color-rule)] dark:bg-[var(--color-night-rule)] overflow-hidden">
        {thumbUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbUrl}
            alt={track.title}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] text-xs uppercase tracking-wider">
            no thumbnail
          </div>
        )}
        <span className="absolute top-2 left-2 text-[10px] uppercase tracking-[0.15em] font-semibold px-1.5 py-0.5 rounded bg-[var(--color-paper)] dark:bg-[var(--color-night)] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] border border-[var(--color-rule)] dark:border-[var(--color-night-rule)]">
          #{index + 1}
        </span>
        {track.boundary && (
          <span className="absolute top-2 right-2 text-[10px] uppercase tracking-[0.15em] font-semibold px-1.5 py-0.5 rounded bg-[var(--color-accent-soft)] dark:bg-[var(--color-night-accent-soft)] text-[var(--color-accent)] dark:text-[var(--color-night-accent)]">
            boundary
          </span>
        )}
      </div>

      <div className="p-3">
        <h3 className="font-display text-base leading-tight tracking-tight text-[var(--color-ink)] dark:text-[var(--color-night-ink)] group-hover:text-[var(--color-accent)] dark:group-hover:text-[var(--color-night-accent)] transition-colors line-clamp-2">
          {track.title}
        </h3>

        {track.artists && (
          <p className="mt-1 text-xs text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] line-clamp-1">
            {track.artists}
          </p>
        )}

        {meta && (
          <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] line-clamp-1">
            {meta}
          </p>
        )}

        {track.view_count != null && formatViews(track.view_count) && (
          <p className="mt-1 text-[11px] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]">
            {formatViews(track.view_count)}
          </p>
        )}
      </div>
    </div>
  );

  if (!href) return card;

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block h-full">
      {card}
    </a>
  );
}
