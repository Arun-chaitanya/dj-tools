"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
    setDark(next);
  };

  if (dark === null) {
    return (
      <button
        type="button"
        aria-label="Toggle theme"
        className="h-10 w-10 rounded-full border border-[var(--color-rule)] dark:border-[var(--color-night-rule)]"
      />
    );
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="h-10 w-10 rounded-full border border-[var(--color-rule)] dark:border-[var(--color-night-rule)] hover:border-[var(--color-accent)] dark:hover:border-[var(--color-night-accent)] hover:text-[var(--color-accent)] dark:hover:text-[var(--color-night-accent)] flex items-center justify-center text-base transition-colors"
    >
      {dark ? "☀" : "☾"}
    </button>
  );
}
