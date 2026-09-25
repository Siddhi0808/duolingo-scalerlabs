"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { GemIcon, HeartIcon } from "@/components/common/Icons";
import { useToast, type ToastOptions } from "@/components/common/Toast";
import { api, ApiClientError } from "@/lib/api/client";
import { queryKeys, useHeartCountdown } from "@/lib/api/hooks";
import type { HeartInfo, HeartRefillResponse } from "@/lib/api/types";

/** Confirmation shown after any successful refill (header modal or out-of-hearts modal). */
export function refillSuccessToast(res: HeartRefillResponse): ToastOptions {
  return {
    title: "Hearts refilled!",
    description: `${res.hearts.current}/${res.hearts.max} hearts · ${res.gems} gems left`,
    icon: <HeartIcon className="h-5 w-5 fill-heart" />,
  };
}

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
  const showToast = useToast();
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
      const res = await api.refillHearts();
      queryClient.invalidateQueries({ queryKey: queryKeys.me });
      queryClient.invalidateQueries({ queryKey: queryKeys.path });
      if (res.refilled) showToast(refillSuccessToast(res));
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
      <div className="relative w-full max-w-sm rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-2xl animate-pop">
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-xl text-sm font-black text-ink-soft transition hover:bg-canvas hover:text-ink"
        >
          ✕
        </button>

        <h3 className="mt-2 text-2xl font-black text-ink">
          {isFull ? "Hearts are full!" : "Refill hearts"}
        </h3>

        {/* One icon per heart: filled for hearts you have, grey for missing ones */}
        <div
          className="mt-4 flex justify-center gap-1.5"
          role="img"
          aria-label={`${current} of ${max} hearts`}
        >
          {Array.from({ length: max }, (_, i) => (
            <HeartIcon
              key={i}
              className={`h-9 w-9 ${i < current ? "fill-heart" : "fill-line"}`}
            />
          ))}
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
              Got it
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
