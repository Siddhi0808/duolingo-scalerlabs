"use client";

import { HeartIcon } from "@/components/common/Icons";
import type { HeartInfo, SessionProgress } from "@/lib/api/types";

interface LessonHeaderProps {
  progress: SessionProgress | undefined;
  hearts: HeartInfo | undefined;
  onQuit: () => void;
}

export function LessonHeader({ progress, hearts, onQuit }: LessonHeaderProps) {
  const total = progress?.total || 1;
  const answered = progress?.answered || 0;
  const percent = Math.min(100, Math.floor((answered / total) * 100));

  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-line bg-surface/95 px-4 backdrop-blur-sm sm:px-8">
      {/* Quit / Close Button */}
      <button
        type="button"
        onClick={onQuit}
        aria-label="Quit lesson"
        className="flex h-10 w-10 items-center justify-center rounded-xl text-ink-soft transition hover:bg-canvas hover:text-ink active:translate-y-0.5"
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={3}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>

      {/* Progress Bar */}
      <div className="mx-4 flex-1 max-w-xl">
        <div className="relative h-4 w-full overflow-hidden rounded-full bg-line">
          <div
            className="h-full rounded-full bg-brand transition-all duration-500"
            style={{ width: `${percent}%` }}
          >
            {/* Top highlight shine on progress bar */}
            <div className="h-1.5 w-full rounded-full bg-white/30" />
          </div>
        </div>
      </div>

      {/* Hearts Counter */}
      <div className="flex items-center gap-1.5 text-heart">
        <HeartIcon className="h-7 w-7 fill-heart" />
        <span className="text-lg font-black tracking-tight">
          {hearts ? hearts.current : "—"}
        </span>
      </div>
    </header>
  );
}
