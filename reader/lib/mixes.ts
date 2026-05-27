import { promises as fs } from "node:fs";
import path from "node:path";

// Canonical tracklist shape — see CLAUDE.md "Tracklist schema" section.
export type Track = {
  // Identity
  title: string;
  artists: string | null;
  film: string | null;
  year: number | null;

  // YouTube canonical reference
  video_id: string | null;
  youtube_url?: string | null;
  youtube_title?: string | null;
  youtube_channel?: string | null;
  view_count?: number | null;

  // Curation provenance
  sources?: string[];
  appears_in_playlists_count?: number;
  passes_popularity_floor?: boolean;

  // Lane judgment (optional — V2-style harvest annotations)
  phase?: string;
  why_in?: string | null;
  boundary?: boolean;

  // Download state
  status?: "planned" | "downloaded" | "needs_manual" | "skipped" | string;
};

export type MixMeta = {
  mix_id: string;
  title: string;
  description?: string;
  lane_profile?: string;
  created?: string;
  total_tracks: number;
  popularity_floor?: string;
};

export type Mix = {
  mix: MixMeta;
  tracks: Track[];
};

export function mixesDir(): string {
  return process.env.MIXES_DIR ?? path.resolve(process.cwd(), "..", "mixes");
}

export async function listMixes(): Promise<MixMeta[]> {
  const dir = mixesDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw err;
  }

  const metas: MixMeta[] = [];
  for (const entry of entries) {
    if (entry.startsWith("_") || entry.startsWith(".")) continue;
    const tracklistPath = path.join(dir, entry, "tracklist.json");
    try {
      const raw = await fs.readFile(tracklistPath, "utf8");
      const data = JSON.parse(raw) as Mix;
      if (data.mix) {
        metas.push({ ...data.mix, mix_id: entry });
      }
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
        console.warn(`[mixes] skipping ${entry}: ${(err as Error).message}`);
      }
    }
  }

  metas.sort((a, b) => {
    const ad = a.created ?? "";
    const bd = b.created ?? "";
    return ad < bd ? 1 : -1;
  });
  return metas;
}

export async function getMix(mixId: string): Promise<Mix | null> {
  const tracklistPath = path.join(mixesDir(), mixId, "tracklist.json");
  try {
    const raw = await fs.readFile(tracklistPath, "utf8");
    return JSON.parse(raw) as Mix;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}
