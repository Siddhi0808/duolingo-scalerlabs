"use client";

import { HeartIcon, GemIcon } from "@/components/common/Icons";
import { useHeartCountdown } from "@/lib/api/hooks";
import type { HeartInfo } from "@/lib/api/types";

interface OutOfHeartsModalProps {
  isOpen: boolean;
  hearts: HeartInfo | undefined;
  gems?: number;
  onRefill: () => void;
  onQuit: () => void;
  isRefilling: boolean;
  refillError?: string | null;
}

export function OutOfHeartsModal({
  isOpen,
  hearts,
  gems,
  onRefill,
  onQuit,
  isRefilling,
  refillError,
}: OutOfHeartsModalProps) {
  const { formatted } = useHeartCountdown(hearts);

  if (!isOpen) return null;

  const refillCost = hearts?.refill_cost_gems;
  const canAfford = typeof gems === "number" && typeof refillCost === "number" && gems >= refillCost;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-sm rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-2xl animate-pop">
        {/* Empty heart: matches the grey 0-hearts counter in the lesson header */}
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-canvas">
          <HeartIcon className="h-12 w-12 fill-locked-ink" />
        </div>

        <h3 className="mt-4 text-2xl font-black text-ink">Out of Hearts!</h3>
        <p className="mt-2 text-sm font-bold text-ink-soft">
          You need hearts to continue learning.
        </p>

        {/* Countdown */}
        {formatted && (
          <div className="mt-4 rounded-2xl bg-canvas p-3">
            <span className="text-xs font-bold text-ink-soft">Next heart in:</span>
            <div className="font-mono text-xl font-black text-danger">
              {formatted}
            </div>
          </div>
        )}

        {refillError && (
          <p className="mt-2 text-xs font-bold text-danger">
            {refillError}
          </p>
        )}

        <div className="mt-6 flex flex-col gap-3">
          {/* Refill Button */}
          <button
            type="button"
            disabled={!canAfford || isRefilling}
            onClick={onRefill}
            className={`flex w-full items-center justify-center gap-2 rounded-2xl border-b-4 py-3.5 text-sm font-black uppercase tracking-wider transition ${
              !canAfford || isRefilling
                ? "cursor-not-allowed border-[#c5c5c5] bg-locked text-locked-ink"
                : "border-sky-shadow bg-sky text-white hover:brightness-105 active:translate-y-1 active:border-b-0 shadow-md"
            }`}
          >
            <GemIcon className="h-5 w-5 fill-white" />
            <span>
              {isRefilling
                ? "Refilling..."
                : typeof refillCost === "number"
                ? `Refill Hearts (${refillCost} Gems)`
                : "Refill Hearts"}
            </span>
          </button>

          {/* Return button */}
          <button
            type="button"
            onClick={onQuit}
            className="w-full rounded-2xl border-2 border-b-4 border-line bg-surface py-3 text-sm font-black uppercase tracking-wider text-ink-soft transition hover:bg-canvas active:translate-y-1 active:border-b-2"
          >
            Back to Learning Path
          </button>
        </div>
      </div>
    </div>
  );
}
