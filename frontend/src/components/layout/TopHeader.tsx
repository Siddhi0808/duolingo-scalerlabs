"use client";

import Link from "next/link";
import { useState } from "react";
import {
  FlameIcon,
  GemIcon,
  HeartIcon,
  LightningIcon,
  SpanishFlag,
} from "@/components/common/Icons";
import { HeartRefillModal } from "@/components/hearts/HeartRefillModal";
import { useHeartCountdown } from "@/lib/api/hooks";
import type { MeResponse } from "@/lib/api/types";

interface TopHeaderProps {
  me: MeResponse | undefined;
  isLoading?: boolean;
}

export function TopHeader({ me, isLoading }: TopHeaderProps) {
  const [showHeartModal, setShowHeartModal] = useState(false);
  const { formatted, isRegenerating } = useHeartCountdown(me?.hearts);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-line bg-surface/95 px-4 backdrop-blur-sm sm:px-6">
        {/* Course indicator */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-xl border border-line px-3 py-1.5 transition hover:bg-canvas"
          >
            <SpanishFlag className="h-4 w-6 rounded-xs shadow-xs" />
            <span className="hidden text-sm font-extrabold text-ink sm:inline">Spanish</span>
          </Link>
        </div>

        {/* Counters: Streak, XP, Gems, Hearts */}
        <div className="flex items-center gap-1 sm:gap-4">
          {/* Streak */}
          <Link
            href="/profile"
            title={me ? `${me.streak.current}-day streak (Longest: ${me.streak.longest})` : "Streak"}
            className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-flame transition hover:bg-canvas sm:px-3 sm:py-1.5"
          >
            <FlameIcon
              className={`h-6 w-6 ${
                me && me.streak.current > 0 ? "fill-flame" : "fill-locked-ink"
              }`}
            />
            <span
              className={`text-base font-extrabold ${
                me && me.streak.current > 0 ? "text-flame" : "text-locked-ink"
              }`}
            >
              {isLoading || !me ? "—" : me.streak.current}
            </span>
          </Link>

          {/* Total XP */}
          <Link
            href="/profile"
            title={me ? `${me.xp_total} total XP` : "Total XP"}
            className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-gold-shadow transition hover:bg-canvas sm:px-3 sm:py-1.5"
          >
            <LightningIcon className="h-6 w-6 fill-gold" />
            <span className="text-base font-extrabold">
              {isLoading || !me ? "—" : me.xp_total}
            </span>
          </Link>

          {/* Gems */}
          <Link
            href="/profile"
            title={me ? `${me.gems} gems` : "Gems"}
            className="flex items-center gap-1.5 rounded-xl px-2 py-1 text-gem transition hover:bg-canvas sm:px-3 sm:py-1.5"
          >
            <GemIcon className="h-6 w-6 fill-gem" />
            <span className="text-base font-extrabold">
              {isLoading || !me ? "—" : me.gems}
            </span>
          </Link>

          {/* Hearts with Refill Trigger */}
          <button
            type="button"
            onClick={() => setShowHeartModal(true)}
            aria-label="Hearts status and refill"
            className={`flex items-center gap-1.5 rounded-xl px-2 py-1 transition hover:bg-canvas active:translate-y-0.5 sm:px-3 sm:py-1.5 ${
              me && me.hearts.current === 0 ? "text-locked-ink" : "text-heart"
            }`}
          >
            {/* Grey at zero, like the streak counter and the lesson header */}
            <HeartIcon
              className={`h-6 w-6 ${me && me.hearts.current === 0 ? "fill-locked-ink" : "fill-heart"}`}
            />
            <span className="text-base font-extrabold">
              {isLoading || !me ? "—" : me.hearts.current}
            </span>
            {isRegenerating && formatted && (
              <span className="ml-1 hidden rounded-md bg-danger-light px-1.5 py-0.5 text-xs font-bold text-danger sm:inline">
                {formatted}
              </span>
            )}
          </button>

          {/* User Avatar (phones reach the profile via the bottom nav) */}
          {me && (
            <Link
              href="/profile"
              title={`${me.display_name} (@${me.username})`}
              className="ml-1 hidden h-9 w-9 items-center sm:flex justify-center rounded-full text-xs font-black text-white shadow-xs transition hover:opacity-90 active:scale-95"
              style={{ backgroundColor: me.avatar_color }}
            >
              {me.display_name.charAt(0).toUpperCase()}
            </Link>
          )}
        </div>
      </header>

      {/* Shared Heart Refill Modal */}
      <HeartRefillModal
        isOpen={showHeartModal}
        onClose={() => setShowHeartModal(false)}
        hearts={me?.hearts}
        gems={me?.gems}
      />
    </>
  );
}
