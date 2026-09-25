"use client";

import { FlameIcon, LightningIcon, TargetIcon, TrophyIcon } from "@/components/common/Icons";
import type { CompletionRewards } from "@/lib/api/types";

interface LessonCompleteScreenProps {
  rewards: CompletionRewards;
  onFinish: () => void;
}

export function LessonCompleteScreen({
  rewards,
  onFinish,
}: LessonCompleteScreenProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface p-4 text-center">
      <div className="w-full max-w-lg space-y-6">
        {/* Celebration Header */}
        <div className="space-y-2">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-gold/20 text-gold-shadow animate-bounce">
            <TrophyIcon className="h-14 w-14 fill-gold" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-ink sm:text-4xl">
            Lesson Complete!
          </h1>
          <p className="text-sm font-bold text-ink-soft">
            {rewards.first_completion
              ? "Great job! You earned XP and kept your streak alive."
              : "Lesson review complete!"}
          </p>
        </div>

        {/* Rewards Summary Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {/* XP Card */}
          <div className="rounded-2xl border-2 border-line bg-canvas p-4 text-center shadow-xs">
            <div className="flex items-center justify-center text-gold">
              <LightningIcon className="h-6 w-6 fill-gold" />
            </div>
            <div className="mt-2 text-2xl font-black text-ink">
              +{rewards.xp_awarded}
            </div>
            <div className="text-xs font-bold uppercase tracking-wider text-ink-soft">
              XP Earned
            </div>
          </div>

          {/* Streak Card */}
          <div className="rounded-2xl border-2 border-line bg-canvas p-4 text-center shadow-xs">
            <div className="flex items-center justify-center text-flame">
              <FlameIcon className="h-6 w-6 fill-flame" />
            </div>
            <div className="mt-2 text-2xl font-black text-ink">
              {rewards.streak.after}
            </div>
            <div className="text-xs font-bold uppercase tracking-wider text-ink-soft">
              {rewards.streak.extended ? "Day Streak! 🔥" : "Day Streak"}
            </div>
          </div>

          {/* Daily Goal Card */}
          <div className="rounded-2xl border-2 border-line bg-canvas p-4 text-center shadow-xs">
            <div className="flex items-center justify-center text-sky">
              <TargetIcon className="h-6 w-6 fill-sky" />
            </div>
            <div className="mt-2 text-2xl font-black text-ink">
              {rewards.daily_goal.today_xp} / {rewards.daily_goal.goal_xp}
            </div>
            <div className="text-xs font-bold uppercase tracking-wider text-ink-soft">
              {rewards.daily_goal.completed ? "Goal Met! 🎯" : "Daily XP"}
            </div>
          </div>
        </div>

        {/* Newly Unlocked Achievements */}
        {rewards.new_achievements.length > 0 && (
          <div className="rounded-2xl border-2 border-gold-shadow/30 bg-gold/10 p-4 text-left">
            <h3 className="text-xs font-black uppercase tracking-wider text-gold-shadow">
              New Achievement Unlocked!
            </h3>
            <div className="mt-3 space-y-2">
              {rewards.new_achievements.map((ach) => (
                <div
                  key={ach.code}
                  className="flex items-center gap-3 rounded-xl bg-surface p-2.5 shadow-xs"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gold/20 text-gold-shadow">
                    <TrophyIcon className="h-5 w-5 fill-gold-shadow" />
                  </div>
                  <div>
                    <h4 className="text-sm font-black text-ink">{ach.title}</h4>
                    <p className="text-xs font-bold text-ink-soft">
                      {ach.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Continue Button */}
        <div className="pt-4">
          <button
            type="button"
            onClick={onFinish}
            className="w-full rounded-2xl border-b-4 border-brand-shadow bg-brand py-4 text-base font-black uppercase tracking-wider text-white shadow-lg transition hover:brightness-105 active:translate-y-1 active:border-b-0"
          >
            Continue to Learning Path
          </button>
        </div>
      </div>
    </div>
  );
}
