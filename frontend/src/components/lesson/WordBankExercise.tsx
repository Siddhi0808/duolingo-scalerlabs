"use client";

import type { WordBankPayload } from "@/lib/api/types";

interface WordBankExerciseProps {
  prompt: string;
  payload: WordBankPayload;
  selectedTileIds: string[];
  onSelectTile: (tileId: string) => void;
  onRemoveTile: (tileId: string) => void;
  disabled: boolean;
}

export function WordBankExercise({
  prompt,
  payload,
  selectedTileIds,
  onSelectTile,
  onRemoveTile,
  disabled,
}: WordBankExerciseProps) {
  // Map of tile id to tile object
  const tileMap = new Map(payload.tiles.map((t) => [t.id, t]));

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

      {/* Ruled answer area: a 2px line every 56px row, 4px under each row of 46px-tall
          tiles (10px row gap), so placed words sit on the lines. */}
      <div
        aria-label="Your answer"
        className="flex min-h-28 w-full flex-wrap content-start items-start gap-x-2 gap-y-[10px] bg-[linear-gradient(to_bottom,transparent_50px,var(--color-line)_50px,var(--color-line)_52px)] bg-size-[100%_56px]"
      >
        {selectedTileIds.map((tileId) => {
          const tile = tileMap.get(tileId);
          if (!tile) return null;

          return (
            <button
              key={tile.id}
              type="button"
              disabled={disabled}
              onClick={() => onRemoveTile(tile.id)}
              className="rounded-xl border-2 border-b-4 border-line bg-surface px-4 py-2 text-base font-black text-ink shadow-xs hover:border-danger hover:text-danger active:translate-y-1 active:border-b-2 transition"
            >
              {tile.text}
            </button>
          );
        })}
      </div>

      {/* Available tiles pool */}
      <div className="flex flex-wrap justify-center gap-2.5 pt-4">
        {payload.tiles.map((tile) => {
          const isUsed = selectedTileIds.includes(tile.id);

          if (isUsed) {
            return (
              <div
                key={tile.id}
                aria-hidden
                className="rounded-xl border-2 border-b-4 border-transparent bg-line/70 px-4 py-2 text-base font-black text-transparent select-none"
              >
                {tile.text}
              </div>
            );
          }

          return (
            <button
              key={tile.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectTile(tile.id)}
              className="rounded-xl border-2 border-b-4 border-line bg-surface px-4 py-2 text-base font-black text-ink shadow-xs hover:bg-canvas hover:border-slate-300 active:translate-y-1 active:border-b-2 transition"
            >
              {tile.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}
