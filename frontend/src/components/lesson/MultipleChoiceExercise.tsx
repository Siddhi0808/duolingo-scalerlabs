"use client";

import { useEffect } from "react";
import type { MultipleChoicePayload } from "@/lib/api/types";

interface MultipleChoiceExerciseProps {
  prompt: string;
  payload: MultipleChoicePayload;
  selectedOptionId: string | null;
  onSelect: (optionId: string) => void;
  disabled: boolean;
  isGraded?: boolean;
  isCorrect?: boolean;
}

export function MultipleChoiceExercise({
  prompt,
  payload,
  selectedOptionId,
  onSelect,
  disabled,
  isGraded,
  isCorrect,
}: MultipleChoiceExerciseProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (disabled) return;
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= payload.options.length) {
        onSelect(payload.options[num - 1].id);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [payload.options, onSelect, disabled]);

  return (
    <div className="mx-auto w-full max-w-xl space-y-6">
      <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{prompt}</h2>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {payload.options.map((option, idx) => {
          const isSelected = selectedOptionId === option.id;
          const buttonStyle = isGraded && isSelected
            ? isCorrect
              ? "border-brand-shadow bg-brand-light text-brand-shadow shadow-xs"
              : "border-danger-shadow bg-danger-light text-danger shadow-xs"
            : isSelected
            ? "border-sky-shadow bg-sky-light/50 text-sky shadow-xs"
            : "border-line bg-surface text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2 shadow-xs";

          return (
            <button
              key={option.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(option.id)}
              className={`group flex items-center justify-between rounded-2xl border-2 border-b-4 p-4 text-left transition-all ${buttonStyle}`}
            >
              <div className="flex items-center gap-3.5">
                {/* Keyboard shortcut number indicator */}
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-xl border-2 text-xs font-black transition ${
                    isGraded && isSelected
                      ? isCorrect
                        ? "border-brand-shadow bg-brand text-white shadow-xs"
                        : "border-danger-shadow bg-danger text-white shadow-xs"
                      : isSelected
                      ? "border-sky-shadow bg-sky text-white shadow-xs"
                      : "border-line bg-canvas text-ink-soft group-hover:border-slate-300"
                  }`}
                >
                  {idx + 1}
                </span>

                {/* Inherits the card colour, so selected/graded states tint the text too */}
                <span className="text-lg font-black tracking-tight">{option.text}</span>
              </div>

              {option.image && (
                <span className="text-3xl">{option.image}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
