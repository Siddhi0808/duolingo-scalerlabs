/**
 * Base URL of the FastAPI backend, including the version prefix.
 * NEXT_PUBLIC_ variables are inlined at build time, so set it before `next build`.
 */
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");
