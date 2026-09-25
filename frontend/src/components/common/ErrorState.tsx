"use client";

interface ErrorStateProps {
  code?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  code = "API_ERROR",
  message = "Failed to load learning path. Please make sure the backend server is running.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
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

      <h2 className="mt-6 text-2xl font-black tracking-tight text-ink">
        Something went wrong
      </h2>
      <p className="mt-2 max-w-md text-sm font-bold text-ink-soft">
        {message}
      </p>

      {code && (
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
    </div>
  );
}
