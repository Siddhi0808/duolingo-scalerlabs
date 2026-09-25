import { API_BASE_URL } from "@/lib/config";
import type {
  AnswerRequest,
  AnswerResult,
  ApiErrorEnvelope,
  HeartRefillResponse,
  MeResponse,
  PathResponse,
  PublicExercise,
  SessionState,
  StartSessionResponse,
} from "./types";

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/**
 * Base fetcher with consistent error envelope handling for FastAPI responses.
 */
export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch (err) {
    throw new ApiClientError(
      "NETWORK_ERROR",
      err instanceof Error ? err.message : "Failed to connect to backend",
      0,
    );
  }

  if (!response.ok) {
    let errorCode = "UNKNOWN_ERROR";
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    let details: Record<string, unknown> = {};

    try {
      const data = (await response.json()) as ApiErrorEnvelope;
      if (data && data.error) {
        errorCode = data.error.code || errorCode;
        errorMessage = data.error.message || errorMessage;
        details = data.error.details || {};
      }
    } catch {
      // Non-JSON response body
    }

    throw new ApiClientError(errorCode, errorMessage, response.status, details);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Navigation & User
  getPath: () => apiFetch<PathResponse>("/path"),
  getMe: () => apiFetch<MeResponse>("/me"),
  getLeaderboard: () => apiFetch<import("./types").LeaderboardResponse>("/leaderboard"),
  getHealth: () =>
    apiFetch<{ status: string; service: string; version: string; time: string }>("/health"),

  // Lesson Engine & Sessions
  startLesson: (lessonId: number) =>
    apiFetch<StartSessionResponse>(`/lessons/${lessonId}/start`, {
      method: "POST",
    }),
  getSession: (sessionId: string) => apiFetch<SessionState>(`/sessions/${sessionId}`),
  getCurrentExercise: (sessionId: string) =>
    apiFetch<PublicExercise>(`/sessions/${sessionId}/current`),
  submitAnswer: (sessionId: string, request: AnswerRequest) =>
    apiFetch<AnswerResult>(`/sessions/${sessionId}/answer`, {
      method: "POST",
      body: JSON.stringify(request),
    }),
  abandonSession: (sessionId: string) =>
    apiFetch<SessionState>(`/sessions/${sessionId}/abandon`, {
      method: "POST",
    }),
  refillHearts: () =>
    apiFetch<HeartRefillResponse>("/hearts/refill", {
      method: "POST",
    }),
};
