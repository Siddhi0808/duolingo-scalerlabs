"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckIcon } from "@/components/common/Icons";

/**
 * Lightweight app-wide toasts: short, non-blocking confirmations of state changes.
 *
 * `ToastProvider` is mounted once in the root providers, so a toast survives client-side
 * navigation (e.g. "Lesson complete" shown after returning to the path). Components call
 * `useToast()` and never manage toast state themselves.
 */

export type ToastVariant = "success" | "error";

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  icon?: ReactNode; // overrides the variant's default icon
}

interface ToastItem extends ToastOptions {
  id: number;
  variant: ToastVariant;
}

const TOAST_DURATION_MS = 3500;
const MAX_VISIBLE = 3;

const ToastContext = createContext<((toast: ToastOptions) => void) | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timers.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const showToast = useCallback(
    (toast: ToastOptions) => {
      const id = ++nextId.current;
      setToasts((current) =>
        [...current, { ...toast, id, variant: toast.variant ?? "success" }].slice(-MAX_VISIBLE)
      );
      timers.current.set(
        id,
        window.setTimeout(() => dismiss(id), TOAST_DURATION_MS)
      );
    },
    [dismiss]
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach((timer) => window.clearTimeout(timer));
      pending.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {/* Always mounted so screen readers pick up toasts added later. */}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 top-20 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto flex w-full max-w-sm items-center gap-3 rounded-2xl border-2 border-b-4 border-line bg-surface p-3 shadow-lg animate-toast-in motion-reduce:animate-none"
          >
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                toast.variant === "success" ? "bg-brand-light" : "bg-danger-light"
              }`}
            >
              {toast.icon ??
                (toast.variant === "success" ? (
                  <CheckIcon className="h-5 w-5 stroke-brand-shadow stroke-[3.5]" />
                ) : (
                  <span className="text-lg font-black text-danger">!</span>
                ))}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-black text-ink">{toast.title}</p>
              {toast.description && (
                <p className="text-xs font-bold text-ink-soft">{toast.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-black text-locked-ink transition hover:bg-canvas hover:text-ink"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const showToast = useContext(ToastContext);
  if (!showToast) throw new Error("useToast must be used inside <ToastProvider>");
  return showToast;
}
