"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import {
  FlameIcon,
  GemIcon,
  HeartIcon,
  LightningIcon,
  SpanishFlag,
  StarIcon,
  TargetIcon,
  TrophyIcon,
  getAchievementIcon,
} from "@/components/common/Icons";
import { HeartRefillModal } from "@/components/hearts/HeartRefillModal";
import { ErrorState } from "@/components/common/ErrorState";
import { useMe } from "@/lib/api/hooks";
import type { AchievementProgress } from "@/lib/api/types";
import { ApiClientError } from "@/lib/api/client";

export default function ProfilePage() {
  const { data: me, error, isLoading, refetch } = useMe();
  const [showHeartModal, setShowHeartModal] = useState(false);
  const [selectedAchievement, setSelectedAchievement] = useState<AchievementProgress | null>(null);

  const errorCode = error instanceof ApiClientError ? error.code : "API_ERROR";
  const errorMessage = error instanceof Error ? error.message : "Failed to load profile";

  if (isLoading) {
    return (
      <AppShell me={me} isLoading={isLoading}>
        <div className="mx-auto max-w-4xl animate-pulse space-y-6 px-4 py-8">
          <div className="h-44 rounded-3xl bg-canvas" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 rounded-2xl bg-canvas" />
            ))}
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !me) {
    return (
      <AppShell me={me}>
        <div className="mx-auto max-w-xl px-4 py-16">
          <ErrorState code={errorCode} message={errorMessage} onRetry={() => refetch()} />
        </div>
      </AppShell>
    );
  }

  const unlockedCount = me.achievements.filter((a) => a.unlocked).length;
  const goalPercent = Math.min(
    100,
    Math.floor((me.daily_goal.today_xp / me.daily_goal.goal_xp) * 100)
  );

  return (
    <AppShell me={me}>
      <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 sm:px-6">
        {/* User Hero Identity Card */}
        <section className="flex flex-col items-center gap-6 rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-xs sm:flex-row sm:text-left">
          <div
            className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full text-3xl font-black text-white shadow-md"
            style={{ backgroundColor: me.avatar_color }}
          >
            {me.display_name.charAt(0).toUpperCase()}
          </div>

          <div className="flex-1 space-y-1">
            <h1 className="text-2xl font-black text-ink sm:text-3xl">
              {me.display_name}
            </h1>
            <p className="text-sm font-bold text-ink-soft">@{me.username}</p>

            <div className="mt-3 flex flex-wrap items-center justify-center gap-3 sm:justify-start">
              <span className="flex items-center gap-1.5 rounded-full border border-line bg-canvas px-3 py-1 text-xs font-extrabold text-ink">
                <SpanishFlag className="h-3.5 w-5 rounded-xs" />
                Learning Spanish
              </span>
              <span className="rounded-full bg-canvas px-3 py-1 text-xs font-bold text-ink-soft">
                {(() => {
                  try {
                    const [y, m, d] = me.today.split("-").map(Number);
                    if (y && m && d) {
                      const date = new Date(Date.UTC(y, m - 1, d));
                      return `Today · ${date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}`;
                    }
                  } catch {
                    // fallback
                  }
                  return `Today · ${me.today}`;
                })()}
              </span>
            </div>
          </div>
        </section>

        {/* Statistics Grid */}
        <section className="space-y-4">
          <h2 className="text-xl font-black text-ink">Statistics</h2>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {/* Streak Card */}
            <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
              <div className="flex items-center gap-2">
                <FlameIcon
                  className={`h-6 w-6 ${
                    me.streak.current > 0 ? "fill-flame" : "fill-locked-ink"
                  }`}
                />
                <span className="text-xs font-black uppercase tracking-wider text-ink-soft">
                  Streak
                </span>
              </div>
              <div className="mt-2 text-2xl font-black text-ink">
                {me.streak.current}{" "}
                <span className="text-xs font-extrabold text-ink-soft">days</span>
              </div>
              <div className="mt-1 text-xs font-bold text-ink-soft">
                Longest: {me.streak.longest} days
              </div>
            </div>

            {/* Total XP Card */}
            <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
              <div className="flex items-center gap-2">
                <LightningIcon className="h-6 w-6 fill-gold" />
                <span className="text-xs font-black uppercase tracking-wider text-ink-soft">
                  Total XP
                </span>
              </div>
              <div className="mt-2 text-2xl font-black text-ink">
                {me.xp_total}
              </div>
              <div className="mt-1 text-xs font-bold text-ink-soft">
                XP Earned
              </div>
            </div>

            {/* Lessons Completed */}
            <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
              <div className="flex items-center gap-2">
                <StarIcon className="h-6 w-6 fill-brand" />
                <span className="text-xs font-black uppercase tracking-wider text-ink-soft">
                  Lessons
                </span>
              </div>
              <div className="mt-2 text-2xl font-black text-ink">
                {me.stats.lessons_completed} / {me.stats.total_lessons}
              </div>
              <div className="mt-1 text-xs font-bold text-ink-soft">
                {me.stats.perfect_lessons} perfect
              </div>
            </div>

            {/* Skills Completed */}
            <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
              <div className="flex items-center gap-2">
                <TrophyIcon className="h-6 w-6 fill-purple" />
                <span className="text-xs font-black uppercase tracking-wider text-ink-soft">
                  Skills
                </span>
              </div>
              <div className="mt-2 text-2xl font-black text-ink">
                {me.stats.skills_completed} / {me.stats.total_skills}
              </div>
              <div className="mt-1 text-xs font-bold text-ink-soft">
                Skills done
              </div>
            </div>
          </div>

          {/* Daily Goal & Currency Row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Daily Goal Card */}
            <div className="rounded-2xl border-2 border-line bg-surface p-5 shadow-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TargetIcon className="h-6 w-6 fill-sky" />
                  <span className="text-sm font-black uppercase tracking-wider text-ink">
                    Daily Goal
                  </span>
                </div>
                {me.daily_goal.completed && (
                  <span className="rounded-full bg-gold/15 px-2.5 py-0.5 text-xs font-black text-gold-shadow">
                    Completed! 🎯
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-baseline justify-between text-sm font-extrabold text-ink-soft">
                <span>Today&apos;s XP</span>
                <span className="text-ink">
                  {me.daily_goal.today_xp} / {me.daily_goal.goal_xp} XP
                </span>
              </div>

              <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-line">
                <div
                  className={`h-full transition-all duration-500 ${
                    me.daily_goal.completed ? "bg-gold" : "bg-brand"
                  }`}
                  style={{ width: `${goalPercent}%` }}
                />
              </div>
            </div>

            {/* Resources (Hearts & Gems) */}
            <div className="flex items-center justify-between gap-4 rounded-2xl border-2 border-line bg-surface p-5 shadow-xs">
              {/* Hearts */}
              <div className="flex items-center gap-3">
                <HeartIcon className="h-8 w-8 fill-heart" />
                <div>
                  <div className="text-lg font-black text-ink">
                    {me.hearts.current} / {me.hearts.max}
                  </div>
                  {me.hearts.current < me.hearts.max ? (
                    <button
                      type="button"
                      onClick={() => setShowHeartModal(true)}
                      className="text-xs font-extrabold text-brand hover:underline"
                    >
                      Refill Hearts
                    </button>
                  ) : (
                    <span className="text-xs font-bold text-ink-soft">Full</span>
                  )}
                </div>
              </div>

              {/* Gems */}
              <div className="flex items-center gap-3">
                <GemIcon className="h-8 w-8 fill-gem" />
                <div>
                  <div className="text-lg font-black text-ink">{me.gems}</div>
                  <span className="text-xs font-bold text-ink-soft">Gems</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Achievements Showcase */}
        <section id="achievements" className="space-y-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-xl font-black text-ink">Achievements</h2>
            <span className="text-xs font-extrabold text-ink-soft">
              {unlockedCount} of {me.achievements.length} Unlocked
            </span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {Object.values(
              me.achievements.reduce<Record<string, AchievementProgress[]>>((acc, ach) => {
                acc[ach.title] = acc[ach.title] || [];
                acc[ach.title].push(ach);
                return acc;
              }, {})
            ).map((tiers) => {
              tiers.sort((a, b) => a.tier - b.tier);
              const ach = tiers.find((t) => !t.unlocked) || tiers[tiers.length - 1];
              const unlockedTiers = tiers.filter((t) => t.unlocked);
              const allUnlocked = unlockedTiers.length === tiers.length;
              const percent = Math.min(
                100,
                Math.floor((ach.current / ach.target) * 100)
              );

              return (
                <div
                  key={ach.code}
                  onClick={() => setSelectedAchievement(ach)}
                  className={`cursor-pointer rounded-2xl border-2 p-4 transition hover:brightness-102 ${
                    allUnlocked
                      ? "border-gold-shadow/30 bg-gold/5"
                      : "border-line bg-surface hover:bg-canvas"
                  }`}
                >
                  <div className="flex items-start gap-4">
                    {/* Badge Icon */}
                    <div
                      className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${
                        unlockedTiers.length > 0
                          ? "bg-gold/20 text-gold-shadow shadow-xs"
                          : "bg-canvas text-locked-ink"
                      }`}
                    >
                      {getAchievementIcon(ach.icon)}
                    </div>

                    <div className="flex-1 space-y-1 truncate">
                      <div className="flex items-center justify-between">
                        <h3 className="text-base font-black text-ink truncate">
                          {ach.title}
                        </h3>
                        <span className="rounded-md bg-canvas px-2 py-0.5 text-[10px] font-black uppercase text-ink-soft">
                          Tier {ach.tier} of {tiers.length}
                        </span>
                      </div>

                      <p className="text-xs font-semibold text-ink-soft truncate">
                        {ach.description}
                      </p>

                      {/* Status / Progress */}
                      {allUnlocked ? (
                        <div className="pt-1 text-[11px] font-black text-brand">
                          All Tiers Unlocked ✓
                        </div>
                      ) : (
                        <div className="pt-2">
                          <div className="flex items-center justify-between text-[10px] font-bold text-ink-soft">
                            <span>
                              {unlockedTiers.length > 0
                                ? `Tier ${unlockedTiers.length} done · Next`
                                : "Progress"}
                            </span>
                            <span>
                              {ach.current} / {ach.target}
                            </span>
                          </div>
                          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-line">
                            <div
                              className="h-full bg-brand transition-all duration-300"
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Shared Heart Refill Modal */}
      <HeartRefillModal
        isOpen={showHeartModal}
        onClose={() => setShowHeartModal(false)}
        hearts={me.hearts}
        gems={me.gems}
      />

      {/* Achievement Detail Dialog */}
      {selectedAchievement && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-sm rounded-3xl border-2 border-line bg-surface p-6 text-center shadow-2xl animate-pop">
            <div
              className={`mx-auto flex h-20 w-20 items-center justify-center rounded-3xl ${
                selectedAchievement.unlocked ? "bg-gold/20 shadow-md" : "bg-canvas"
              }`}
            >
              {getAchievementIcon(selectedAchievement.icon)}
            </div>

            <h3 className="mt-4 text-xl font-black text-ink">
              {selectedAchievement.title}
            </h3>
            <span className="mt-1 inline-block rounded-md bg-canvas px-2.5 py-0.5 text-xs font-black uppercase text-ink-soft">
              Tier {selectedAchievement.tier}
            </span>
            <p className="mt-2 text-sm font-semibold text-ink-soft">
              {selectedAchievement.description}
            </p>

            {selectedAchievement.unlocked ? (
              <div className="mt-4 rounded-xl bg-brand-light p-3 text-xs font-black text-brand-shadow">
                Unlocked on {new Date(selectedAchievement.unlocked_at || "").toLocaleDateString()} ✓
              </div>
            ) : (
              <div className="mt-4 rounded-xl bg-canvas p-3">
                <div className="flex items-center justify-between text-xs font-bold text-ink-soft">
                  <span>Progress to unlock</span>
                  <span>
                    {selectedAchievement.current} / {selectedAchievement.target}
                  </span>
                </div>
                <div className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full bg-brand"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.floor(
                          (selectedAchievement.current / selectedAchievement.target) * 100
                        )
                      )}%`,
                    }}
                  />
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => setSelectedAchievement(null)}
              className="mt-6 w-full rounded-2xl border-b-4 border-brand-shadow bg-brand py-3 text-sm font-black uppercase tracking-wider text-white shadow-md active:translate-y-1 active:border-b-0"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
