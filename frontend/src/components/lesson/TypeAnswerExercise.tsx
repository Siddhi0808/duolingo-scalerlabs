"use client";

import { useRef, useEffect } from "react";
import type { TypeAnswerPayload } from "@/lib/api/types";

interface TypeAnswerExerciseProps {
  prompt: string;
  payload: TypeAnswerPayload;
  text: string;
  onChangeText: (text: string) => void;
  disabled: boolean;
}

const SPANISH_SPECIALS = ["á", "é", "í", "ó", "ú", "ñ", "¿", "¡"];

export function TypeAnswerExercise({
  prompt,
  payload,
  text,
  onChangeText,
  disabled,
}: TypeAnswerExerciseProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  const handleSpecialChar = (char: string) => {
    if (disabled || !textareaRef.current) return;
    const start = textareaRef.current.selectionStart || text.length;
    const end = textareaRef.current.selectionEnd || text.length;
    const next = text.slice(0, start) + char + text.slice(end);
    onChangeText(next);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(start + 1, start + 1);
      }
    }, 0);
  };

  return (
    <div className="mx-auto w-full max-w-xl space-y-6">
      <h2 className="text-2xl font-black tracking-tight text-ink sm:text-3xl">{prompt}</h2>

      {/* Source sentence prompt with Duolingo speech bubble */}
      <div className="flex items-center gap-3.5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-light text-2xl shadow-xs">
          🦉
        </div>
        <div className="relative rounded-2xl border-2 border-line bg-surface px-5 py-3 text-lg font-black text-ink shadow-xs">
          {payload.source_text}
          {/* Bubble pointer to avatar */}
          <div className="absolute top-1/2 -left-2 -translate-y-1/2 border-y-6 border-r-8 border-y-transparent border-r-line" />
          <div className="absolute top-1/2 -left-1.5 -translate-y-1/2 border-y-5 border-r-7 border-y-transparent border-r-surface" />
        </div>
      </div>

      {/* Input area */}
      <div className="space-y-3">
        <textarea
          ref={textareaRef}
          value={text}
          disabled={disabled}
          onChange={(e) => onChangeText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              // Prevent inserting newline into textarea.
              // FeedbackSheet owns the single global Enter submission handler.
              e.preventDefault();
            }
          }}
          placeholder="Type in Spanish..."
          rows={3}
          className="w-full resize-none rounded-2xl border-2 border-b-4 border-line bg-surface p-4 text-xl font-black text-ink placeholder:text-locked-ink focus:border-sky-shadow focus:bg-sky-light/10 focus:outline-hidden transition shadow-xs"
        />

        {/* Special characters keyboard row for Spanish */}
        {payload.answer_language === "es" && (
          <div className="flex flex-wrap gap-2 pt-1">
            {SPANISH_SPECIALS.map((char) => (
              <button
                key={char}
                type="button"
                disabled={disabled}
                onClick={() => handleSpecialChar(char)}
                className="h-11 w-11 rounded-xl border-2 border-b-4 border-line bg-surface text-lg font-black text-ink hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2 transition shadow-xs"
              >
                {char}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
