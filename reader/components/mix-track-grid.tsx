"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Track } from "@/lib/mixes";
import { TrackCard } from "@/components/track-card";

type SortKey = "original" | "views_desc" | "year_desc" | "year_asc";
type YearBucket = "all" | "pre2015" | "2015_2019" | "2020_2024" | "2025_plus";
type ViewsBucket = "all" | "lt1m" | "1to10m" | "10mplus" | "50mplus" | "100mplus";

const YEAR_BUCKETS: { key: YearBucket; label: string; test: (y: number | null | undefined) => boolean }[] = [
  { key: "all", label: "All years", test: () => true },
  { key: "pre2015", label: "≤ 2014", test: (y) => y != null && y <= 2014 },
  { key: "2015_2019", label: "2015–19", test: (y) => y != null && y >= 2015 && y <= 2019 },
  { key: "2020_2024", label: "2020–24", test: (y) => y != null && y >= 2020 && y <= 2024 },
  { key: "2025_plus", label: "2025+", test: (y) => y != null && y >= 2025 },
];

const VIEWS_BUCKETS: { key: ViewsBucket; label: string; test: (v: number | null | undefined) => boolean }[] = [
  { key: "all", label: "All views", test: () => true },
  { key: "lt1m", label: "< 1M", test: (v) => v != null && v > 0 && v < 1_000_000 },
  { key: "1to10m", label: "1–10M", test: (v) => v != null && v >= 1_000_000 && v < 10_000_000 },
  { key: "10mplus", label: "10M+", test: (v) => v != null && v >= 10_000_000 },
  { key: "50mplus", label: "50M+", test: (v) => v != null && v >= 50_000_000 },
  { key: "100mplus", label: "100M+", test: (v) => v != null && v >= 100_000_000 },
];

const SORTS: { key: SortKey; label: string }[] = [
  { key: "original", label: "Curated order" },
  { key: "views_desc", label: "Most viewed" },
  { key: "year_desc", label: "Newest" },
  { key: "year_asc", label: "Oldest" },
];

const PILL_BASE = "px-2.5 py-1 text-[11px] uppercase tracking-[0.12em] rounded-full border transition-colors";
const PILL_ACTIVE =
  "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)] dark:border-[var(--color-night-accent)] dark:bg-[var(--color-night-accent-soft)] dark:text-[var(--color-night-accent)]";
const PILL_IDLE =
  "border-[var(--color-rule)] dark:border-[var(--color-night-rule)] text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] hover:border-[var(--color-accent)] dark:hover:border-[var(--color-night-accent)]";

function pillClass(active: boolean) {
  return `${PILL_BASE} ${active ? PILL_ACTIVE : PILL_IDLE}`;
}

function readParam<T extends string>(sp: URLSearchParams, key: string, allowed: readonly T[], fallback: T): T {
  const v = sp.get(key);
  return (allowed as readonly string[]).includes(v ?? "") ? (v as T) : fallback;
}

export function MixTrackGrid({ tracks }: { tracks: Track[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initial = useMemo(() => {
    const sp = new URLSearchParams(searchParams.toString());
    return {
      query: sp.get("q") ?? "",
      year: readParam<YearBucket>(sp, "year", ["all", "pre2015", "2015_2019", "2020_2024", "2025_plus"], "all"),
      views: readParam<ViewsBucket>(sp, "views", ["all", "lt1m", "1to10m", "10mplus", "50mplus", "100mplus"], "all"),
      sort: readParam<SortKey>(sp, "sort", ["original", "views_desc", "year_desc", "year_asc"], "original"),
      boundary: sp.get("boundary") === "1",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [query, setQuery] = useState(initial.query);
  const [yearBucket, setYearBucket] = useState<YearBucket>(initial.year);
  const [viewsBucket, setViewsBucket] = useState<ViewsBucket>(initial.views);
  const [sort, setSort] = useState<SortKey>(initial.sort);
  const [boundaryOnly, setBoundaryOnly] = useState(initial.boundary);

  const writeUrl = useCallback(
    (next: { query: string; year: YearBucket; views: ViewsBucket; sort: SortKey; boundary: boolean }) => {
      const sp = new URLSearchParams();
      if (next.query.trim()) sp.set("q", next.query.trim());
      if (next.year !== "all") sp.set("year", next.year);
      if (next.views !== "all") sp.set("views", next.views);
      if (next.sort !== "original") sp.set("sort", next.sort);
      if (next.boundary) sp.set("boundary", "1");
      const qs = sp.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      router.replace(url as never, { scroll: false });
    },
    [pathname, router],
  );

  useEffect(() => {
    const handle = setTimeout(() => {
      writeUrl({ query, year: yearBucket, views: viewsBucket, sort, boundary: boundaryOnly });
    }, 150);
    return () => clearTimeout(handle);
  }, [query, yearBucket, viewsBucket, sort, boundaryOnly, writeUrl]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const yearTest = YEAR_BUCKETS.find((b) => b.key === yearBucket)?.test ?? (() => true);
    const viewsTest = VIEWS_BUCKETS.find((b) => b.key === viewsBucket)?.test ?? (() => true);

    const indexed = tracks.map((track, originalIndex) => ({ track, originalIndex }));

    const matches = indexed.filter(({ track }) => {
      if (boundaryOnly && !track.boundary) return false;
      if (!yearTest(track.year)) return false;
      if (!viewsTest(track.view_count)) return false;
      if (q) {
        const hay = [track.title, track.artists, track.film, track.youtube_title, track.youtube_channel]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    if (sort === "views_desc") {
      matches.sort((a, b) => (b.track.view_count ?? -1) - (a.track.view_count ?? -1));
    } else if (sort === "year_desc") {
      matches.sort((a, b) => (b.track.year ?? -Infinity) - (a.track.year ?? -Infinity));
    } else if (sort === "year_asc") {
      matches.sort((a, b) => (a.track.year ?? Infinity) - (b.track.year ?? Infinity));
    }

    return matches;
  }, [tracks, query, yearBucket, viewsBucket, sort, boundaryOnly]);

  const boundaryCount = useMemo(() => tracks.filter((t) => t.boundary).length, [tracks]);

  return (
    <>
      <div className="mb-6 flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search title, artist, film…"
            className="flex-1 min-w-[200px] px-3 py-2 text-sm rounded-md border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] bg-[var(--color-paper-2)] dark:bg-[var(--color-night-2)] text-[var(--color-ink)] dark:text-[var(--color-night-ink)] placeholder:text-[var(--color-ink-mute)] dark:placeholder:text-[var(--color-night-mute)] focus:outline-none focus:border-[var(--color-accent)] dark:focus:border-[var(--color-night-accent)]"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="px-3 py-2 text-sm rounded-md border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] bg-[var(--color-paper-2)] dark:bg-[var(--color-night-2)] text-[var(--color-ink)] dark:text-[var(--color-night-ink)] focus:outline-none focus:border-[var(--color-accent)] dark:focus:border-[var(--color-night-accent)]"
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {YEAR_BUCKETS.map((b) => (
            <button key={b.key} type="button" onClick={() => setYearBucket(b.key)} className={pillClass(yearBucket === b.key)}>
              {b.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {VIEWS_BUCKETS.map((b) => (
            <button key={b.key} type="button" onClick={() => setViewsBucket(b.key)} className={pillClass(viewsBucket === b.key)}>
              {b.label}
            </button>
          ))}
          {boundaryCount > 0 && (
            <button
              type="button"
              onClick={() => setBoundaryOnly((v) => !v)}
              className={`ml-1 ${pillClass(boundaryOnly)}`}
            >
              Boundary only ({boundaryCount})
            </button>
          )}
        </div>

        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)]">
          {filtered.length} of {tracks.length} tracks
        </p>
      </div>

      {filtered.length === 0 ? (
        <p className="py-16 text-center text-sm text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] italic">
          No tracks match these filters.
        </p>
      ) : (
        <ol className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map(({ track, originalIndex }) => (
            <li key={`${track.title}-${originalIndex}`}>
              <TrackCard track={track} index={originalIndex} />
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
