import { promises as fs } from "node:fs";
import path from "node:path";

// A SetTrack is a row in a performable set. Each one references a track that
// lives in rekordbox (track_id = DjmdContent.ID) and carries denormalized
// display fields + the two per-set annotations the user fills in: sequence
// (playback order) and comment (free-form note for this set only).
export type SetTrack = {
  track_id: string;
  title: string;
  artists: string | null;
  film?: string | null;
  bpm: number | null;
  key: string | null;
  duration_sec?: number | null;

  // Per-set annotations — what makes this a *set* row, not just a library row.
  sequence: number | null;
  comment: string;
};

export type SetMeta = {
  set_id: string;
  title: string;
  description?: string;
  lane?: string;
  target_duration_min?: number;
  created?: string;
  updated?: string;
  total_tracks: number;
};

export type DjSet = {
  set: SetMeta;
  tracks: SetTrack[];
};

export function setsDir(): string {
  return process.env.SETS_DIR ?? path.resolve(process.cwd(), "..", "sets");
}

export async function listSets(): Promise<SetMeta[]> {
  const dir = setsDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw err;
  }

  const metas: SetMeta[] = [];
  for (const entry of entries) {
    if (entry.startsWith("_") || entry.startsWith(".")) continue;
    const setPath = path.join(dir, entry, "set.json");
    try {
      const raw = await fs.readFile(setPath, "utf8");
      const data = JSON.parse(raw) as DjSet;
      if (data.set) {
        metas.push({ ...data.set, set_id: entry });
      }
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
        console.warn(`[sets] skipping ${entry}: ${(err as Error).message}`);
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

export async function getSet(setId: string): Promise<DjSet | null> {
  const setPath = path.join(setsDir(), setId, "set.json");
  try {
    const raw = await fs.readFile(setPath, "utf8");
    return JSON.parse(raw) as DjSet;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}
