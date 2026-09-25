"use client";

import { AppShell } from "@/components/layout/AppShell";
import { UnitHeader } from "@/components/path/UnitHeader";
import { SkillNode } from "@/components/path/SkillNode";
import { PathSkeleton } from "@/components/path/PathSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { DailyGoalCard } from "@/components/widgets/DailyGoalCard";
import { CourseStatsCard } from "@/components/widgets/CourseStatsCard";
import { useMe, usePath } from "@/lib/api/hooks";
import { ApiClientError } from "@/lib/api/client";

const PATH_OFFSETS = [0, 48, 72, 48, 0, -48, -72, -48];

export default function Home() {
  const {
    data: pathData,
    error: pathError,
    isLoading: isPathLoading,
    refetch: refetchPath,
  } = usePath();

  const {
    data: meData,
    error: meError,
    isLoading: isMeLoading,
    refetch: refetchMe,
  } = useMe();

  const isLoading = isPathLoading || isMeLoading;
  const error = pathError || meError;

  const handleRetry = () => {
    refetchPath();
    refetchMe();
  };

  const errorCode =
    error instanceof ApiClientError ? error.code : "API_ERROR";
  const errorMessage =
    error instanceof Error ? error.message : "Failed to load learning path";

  const isCourseFinished =
    pathData &&
    pathData.current_skill_id === null &&
    pathData.progress.percent === 100;

  return (
    <AppShell me={meData} isLoading={isMeLoading}>
      <div className="mx-auto flex max-w-6xl justify-center gap-12 px-4 py-8">
        {/* Main Learning Path Column */}
        <main className="w-full max-w-xl">
          {isLoading ? (
            <PathSkeleton />
          ) : error ? (
            <ErrorState
              code={errorCode}
              message={errorMessage}
              onRetry={handleRetry}
            />
          ) : !pathData || pathData.units.length === 0 ? (
            <div className="rounded-3xl border-2 border-line bg-canvas p-10 text-center">
              <h2 className="text-xl font-black text-ink">No course found</h2>
              <p className="mt-2 text-sm font-bold text-ink-soft">
                Please seed the database with Spanish course content.
              </p>
            </div>
          ) : (
            <div className="space-y-12">
              {/* Finished Course Celebration Banner if applicable */}
              {isCourseFinished && (
                <div className="rounded-3xl border-2 border-gold-shadow bg-gold/15 p-6 text-center">
                  <span className="text-4xl">🏆</span>
                  <h2 className="mt-2 text-2xl font-black text-gold-shadow">
                    Course Completed!
                  </h2>
                  <p className="mt-1 text-sm font-bold text-ink-soft">
                    Congratulations! You&apos;ve completed all units and lessons in {pathData.course.title}.
                  </p>
                </div>
              )}

              {/* Units and their skills */}
              {pathData.units.map((unit, unitIdx) => {
                const prevSkillsCount = pathData.units
                  .slice(0, unitIdx)
                  .reduce((acc, u) => acc + u.skills.length, 0);

                return (
                  <section key={unit.id} className="space-y-6">
                    {/* Unit Banner */}
                    <UnitHeader unit={unit} />

                    {/* Vertical Winding Path of Skills with Stepping Stone Connectors */}
                    <div className="relative flex flex-col items-center py-2">
                      {unit.skills.map((skill, skillIdx) => {
                        const globalIdx = prevSkillsCount + skillIdx;
                        const hasNextInUnit = skillIdx < unit.skills.length - 1;
                        const xCurrent = PATH_OFFSETS[globalIdx % PATH_OFFSETS.length];
                        const xNext = hasNextInUnit
                          ? PATH_OFFSETS[(globalIdx + 1) % PATH_OFFSETS.length]
                          : xCurrent;

                        const dot1X = xCurrent + (xNext - xCurrent) * 0.35;
                        const dot2X = xCurrent + (xNext - xCurrent) * 0.65;

                        return (
                          <div key={skill.id} className="flex flex-col items-center">
                            <SkillNode skill={skill} pathIndex={globalIdx} />

                            {/* Stepping stone connectors to next node */}
                            {hasNextInUnit && (
                              <div className="my-2 flex flex-col items-center gap-2">
                                <span
                                  className="h-2.5 w-2.5 rounded-full bg-slate-200 transition-transform shadow-xs"
                                  style={{ transform: `translateX(${dot1X}px)` }}
                                />
                                <span
                                  className="h-2.5 w-2.5 rounded-full bg-slate-200 transition-transform shadow-xs"
                                  style={{ transform: `translateX(${dot2X}px)` }}
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </main>

        {/* Right Desktop Sidebar: Daily Goal & Stats */}
        <aside className="hidden w-80 shrink-0 space-y-6 xl:block">
          <DailyGoalCard goal={meData?.daily_goal} />
          <CourseStatsCard
            stats={meData?.stats}
            xpTotal={meData?.xp_total}
          />
        </aside>
      </div>
    </AppShell>
  );
}
