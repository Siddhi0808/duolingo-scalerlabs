"use client";

import { useEffect } from "react";
import { CheckIcon } from "@/components/common/Icons";
import type { AnswerResult } from "@/lib/api/types";

interface FeedbackSheetProps {
  canCheck: boolean;
  isSubmitting: boolean;
  result: AnswerResult | null;
  onCheck: () => void;
  onContinue: () => void;
}

export function FeedbackSheet({
  canCheck,
  isSubmitting,
  result,
  onCheck,
  onContinue,
}: FeedbackSheetProps) {
  // Single submission owner for Enter key across all exercise types:
  // - When awaiting check: submits answer if canCheck && !isSubmitting
  // - When feedback is shown (result): advances to next exercise
  // - Shift+Enter is preserved to allow standard multiline behavior
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Enter" && !e.shiftKey) {
        if (result) {
          e.preventDefault();
          onContinue();
        } else if (canCheck && !isSubmitting) {
          e.preventDefault();
          onCheck();
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canCheck, isSubmitting, result, onCheck, onContinue]);

  // Evaluated state
  if (result) {
    const isCorrect = result.correct;

    return (
      <div
        className={`fixed inset-x-0 bottom-0 z-30 border-t-2 px-4 py-5 shadow-2xl transition-all sm:px-8 animate-slide-up ${
          isCorrect
            ? "border-brand-shadow/40 bg-brand-light"
            : "border-danger-shadow/40 bg-danger-light"
        }`}
      >
        <div className="mx-auto flex max-w-4xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-start gap-4">
            <div
              className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full shadow-xs ${
                isCorrect ? "bg-brand text-white shadow-brand/30" : "bg-danger text-white shadow-danger/30"
              }`}
            >
              {isCorrect ? (
                <CheckIcon className="h-7 w-7 stroke-white stroke-[3.5]" />
              ) : (
                <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
            </div>

            <div>
              <h3
                className={`text-2xl font-black tracking-tight ${
                  isCorrect ? "text-brand-shadow" : "text-danger-shadow"
                }`}
              >
                {isCorrect ? "Nicely done!" : "Incorrect"}
              </h3>

              {!isCorrect && (
                <p className="mt-1 text-base font-black text-danger-shadow">
                  Correct answer: <span className="underline decoration-2">{result.correct_answer}</span>
                </p>
              )}

              {result.note && (
                <p className="mt-1 text-xs font-bold text-ink-soft">
                  {result.note}
                </p>
              )}

              {result.explanation && (
                <p className="mt-1 text-xs font-bold text-ink-soft">
                  {result.explanation}
                </p>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onContinue}
            className={`w-full sm:w-auto min-w-44 rounded-2xl border-b-4 px-8 py-3.5 text-base font-black uppercase tracking-wider text-white shadow-md transition active:translate-y-1 active:border-b-0 ${
              isCorrect
                ? "border-brand-shadow bg-brand hover:brightness-105"
                : "border-danger-shadow bg-danger hover:brightness-105"
            }`}
          >
            Continue ↵
          </button>
        </div>
      </div>
    );
  }

  // Pre-submit Check button bar
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface px-4 py-4 sm:px-8">
      <div className="mx-auto flex max-w-4xl items-center justify-between">
        <span className="hidden text-xs font-black uppercase tracking-wider text-locked-ink sm:inline">
          {canCheck ? "Press Enter ↵ to check" : "Select an answer to continue"}
        </span>

        <button
          type="button"
          disabled={!canCheck || isSubmitting}
          onClick={onCheck}
          className={`w-full sm:w-auto min-w-44 rounded-2xl border-b-4 px-8 py-3.5 text-base font-black uppercase tracking-wider transition ${
            !canCheck || isSubmitting
              ? "cursor-not-allowed border-[#c5c5c5] bg-locked text-locked-ink"
              : "border-brand-shadow bg-brand text-white hover:brightness-105 active:translate-y-1 active:border-b-0 shadow-md"
          }`}
        >
          {isSubmitting ? "Checking..." : "Check"}
        </button>
      </div>
    </div>
  );
}
