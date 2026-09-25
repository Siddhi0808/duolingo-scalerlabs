import type { NextConfig } from "next";

// NEXT_PUBLIC_API_URL is inlined into the browser bundle at build time. Without it the
// client falls back to http://localhost:8000, which silently breaks a hosted deployment,
// so a Vercel build (VERCEL=1) fails fast instead. Local builds keep the fallback.
if (process.env.VERCEL && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Add it in Vercel (e.g. https://<backend-host>/api/v1) and redeploy."
  );
}

const nextConfig: NextConfig = {
  devIndicators: false,
};

export default nextConfig;
