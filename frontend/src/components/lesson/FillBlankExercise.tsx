"use client";

import type { FillBlankPayload } from "@/lib/api/types";

interface FillBlankExerciseProps {
  prompt: string;
  payload: FillBlankPayload;
  selectedText: string | null;
  onSelectText: (text: string) => void;
  disabled: boolean;
  isGraded?: boolean;
  isCorrect?: boolean;
}

export function FillBlankExercise({
  prompt,
  payload,
  selectedText,
  onSelectText,
  disabled,
  isGraded,
  isCorrect,
}: FillBlankExerciseProps) {
  return (
    <div className="mx-auto w-full max-w-xl space-y-6">
      <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{prompt}</h2>

      {/* Sentence with blank */}
      <div className="rounded-2xl border-2 border-line bg-canvas/60 p-6 shadow-xs">
        <div className="flex flex-wrap items-baseline gap-2.5 text-xl font-black text-ink">
          {payload.before && <span>{payload.before}</span>}

          {/* Gap slot */}
          <span
            className={`inline-flex min-w-24 items-center justify-center rounded-xl border-2 border-b-4 px-4 py-1.5 text-center transition-all ${
              selectedText
                ? isGraded
                  ? isCorrect
                    ? "border-brand-shadow bg-brand-light text-brand-shadow font-black"
                    : "border-danger-shadow bg-danger-light text-danger font-black"
                  : "border-sky-shadow bg-sky-light text-sky font-black"
                : "border-dashed border-line bg-surface text-transparent"
            }`}
          >
            {selectedText || "______"}
          </span>

          {payload.after && <span>{payload.after}</span>}
        </div>

        {payload.hint && (
          <p className="mt-4 text-xs font-black uppercase tracking-wider text-ink-soft">
            Hint: {payload.hint}
          </p>
        )}
      </div>

      {/* Options */}
      <div className="flex flex-wrap justify-center gap-3 pt-4">
        {payload.options.map((option) => {
          const isSelected = selectedText === option.text;
          const buttonStyle = isGraded && isSelected
            ? isCorrect
              ? "border-brand-shadow bg-brand-light text-brand-shadow shadow-xs"
              : "border-danger-shadow bg-danger-light text-danger shadow-xs"
            : isSelected
            ? "border-sky-shadow bg-sky-light text-sky shadow-xs"
            : "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2";

          return (
            <button
              key={option.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectText(option.text)}
              className={`rounded-2xl border-2 border-b-4 px-6 py-3.5 text-lg font-black transition shadow-xs ${buttonStyle}`}
            >
              {option.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}
