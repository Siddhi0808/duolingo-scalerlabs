"use client";

import type { CSSProperties, ReactNode } from "react";
import {
  FlameIcon,
  LightningIcon,
  TargetIcon,
  TrophyIcon,
  getAchievementIcon,
} from "@/components/common/Icons";
import type { CompletionRewards } from "@/lib/api/types";

interface LessonCompleteScreenProps {
  rewards: CompletionRewards;
  onFinish: () => void;
}

// Pops in once, one after another (fill-mode "both" keeps it hidden during its delay).
const popIn = (delayMs: number): CSSProperties => ({
  animationDelay: `${delayMs}ms`,
  animationFillMode: "both",
});

/** Duolingo-style reward tile: coloured label strip over a white body. */
function RewardTile({
  label,
  value,
  icon,
  tone,
  delayMs,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  tone: { border: string; strip: string; text: string };
  delayMs: number;
}) {
  return (
    <div
      className={`overflow-hidden rounded-2xl border-2 ${tone.border} animate-pop`}
      style={popIn(delayMs)}
    >
      <div
        className={`${tone.strip} px-1 py-1 text-[10px] font-black uppercase tracking-wide text-white sm:text-xs`}
      >
        {label}
      </div>
      <div className="flex items-center justify-center gap-1.5 bg-surface py-3 sm:py-4">
        {icon}
        <span className={`text-xl font-black sm:text-2xl ${tone.text}`}>{value}</span>
      </div>
    </div>
  );
}

export function LessonCompleteScreen({ rewards, onFinish }: LessonCompleteScreenProps) {
  const { streak, daily_goal: goal } = rewards;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface p-4 text-center">
      <div className="w-full max-w-lg space-y-5 sm:space-y-6">
        {/* Celebration header */}
        <div className="space-y-2">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-gold/20 text-gold-shadow animate-bounce-once sm:h-24 sm:w-24">
            <TrophyIcon className="h-12 w-12 fill-gold sm:h-14 sm:w-14" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-gold-shadow sm:text-4xl">
            Lesson complete!
          </h1>
          <p className="text-sm font-bold text-ink-soft">
            {rewards.first_completion
              ? "Great job! You earned XP and kept your streak alive."
              : "Lesson reviewed. Keep practising!"}
          </p>
        </div>

        {/* Rewards: three tiles in one row at every width */}
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <RewardTile
            label="XP earned"
            value={`+${rewards.xp_awarded}`}
            icon={<LightningIcon className="h-5 w-5 fill-gold sm:h-6 sm:w-6" />}
            tone={{ border: "border-gold", strip: "bg-gold", text: "text-gold-shadow" }}
            delayMs={150}
          />
          <RewardTile
            label={streak.extended ? "Streak +1" : "Day streak"}
            value={`${streak.after}`}
            icon={<FlameIcon className="h-5 w-5 fill-flame sm:h-6 sm:w-6" />}
            tone={{ border: "border-flame", strip: "bg-flame", text: "text-flame" }}
            delayMs={300}
          />
          <RewardTile
            label={goal.completed ? "Goal met" : "Daily goal"}
            value={`${goal.today_xp}/${goal.goal_xp}`}
            icon={<TargetIcon className="h-5 w-5 fill-sky sm:h-6 sm:w-6" />}
            tone={{ border: "border-sky", strip: "bg-sky", text: "text-sky" }}
            delayMs={450}
          />
        </div>

        {/* Newly unlocked achievements */}
        {rewards.new_achievements.length > 0 && (
          <div
            className="rounded-2xl border-2 border-gold bg-gold/10 p-4 text-left animate-pop"
            style={popIn(600)}
          >
            <h3 className="text-xs font-black uppercase tracking-wider text-gold-shadow">
              {rewards.new_achievements.length > 1
                ? "New achievements unlocked!"
                : "New achievement unlocked!"}
            </h3>
            <div className="mt-3 space-y-2">
              {rewards.new_achievements.map((ach) => (
                <div
                  key={ach.code}
                  className="flex items-center gap-3 rounded-xl border-2 border-gold/30 bg-surface p-2.5"
                >
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gold/20">
                    {getAchievementIcon(ach.icon, "h-7 w-7")}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-sm font-black text-ink">{ach.title}</h4>
                    <p className="text-xs font-bold text-ink-soft">{ach.description}</p>
                  </div>
                  <span className="shrink-0 rounded-lg bg-gold/20 px-2 py-0.5 text-[10px] font-black uppercase text-gold-shadow">
                    Tier {ach.tier}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Continue */}
        <button
          type="button"
          onClick={onFinish}
          className="w-full rounded-2xl border-b-4 border-brand-shadow bg-brand py-4 text-base font-black uppercase tracking-wider text-white shadow-lg transition hover:brightness-105 active:translate-y-1 active:border-b-0"
        >
          Continue
        </button>
      </div>
    </div>
  );
}
