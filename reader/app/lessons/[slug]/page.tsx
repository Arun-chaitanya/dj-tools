import Link from "next/link";
import { notFound } from "next/navigation";
import { getLesson } from "@/lib/lessons";
import { ThemeToggle } from "@/components/theme-toggle";
import { ReaderControls } from "./reader-controls";

export const dynamic = "force-dynamic";

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

export default async function LessonPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const lesson = await getLesson(slug);
  if (!lesson) notFound();

  const { meta, variants } = lesson;

  return (
    <div className="min-h-screen">
      <header className="max-w-3xl mx-auto px-6 pt-4 pb-4 flex items-center justify-between">
        <Link
          href="/"
          className="group inline-flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-[var(--color-ink-mute)] hover:text-[var(--color-accent)] dark:text-[var(--color-night-mute)] dark:hover:text-[var(--color-night-accent)] transition-colors"
        >
          <span className="transition-transform group-hover:-translate-x-0.5">
            ←
          </span>
          <span>All Lessons</span>
        </Link>
        <ThemeToggle />
      </header>

      <main className="max-w-3xl mx-auto px-6 pb-32">
        <div className="text-center pt-8 pb-10 animate-fade-up">
          <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] mb-5">
            <time dateTime={meta.created}>{formatDate(meta.created)}</time>
            {meta.tags.length > 0 && (
              <>
                <span className="mx-3 opacity-50" aria-hidden>
                  ·
                </span>
                {meta.tags.join(" · ")}
              </>
            )}
          </p>
          <h1 className="font-display text-4xl md:text-6xl tracking-tight leading-[1.05] text-[var(--color-ink)] dark:text-[var(--color-night-ink)] max-w-3xl mx-auto">
            {meta.title}
          </h1>
          <div className="mt-10 flex justify-center">
            <span className="inline-block w-12 h-px bg-[var(--color-accent)] dark:bg-[var(--color-night-accent)]" />
          </div>
        </div>

        <ReaderControls meta={meta} variants={variants} />

        <div className="mt-20 flex justify-center">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] dark:bg-[var(--color-night-accent)]" />
        </div>
      </main>
    </div>
  );
}
