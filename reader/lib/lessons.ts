import { promises as fs } from "node:fs";
import path from "node:path";

export type Variant = "short" | "medium" | "long";

export type LessonMeta = {
  slug: string;
  title: string;
  created: string;
  updated: string;
  primary_variant: Variant;
  tags: string[];
};

export type Lesson = {
  meta: LessonMeta;
  variants: Record<Variant, string>;
};

const VARIANTS: Variant[] = ["short", "medium", "long"];

export function lessonsDir(): string {
  return (
    process.env.LESSONS_DIR ?? path.resolve(process.cwd(), "..", "lessons")
  );
}

export async function listLessons(): Promise<LessonMeta[]> {
  const dir = lessonsDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw err;
  }

  const metas: LessonMeta[] = [];
  for (const entry of entries) {
    if (entry.startsWith("_") || entry.startsWith(".")) continue;
    const metaPath = path.join(dir, entry, "meta.json");
    try {
      const raw = await fs.readFile(metaPath, "utf8");
      metas.push(JSON.parse(raw) as LessonMeta);
    } catch (err) {
      // Skip folders that aren't lessons (no meta.json) or have malformed JSON.
      if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
        console.warn(`[lessons] skipping ${entry}: ${(err as Error).message}`);
      }
    }
  }

  metas.sort((a, b) => (a.created < b.created ? 1 : -1));
  return metas;
}

export async function getLesson(slug: string): Promise<Lesson | null> {
  const dir = lessonsDir();
  const lessonDir = path.join(dir, slug);
  let raw: string;
  try {
    raw = await fs.readFile(path.join(lessonDir, "meta.json"), "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
  const meta = JSON.parse(raw) as LessonMeta;

  const variantContents = await Promise.all(
    VARIANTS.map(async (v) => {
      try {
        return [v, await fs.readFile(path.join(lessonDir, `${v}.md`), "utf8")] as const;
      } catch (err) {
        if ((err as NodeJS.ErrnoException).code === "ENOENT") {
          return [v, ""] as const;
        }
        throw err;
      }
    }),
  );

  const variants = Object.fromEntries(variantContents) as Record<Variant, string>;
  return { meta, variants };
}

export async function getIdentity(): Promise<string | null> {
  const p = path.join(lessonsDir(), "_identity.md");
  try {
    return await fs.readFile(p, "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}

export async function setPrimaryVariant(
  slug: string,
  variant: Variant,
): Promise<void> {
  const metaPath = path.join(lessonsDir(), slug, "meta.json");
  const raw = await fs.readFile(metaPath, "utf8");
  const meta = JSON.parse(raw) as LessonMeta;
  if (meta.primary_variant === variant) return;
  meta.primary_variant = variant;
  // Intentionally do not touch `updated` — set-primary is metadata, not content.
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2) + "\n", "utf8");
}
