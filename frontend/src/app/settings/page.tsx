"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorState } from "@/components/common/ErrorState";
import { SpanishFlag } from "@/components/common/Icons";
import { ApiClientError } from "@/lib/api/client";
import { useMe } from "@/lib/api/hooks";

/**
 * Settings placeholder (the assignment allows "Coming soon" for unimplemented settings).
 * Values shown are real learner data from GET /me; every control is read-only.
 */

function ComingSoonBadge() {
  return (
    <span className="shrink-0 rounded-lg bg-canvas px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-locked-ink">
      Coming soon
    </span>
  );
}

/** A switch drawn in its "off" state; disabled until the setting exists. */
function PlaceholderToggle({ label }: { label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={false}
      aria-label={`${label} (coming soon)`}
      disabled
      className="relative h-7 w-12 shrink-0 cursor-not-allowed rounded-full bg-line"
    >
      <span className="absolute left-1 top-1 h-5 w-5 rounded-full bg-surface shadow-xs" />
    </button>
  );
}

function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-black text-ink">{title}</h2>
      <div className="divide-y-2 divide-line overflow-hidden rounded-2xl border-2 border-line bg-surface">
        {children}
      </div>
    </section>
  );
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5">
      <div className="min-w-0">
        <p className="text-sm font-extrabold text-ink">{label}</p>
        {hint && <p className="text-xs font-bold text-ink-soft">{hint}</p>}
      </div>
      <div className="flex items-center gap-3">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { data: me, error, isLoading, refetch } = useMe();

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/");
  };

  return (
    <AppShell me={me} isLoading={isLoading}>
      <div className="mx-auto max-w-2xl space-y-8 px-4 py-8 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={goBack}
            aria-label="Go back"
            className="flex h-10 w-10 items-center justify-center rounded-xl text-ink-soft transition hover:bg-canvas hover:text-ink active:translate-y-0.5"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-black text-ink sm:text-3xl">Settings</h1>
        </div>

        {isLoading ? (
          <div className="animate-pulse space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-36 rounded-2xl bg-canvas" />
            ))}
          </div>
        ) : error || !me ? (
          <ErrorState
            code={error instanceof ApiClientError ? error.code : "API_ERROR"}
            message={error instanceof Error ? error.message : "Failed to load settings"}
            onRetry={() => refetch()}
          />
        ) : (
          <>
            <SettingsSection title="Profile">
              <SettingRow label="Name">
                <span className="text-sm font-bold text-ink-soft">{me.display_name}</span>
                <span
                  aria-hidden
                  className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-black text-white"
                  style={{ backgroundColor: me.avatar_color }}
                >
                  {me.display_name.charAt(0).toUpperCase()}
                </span>
              </SettingRow>
              <SettingRow label="Username">
                <span className="text-sm font-bold text-ink-soft">@{me.username}</span>
              </SettingRow>
              <SettingRow label="Edit profile" hint="Change your name, username and avatar">
                <ComingSoonBadge />
              </SettingRow>
            </SettingsSection>

            <SettingsSection title="Course">
              <SettingRow label="Learning" hint="From English">
                <span className="flex items-center gap-2 text-sm font-bold text-ink-soft">
                  <SpanishFlag className="h-4 w-6 rounded-xs" />
                  Spanish
                </span>
              </SettingRow>
              <SettingRow label="Daily goal" hint={`${me.daily_goal.goal_xp} XP per day`}>
                <ComingSoonBadge />
              </SettingRow>
              <SettingRow label="Add a course" hint="Only one course is available">
                <ComingSoonBadge />
              </SettingRow>
            </SettingsSection>

            <SettingsSection title="Notifications">
              <SettingRow label="Practice reminders">
                <ComingSoonBadge />
                <PlaceholderToggle label="Practice reminders" />
              </SettingRow>
              <SettingRow label="Streak reminders">
                <ComingSoonBadge />
                <PlaceholderToggle label="Streak reminders" />
              </SettingRow>
              <SettingRow label="Leaderboard updates">
                <ComingSoonBadge />
                <PlaceholderToggle label="Leaderboard updates" />
              </SettingRow>
            </SettingsSection>

            <SettingsSection title="Sound & experience">
              <SettingRow label="Sound effects">
                <ComingSoonBadge />
                <PlaceholderToggle label="Sound effects" />
              </SettingRow>
              <SettingRow label="Animations">
                <ComingSoonBadge />
                <PlaceholderToggle label="Animations" />
              </SettingRow>
              <SettingRow label="Dark mode">
                <ComingSoonBadge />
                <PlaceholderToggle label="Dark mode" />
              </SettingRow>
            </SettingsSection>

            <SettingsSection title="Account">
              <SettingRow label="Super subscription" hint="Gems and hearts are mocked">
                <ComingSoonBadge />
              </SettingRow>
              <SettingRow label="Sign out" hint="Demo mode: you are always the sample learner">
                <ComingSoonBadge />
              </SettingRow>
            </SettingsSection>
          </>
        )}
      </div>
    </AppShell>
  );
}
