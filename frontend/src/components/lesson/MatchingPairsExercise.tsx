"use client";

import type { MatchingPairsPayload } from "@/lib/api/types";

interface MatchingPairsExerciseProps {
  prompt: string;
  payload: MatchingPairsPayload;
  pairs: [string, string][];
  selectedLeftId: string | null;
  selectedRightId: string | null;
  onSelectLeft: (id: string) => void;
  onSelectRight: (id: string) => void;
  onUnpair: (leftId: string) => void;
  disabled: boolean;
}

export function MatchingPairsExercise({
  prompt,
  payload,
  pairs,
  selectedLeftId,
  selectedRightId,
  onSelectLeft,
  onSelectRight,
  onUnpair,
  disabled,
}: MatchingPairsExerciseProps) {
  const pairedLeftIds = new Set(pairs.map((p) => p[0]));
  const pairedRightIds = new Set(pairs.map((p) => p[1]));

  return (
    <div className="mx-auto w-full max-w-xl space-y-6">
      <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{prompt}</h2>

      <div className="grid grid-cols-2 gap-4">
        {/* Left Column */}
        <div className="space-y-3">
          {payload.left.map((item) => {
            const isPaired = pairedLeftIds.has(item.id);
            const isSelected = selectedLeftId === item.id;

            return (
              <button
                key={item.id}
                type="button"
                disabled={disabled}
                onClick={() => {
                  if (isPaired) onUnpair(item.id);
                  else onSelectLeft(item.id);
                }}
                className={`w-full rounded-2xl border-2 border-b-4 p-4 text-center font-black transition text-base shadow-xs ${
                  isPaired
                    ? "border-sky-shadow/60 bg-sky-light/40 text-sky font-black cursor-pointer"
                    : isSelected
                    ? "border-sky-shadow bg-sky-light text-sky active:translate-y-1 active:border-b-2"
                    : "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2"
                }`}
              >
                {item.text}
              </button>
            );
          })}
        </div>

        {/* Right Column */}
        <div className="space-y-3">
          {payload.right.map((item) => {
            const isPaired = pairedRightIds.has(item.id);
            const isSelected = selectedRightId === item.id;

            return (
              <button
                key={item.id}
                type="button"
                disabled={disabled}
                onClick={() => {
                  if (isPaired) {
                    const found = pairs.find((p) => p[1] === item.id);
                    if (found) onUnpair(found[0]);
                  } else {
                    onSelectRight(item.id);
                  }
                }}
                className={`w-full rounded-2xl border-2 border-b-4 p-4 text-center font-black transition text-base shadow-xs ${
                  isPaired
                    ? "border-sky-shadow/60 bg-sky-light/40 text-sky font-black cursor-pointer"
                    : isSelected
                    ? "border-sky-shadow bg-sky-light text-sky active:translate-y-1 active:border-b-2"
                    : "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2"
                }`}
              >
                {item.text}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
