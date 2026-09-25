"use client";

import { AppShell } from "@/components/layout/AppShell";
import { LightningIcon, TrophyIcon } from "@/components/common/Icons";
import { ErrorState } from "@/components/common/ErrorState";
import { useLeaderboard, useMe } from "@/lib/api/hooks";
import { ApiClientError } from "@/lib/api/client";

export default function LeaderboardPage() {
  const { data: meData, isLoading: isMeLoading } = useMe();
  const {
    data: leaderboardData,
    error: leaderboardError,
    isLoading: isLeaderboardLoading,
    refetch,
  } = useLeaderboard();

  const isLoading = isLeaderboardLoading || isMeLoading;

  const errorCode =
    leaderboardError instanceof ApiClientError ? leaderboardError.code : "API_ERROR";
  const errorMessage =
    leaderboardError instanceof Error ? leaderboardError.message : "Failed to load leaderboard";

  return (
    <AppShell me={meData} isLoading={isMeLoading}>
      <div className="mx-auto flex max-w-5xl justify-center gap-10 px-4 py-8">
        {/* Main Leaderboard Table */}
        <main className="w-full max-w-xl">
          {/* Header Banner */}
          <div className="flex items-center gap-4 rounded-3xl border-2 border-gold-shadow/30 bg-gold/15 p-6 shadow-xs">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gold text-white shadow-md">
              <TrophyIcon className="h-10 w-10 fill-white" />
            </div>
            <div>
              <span className="text-xs font-black uppercase tracking-widest text-gold-shadow">
                Emerald League
              </span>
              <h1 className="text-2xl font-black text-ink">Leaderboard</h1>
              <p className="mt-0.5 text-xs font-bold text-ink-soft">
                Compete with other language learners based on total XP.
              </p>
            </div>
          </div>

          {/* Leaderboard Content */}
          <div className="mt-6">
            {isLoading ? (
              <div className="space-y-3 animate-pulse">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-16 rounded-2xl bg-canvas" />
                ))}
              </div>
            ) : leaderboardError ? (
              <ErrorState
                code={errorCode}
                message={errorMessage}
                onRetry={() => refetch()}
              />
            ) : !leaderboardData || leaderboardData.entries.length === 0 ? (
              <div className="rounded-2xl border-2 border-line bg-canvas p-8 text-center font-bold text-ink-soft">
                No leaderboard entries found.
              </div>
            ) : (
              <div className="space-y-2">
                {leaderboardData.entries.map((entry) => {
                  const isTop1 = entry.rank === 1;
                  const isTop2 = entry.rank === 2;
                  const isTop3 = entry.rank === 3;
                  const isCurrent = entry.is_current_user;

                  return (
                    <div
                      key={entry.username}
                      className={`flex items-center justify-between rounded-2xl border-2 p-3 sm:p-4 transition ${
                        isCurrent
                          ? "border-brand-shadow/40 bg-brand-light/50 shadow-sm"
                          : "border-line bg-surface hover:bg-canvas"
                      }`}
                    >
                      <div className="flex items-center gap-3 sm:gap-4">
                        {/* Rank indicator */}
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center text-sm font-black">
                          {isTop1 ? (
                            <span className="text-xl">🥇</span>
                          ) : isTop2 ? (
                            <span className="text-xl">🥈</span>
                          ) : isTop3 ? (
                            <span className="text-xl">🥉</span>
                          ) : (
                            <span className="text-ink-soft font-extrabold">{entry.rank}</span>
                          )}
                        </div>

                        {/* Avatar */}
                        <div
                          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-black text-white shadow-xs"
                          style={{ backgroundColor: entry.avatar_color }}
                        >
                          {entry.display_name.charAt(0).toUpperCase()}
                        </div>

                        {/* Names */}
                        <div className="truncate">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-extrabold text-ink truncate">
                              {entry.display_name}
                            </span>
                            {isCurrent && (
                              <span className="rounded-md bg-brand px-1.5 py-0.5 text-[10px] font-black uppercase text-white">
                                You
                              </span>
                            )}
                          </div>
                          <span className="text-xs font-bold text-ink-soft">
                            @{entry.username}
                          </span>
                        </div>
                      </div>

                      {/* XP Score */}
                      <div className="flex items-center gap-1.5 font-black text-ink shrink-0">
                        <LightningIcon className="h-4 w-4 fill-gold" />
                        <span className="text-sm sm:text-base">{entry.xp} XP</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>

        {/* Right Desktop Info Column */}
        <aside className="hidden w-72 shrink-0 space-y-4 xl:block">
          {leaderboardData?.current_user_rank && (
            <div className="rounded-2xl border-2 border-line bg-surface p-5 shadow-xs">
              <h3 className="text-xs font-black uppercase tracking-wider text-ink-soft">
                Your Current Rank
              </h3>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-black text-brand">
                  #{leaderboardData.current_user_rank}
                </span>
                <span className="text-sm font-bold text-ink-soft">
                  out of {leaderboardData.entries.length} learners
                </span>
              </div>
            </div>
          )}

          <div className="rounded-2xl border-2 border-line bg-surface p-5 shadow-xs">
            <h3 className="text-xs font-black uppercase tracking-wider text-ink-soft">
              What are Leaderboards?
            </h3>
            <p className="mt-2 text-xs font-semibold text-ink-soft leading-relaxed">
              Earn XP by completing Spanish lessons to climb the ranks! Compete with other learners in the league.
            </p>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
