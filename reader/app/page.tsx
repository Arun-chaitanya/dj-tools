import { listLessons } from "@/lib/lessons";
import { LessonCard } from "@/components/lesson-card";
import { ThemeToggle } from "@/components/theme-toggle";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const lessons = await listLessons();

  return (
    <div className="min-h-screen">
      <header className="max-w-3xl mx-auto px-6 pt-4 pb-12">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="text-[11px] uppercase tracking-[0.3em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] mb-3">
              Notes from the booth
              <span className="mx-2">·</span>
              <a
                href="/mixes"
                className="hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] transition-colors"
              >
                Mixes →
              </a>
              <span className="mx-2">·</span>
              <a
                href="/sets"
                className="hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] transition-colors"
              >
                Sets →
              </a>
            </p>
            <h1 className="font-display text-5xl md:text-6xl tracking-tight leading-[0.95] text-[var(--color-ink)] dark:text-[var(--color-night-ink)]">
              DJ Lessons
            </h1>
            <p className="mt-5 text-base text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)] leading-relaxed max-w-md italic">
              {lessons.length === 0
                ? "Nothing recorded yet."
                : `${lessons.length} ${lessons.length === 1 ? "lesson" : "lessons"} captured. Each one in three lengths — short, medium, long.`}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <div className="mt-10 h-px w-full bg-[var(--color-rule)] dark:bg-[var(--color-night-rule)]" />
      </header>

      <main className="max-w-3xl mx-auto px-6 pb-32">
        {lessons.length === 0 ? (
          <div className="text-center py-24">
            <p className="font-display text-2xl text-[var(--color-ink-soft)] dark:text-[var(--color-night-mute)]">
              The first lesson is the hardest.
            </p>
            <p className="mt-4 text-sm text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] max-w-sm mx-auto">
              Open <code className="font-mono px-1.5 py-0.5 rounded bg-[var(--color-paper-2)] dark:bg-[var(--color-night-2)]">claude</code> in this repo and dictate what you learned today. The notes will appear here.
            </p>
          </div>
        ) : (
          <ol className="-ml-px animate-fade-up">
            {lessons.map((meta) => (
              <li key={meta.slug}>
                <LessonCard meta={meta} />
              </li>
            ))}
          </ol>
        )}
      </main>

      <footer className="max-w-3xl mx-auto px-6 pb-12 text-[11px] uppercase tracking-[0.18em] text-[var(--color-ink-mute)] dark:text-[var(--color-night-mute)] text-center">
        Read on. Learn forever.
      </footer>
    </div>
  );
}
