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
  isGraded?: boolean;
  isCorrect?: boolean;
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
  isGraded = false,
  isCorrect,
}: MatchingPairsExerciseProps) {
  const getPairIndex = (leftId?: string, rightId?: string) => {
    if (leftId) {
      const idx = pairs.findIndex((p) => p[0] === leftId);
      return idx >= 0 ? idx + 1 : null;
    }
    if (rightId) {
      const idx = pairs.findIndex((p) => p[1] === rightId);
      return idx >= 0 ? idx + 1 : null;
    }
    return null;
  };

  return (
    <div className="mx-auto w-full max-w-xl space-y-6">
      <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{prompt}</h2>

      <div className="grid grid-cols-2 gap-4">
        {/* Left Column */}
        <div className="space-y-3">
          {payload.left.map((item) => {
            const pairIdx = getPairIndex(item.id, undefined);
            const isPaired = pairIdx !== null;
            const isSelected = selectedLeftId === item.id;

            let buttonStyle = "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2";
            let badgeStyle = "bg-slate-200 text-slate-600 border border-slate-300";

            if (isGraded && isPaired) {
              if (isCorrect) {
                buttonStyle = "border-brand-shadow bg-brand-light text-brand-shadow cursor-default";
                badgeStyle = "bg-brand text-white";
              } else {
                buttonStyle = "border-danger-shadow bg-danger-light text-danger cursor-default";
                badgeStyle = "bg-danger text-white";
              }
            } else if (isPaired) {
              buttonStyle = "border-slate-300 bg-slate-100 text-slate-600 cursor-pointer hover:bg-slate-200/70 border-b-2";
              badgeStyle = "bg-slate-200 text-slate-600 border border-slate-300";
            } else if (isSelected) {
              buttonStyle = "border-sky-shadow bg-sky-light text-sky active:translate-y-1 active:border-b-2";
            }

            return (
              <button
                key={item.id}
                type="button"
                disabled={disabled}
                onClick={() => {
                  if (isPaired) onUnpair(item.id);
                  else onSelectLeft(item.id);
                }}
                className={`relative flex items-center justify-center w-full rounded-2xl border-2 border-b-4 p-4 text-center font-black transition text-base shadow-xs ${buttonStyle}`}
              >
                <span>{item.text}</span>
                {pairIdx !== null && (
                  <span
                    className={`absolute right-3.5 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-black shadow-xs ${badgeStyle}`}
                  >
                    {pairIdx}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Right Column */}
        <div className="space-y-3">
          {payload.right.map((item) => {
            const pairIdx = getPairIndex(undefined, item.id);
            const isPaired = pairIdx !== null;
            const isSelected = selectedRightId === item.id;

            let buttonStyle = "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2";
            let badgeStyle = "bg-slate-200 text-slate-600 border border-slate-300";

            if (isGraded && isPaired) {
              if (isCorrect) {
                buttonStyle = "border-brand-shadow bg-brand-light text-brand-shadow cursor-default";
                badgeStyle = "bg-brand text-white";
              } else {
                buttonStyle = "border-danger-shadow bg-danger-light text-danger cursor-default";
                badgeStyle = "bg-danger text-white";
              }
            } else if (isPaired) {
              buttonStyle = "border-slate-300 bg-slate-100 text-slate-600 cursor-pointer hover:bg-slate-200/70 border-b-2";
              badgeStyle = "bg-slate-200 text-slate-600 border border-slate-300";
            } else if (isSelected) {
              buttonStyle = "border-sky-shadow bg-sky-light text-sky active:translate-y-1 active:border-b-2";
            }

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
                className={`relative flex items-center justify-center w-full rounded-2xl border-2 border-b-4 p-4 text-center font-black transition text-base shadow-xs ${buttonStyle}`}
              >
                <span>{item.text}</span>
                {pairIdx !== null && (
                  <span
                    className={`absolute right-3.5 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-black shadow-xs ${badgeStyle}`}
                  >
                    {pairIdx}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
