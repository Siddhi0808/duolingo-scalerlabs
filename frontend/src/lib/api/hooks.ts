"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./client";
import type { HeartInfo, MeResponse, PathResponse } from "./types";

export const queryKeys = {
  path: ["path"] as const,
  me: ["me"] as const,
  leaderboard: ["leaderboard"] as const,
  health: ["health"] as const,
};

export function usePath() {
  return useQuery<PathResponse>({
    queryKey: queryKeys.path,
    queryFn: api.getPath,
  });
}

export function useMe() {
  return useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: api.getMe,
  });
}

export function useLeaderboard() {
  return useQuery<import("./types").LeaderboardResponse>({
    queryKey: queryKeys.leaderboard,
    queryFn: api.getLeaderboard,
  });
}

/**
 * Display-only countdown for heart regeneration based on backend `seconds_until_next`.
 * Never mutates heart count locally. When the countdown reaches zero, it invalidates
 * the backend queries to fetch the authoritative regenerated state.
 */
export function useHeartCountdown(hearts: HeartInfo | undefined) {
  const queryClient = useQueryClient();
  const initialSeconds =
    hearts?.regenerating && hearts.seconds_until_next != null
      ? hearts.seconds_until_next
      : null;

  const [elapsed, setElapsed] = useState(0);
  const [prevSeconds, setPrevSeconds] = useState(initialSeconds);

  // Sync state during render when prop changes (recommended React pattern)
  if (initialSeconds !== prevSeconds) {
    setPrevSeconds(initialSeconds);
    setElapsed(0);
  }

  useEffect(() => {
    if (initialSeconds == null || initialSeconds <= 0) return;

    const interval = window.setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [initialSeconds]);

  // Invalidate queries when countdown expires
  useEffect(() => {
    if (initialSeconds != null && initialSeconds > 0 && elapsed >= initialSeconds) {
      queryClient.invalidateQueries({ queryKey: queryKeys.me });
      queryClient.invalidateQueries({ queryKey: queryKeys.path });
    }
  }, [elapsed, initialSeconds, queryClient]);

  const secondsRemaining =
    initialSeconds != null ? Math.max(0, initialSeconds - elapsed) : null;

  const formatted =
    secondsRemaining != null
      ? `${Math.floor(secondsRemaining / 60)}:${(secondsRemaining % 60)
          .toString()
          .padStart(2, "0")}`
      : null;

  return {
    secondsRemaining,
    formatted,
    isRegenerating: !!hearts?.regenerating,
  };
}
