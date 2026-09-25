"use client";

import Link from "next/link";
import { LockIcon } from "@/components/common/Icons";

interface ErrorStateProps {
  code?: string;
  title?: string;
  message?: string;
  onRetry?: () => void;
  actionText?: string;
  actionHref?: string;
}

export function ErrorState({
  code = "API_ERROR",
  title,
  message,
  onRetry,
  actionText,
  actionHref,
}: ErrorStateProps) {
  // Normalize network errors
  const isNetworkError =
    code === "NETWORK_ERROR" ||
    (message && /failed to fetch|network error|load failed/i.test(message));

  const displayMessage = isNetworkError
    ? "We can't reach the Lingo server right now. Check your connection and try again."
    : message || "Failed to load learning path. Please make sure the backend server is running.";

  // Application-specific expected states
  if (code === "LESSON_LOCKED") {
    return (
      <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gold/15 text-gold-shadow">
          <LockIcon className="h-10 w-10 fill-gold-shadow" />
        </div>
        <h2 className="mt-6 text-2xl font-black tracking-tight text-ink">
          Lesson Locked
        </h2>
        <p className="mt-2 max-w-md text-sm font-bold text-ink-soft">
          Complete previous lessons on the path to unlock this one.
        </p>
        <Link
          href="/"
          className="mt-6 rounded-2xl border-b-4 border-brand-shadow bg-brand px-8 py-3.5 text-sm font-black uppercase tracking-wider text-white transition hover:brightness-105 active:translate-y-1 active:border-b-0"
        >
          Back to Path
        </Link>
      </div>
    );
  }

  if (code === "LESSON_NOT_FOUND" || code === "INVALID_ID") {
    return (
      <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sky-light text-sky">
          <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2.5}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <h2 className="mt-6 text-2xl font-black tracking-tight text-ink">
          Lesson Not Found
        </h2>
        <p className="mt-2 max-w-md text-sm font-bold text-ink-soft">
          We couldn&apos;t find this lesson. It may have moved or doesn&apos;t exist.
        </p>
        <Link
          href="/"
          className="mt-6 rounded-2xl border-b-4 border-brand-shadow bg-brand px-8 py-3.5 text-sm font-black uppercase tracking-wider text-white transition hover:brightness-105 active:translate-y-1 active:border-b-0"
        >
          Back to Path
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
      {isNetworkError ? (
        // Connection problem: calm "offline" treatment rather than a red crash icon.
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-sky-light text-sky">
          <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2.5}
              d="M3 3l18 18M8.5 16.5a5 5 0 017 0M5 13a10 10 0 0114 0M1.5 9.5a15 15 0 0121 0M12 20h.01"
            />
          </svg>
        </div>
      ) : (
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-danger-light text-danger">
          <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2.5}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
      )}

      <h2 className="mt-6 text-2xl font-black tracking-tight text-ink">
        {title || (isNetworkError ? "Can't connect" : "Something went wrong")}
      </h2>
      <p className="mt-2 max-w-md text-sm font-bold text-ink-soft">
        {displayMessage}
      </p>

      {code && !isNetworkError && (
        <span className="mt-3 inline-block rounded-lg bg-canvas px-3 py-1 font-mono text-xs font-bold text-locked-ink">
          Code: {code}
        </span>
      )}

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 rounded-2xl border-b-4 border-brand-shadow bg-brand px-8 py-3.5 text-sm font-black uppercase tracking-wider text-white transition hover:brightness-105 active:translate-y-1 active:border-b-0"
        >
          Try Again
        </button>
      )}

      {actionHref && (
        <Link
          href={actionHref}
          className="mt-3 text-sm font-black uppercase tracking-wider text-ink-soft hover:text-ink"
        >
          {actionText || "Back to Path"}
        </Link>
      )}
    </div>
  );
}
