import { LightningIcon, TrophyIcon } from "@/components/common/Icons";
import type { DailyGoal } from "@/lib/api/types";

interface DailyGoalCardProps {
  goal: DailyGoal | undefined;
}

export function DailyGoalCard({ goal }: DailyGoalCardProps) {
  if (!goal) return null;

  const percent = Math.min(100, Math.floor((goal.today_xp / goal.goal_xp) * 100));

  return (
    <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LightningIcon className="h-5 w-5 fill-gold" />
          <h3 className="text-sm font-extrabold uppercase tracking-wider text-ink">
            Daily Goal
          </h3>
        </div>
        {goal.completed && (
          <span className="flex items-center gap-1 rounded-full bg-gold/15 px-2 py-0.5 text-xs font-black text-gold-shadow">
            <TrophyIcon className="h-3.5 w-3.5 fill-gold-shadow" />
            Done!
          </span>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-xs font-bold text-ink-soft">
        <span>Earn XP today</span>
        <span>
          {goal.today_xp} / {goal.goal_xp} XP
        </span>
      </div>

      <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-line">
        <div
          className={`h-full transition-all duration-500 ${
            goal.completed ? "bg-gold" : "bg-brand"
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
