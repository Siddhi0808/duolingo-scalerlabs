"use client";

interface QuitModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirmQuit: () => void;
  isQuitting: boolean;
}

export function QuitModal({
  isOpen,
  onClose,
  onConfirmQuit,
  isQuitting,
}: QuitModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-sm rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-2xl animate-pop">
        {/* Mascot / Icon */}
        <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-brand-light text-3xl shadow-xs">
          🥺
        </div>

        <h3 className="text-2xl font-black tracking-tight text-ink">Quit lesson?</h3>
        <p className="mt-2 text-sm font-bold text-ink-soft">
          All progress in this lesson session will be lost. Are you sure you want to leave?
        </p>

        <div className="mt-6 flex flex-col gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isQuitting}
            className="w-full rounded-2xl border-b-4 border-brand-shadow bg-brand py-3.5 text-sm font-black uppercase tracking-wider text-white shadow-md transition hover:brightness-105 active:translate-y-1 active:border-b-0"
          >
            Keep Learning
          </button>

          <button
            type="button"
            onClick={onConfirmQuit}
            disabled={isQuitting}
            className="w-full rounded-2xl border-2 border-b-4 border-line bg-surface py-3 text-sm font-black uppercase tracking-wider text-danger transition hover:bg-danger-light hover:border-danger-shadow/30 active:translate-y-1 active:border-b-2"
          >
            {isQuitting ? "Quitting..." : "End Session"}
          </button>
        </div>
      </div>
    </div>
  );
}
