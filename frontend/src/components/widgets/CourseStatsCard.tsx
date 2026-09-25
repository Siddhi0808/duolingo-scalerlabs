import { LightningIcon, StarIcon } from "@/components/common/Icons";
import type { LessonStats } from "@/lib/api/types";

interface CourseStatsCardProps {
  stats: LessonStats | undefined;
  xpTotal: number | undefined;
}

export function CourseStatsCard({ stats, xpTotal }: CourseStatsCardProps) {
  if (!stats) return null;

  return (
    <div className="rounded-2xl border-2 border-line bg-surface p-4 shadow-xs">
      <h3 className="text-sm font-extrabold uppercase tracking-wider text-ink">
        Statistics
      </h3>

      <div className="mt-3 grid grid-cols-2 gap-3 text-left">
        <div className="rounded-xl border border-line bg-canvas p-2.5">
          <div className="flex items-center gap-1.5 text-xs font-bold text-ink-soft">
            <LightningIcon className="h-4 w-4 fill-gold" />
            <span>Total XP</span>
          </div>
          <div className="mt-1 text-lg font-black text-ink">{xpTotal ?? 0}</div>
        </div>

        <div className="rounded-xl border border-line bg-canvas p-2.5">
          <div className="flex items-center gap-1.5 text-xs font-bold text-ink-soft">
            <StarIcon className="h-4 w-4 fill-brand" />
            <span>Lessons</span>
          </div>
          <div className="mt-1 text-lg font-black text-ink">
            {stats.lessons_completed} / {stats.total_lessons}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-canvas p-2.5">
          <div className="text-xs font-bold text-ink-soft">Skills done</div>
          <div className="mt-1 text-lg font-black text-ink">
            {stats.skills_completed} / {stats.total_skills}
          </div>
        </div>

        <div className="rounded-xl border border-line bg-canvas p-2.5">
          <div className="text-xs font-bold text-ink-soft">Perfect lessons</div>
          <div className="mt-1 text-lg font-black text-ink">
            {stats.perfect_lessons}
          </div>
        </div>
      </div>
    </div>
  );
}
