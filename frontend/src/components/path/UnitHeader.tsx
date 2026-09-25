import { LockIcon } from "@/components/common/Icons";
import type { UnitNode } from "@/lib/api/types";

interface UnitHeaderProps {
  unit: UnitNode;
}

export function UnitHeader({ unit }: UnitHeaderProps) {
  const isLocked = unit.state === "locked";
  const bgColor = isLocked ? "#94a3b8" : unit.color || "#58CC02";

  return (
    <div
      className="relative overflow-hidden rounded-2xl p-5 text-white shadow-lg sm:p-6 transition-all"
      style={{ backgroundColor: bgColor }}
    >
      {/* Decorative background accent circle */}
      <div className="pointer-events-none absolute -right-6 -top-6 h-36 w-36 rounded-full bg-white/10" />

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-black uppercase tracking-widest text-white/85">
              Unit {unit.position}
            </span>
            {isLocked && (
              <span className="flex items-center gap-1 rounded-full bg-black/25 px-2.5 py-0.5 text-[11px] font-black uppercase text-white">
                <LockIcon className="h-3 w-3 fill-white" />
                Locked
              </span>
            )}
          </div>
          <h2 className="mt-1 text-2xl sm:text-3xl font-black tracking-tight">{unit.title}</h2>
          <p className="mt-1 max-w-md text-sm font-bold text-white/90">
            {unit.description}
          </p>
        </div>

        {/* Right side stats & Guidebook indicator */}
        <div className="flex flex-col items-end gap-2 text-right shrink-0">
          <div className="rounded-xl border-2 border-white/30 bg-white/15 px-3 py-1 text-xs font-black text-white shadow-xs whitespace-nowrap">
            {unit.completed_skills} / {unit.total_skills} skills
          </div>
        </div>
      </div>

      {/* Progress capsule bar across unit */}
      <div className="relative mt-4 h-3 w-full overflow-hidden rounded-full bg-black/20">
        <div
          className="relative h-full rounded-full bg-white transition-all duration-500 ease-out"
          style={{ width: `${unit.progress.percent}%` }}
        >
          {/* Glossy top shine */}
          <span className="absolute inset-x-1 top-0.5 h-1 rounded-full bg-white/50" />
        </div>
      </div>
    </div>
  );
}
