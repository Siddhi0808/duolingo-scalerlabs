"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { GemIcon, HeartIcon } from "@/components/common/Icons";
import { api, ApiClientError } from "@/lib/api/client";
import { queryKeys, useHeartCountdown } from "@/lib/api/hooks";
import type { HeartInfo } from "@/lib/api/types";

interface HeartRefillModalProps {
  isOpen: boolean;
  onClose: () => void;
  hearts: HeartInfo | undefined;
  gems?: number;
}

export function HeartRefillModal({
  isOpen,
  onClose,
  hearts,
  gems,
}: HeartRefillModalProps) {
  const queryClient = useQueryClient();
  const { formatted, isRegenerating } = useHeartCountdown(hearts);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const current = hearts?.current ?? 5;
  const max = hearts?.max ?? 5;
  const isFull = current >= max;
  const refillCost = hearts?.refill_cost_gems;
  const canAfford = typeof gems === "number" && typeof refillCost === "number" && gems >= refillCost;

  const handleRefill = async () => {
    if (isFull || isSubmitting) return;

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      await api.refillHearts();
      queryClient.invalidateQueries({ queryKey: queryKeys.me });
      queryClient.invalidateQueries({ queryKey: queryKeys.path });
      onClose();
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === "INSUFFICIENT_GEMS") {
          setErrorMsg("You do not have enough gems to refill hearts.");
        } else {
          setErrorMsg(err.message);
        }
      } else {
        setErrorMsg("Failed to refill hearts. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="relative w-full max-w-sm rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-ink-soft hover:text-ink font-black text-sm p-1"
        >
          ✕
        </button>

        {/* Heart Icon */}
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-danger-light text-danger">
          <HeartIcon className="h-12 w-12 fill-danger" />
        </div>

        <h3 className="mt-4 text-2xl font-black text-ink">
          {isFull ? "Hearts are full!" : "Refill Hearts"}
        </h3>

        <div className="mt-2 text-sm font-bold text-ink-soft">
          {current} / {max} Hearts
        </div>

        {/* Regeneration Countdown */}
        {!isFull && isRegenerating && formatted && (
          <div className="mt-4 rounded-2xl bg-canvas p-3">
            <span className="text-xs font-bold text-ink-soft">Next heart in:</span>
            <div className="font-mono text-xl font-black text-danger">
              {formatted}
            </div>
            <p className="mt-1 text-[11px] text-ink-soft">
              Hearts regenerate automatically over time.
            </p>
          </div>
        )}

        {isFull && (
          <p className="mt-3 text-xs font-semibold text-ink-soft">
            You don&apos;t need to refill right now! Keep practicing to maintain your streak.
          </p>
        )}

        {errorMsg && (
          <div className="mt-3 rounded-xl bg-danger-light p-2.5 text-xs font-bold text-danger">
            {errorMsg}
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex flex-col gap-3">
          {!isFull ? (
            <button
              type="button"
              disabled={!canAfford || isSubmitting}
              onClick={handleRefill}
              className={`flex w-full items-center justify-center gap-2 rounded-2xl border-b-4 py-3.5 text-sm font-black uppercase tracking-wider transition ${
                !canAfford || isSubmitting
                  ? "cursor-not-allowed border-[#c5c5c5] bg-locked text-locked-ink"
                  : "border-sky-shadow bg-sky text-white hover:brightness-105 active:translate-y-1 active:border-b-0 shadow-md"
              }`}
            >
              <GemIcon className="h-5 w-5 fill-white" />
              <span>
                {isSubmitting
                  ? "Refilling..."
                  : typeof refillCost === "number"
                  ? !canAfford
                    ? `Need ${refillCost} Gems (Have ${gems ?? 0})`
                    : `Refill for ${refillCost} Gems`
                  : "Refill Hearts"}
              </span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="w-full rounded-2xl border-b-4 border-brand-shadow bg-brand py-3.5 text-sm font-black uppercase tracking-wider text-white shadow-md transition hover:brightness-105 active:translate-y-1 active:border-b-0"
            >
              Got It
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-2xl border-2 border-line bg-surface py-2.5 text-xs font-black uppercase tracking-wider text-ink-soft hover:bg-canvas transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
