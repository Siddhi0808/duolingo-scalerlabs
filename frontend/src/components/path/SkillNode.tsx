"use client";

import Link from "next/link";
import { useState, useRef, useEffect } from "react";
import { CheckIcon, LockIcon, StarIcon } from "@/components/common/Icons";
import type { SkillNode as SkillNodeType } from "@/lib/api/types";

interface SkillNodeProps {
  skill: SkillNodeType;
  pathIndex: number;
}

export function SkillNode({ skill, pathIndex }: SkillNodeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const isLocked = skill.state === "locked";
  const isCompleted = skill.state === "completed";
  const isInProgress = skill.state === "in_progress";

  // 8-step authentic sinusoidal winding path curve
  const offsets = [0, 48, 72, 48, 0, -48, -72, -48];
  const xOffset = offsets[pathIndex % offsets.length];

  // SVG Progress Ring calculations for active/in-progress node
  const ringRadius = 45;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const progressRatio = skill.progress.total > 0 ? skill.progress.completed / skill.progress.total : 0;
  const ringDashoffset = ringCircumference * (1 - progressRatio);

  // Close popover when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  return (
    <div
      className={`relative flex flex-col items-center justify-center my-6 transition-transform duration-200 ${
        isOpen ? "z-50" : "z-10"
      }`}
      style={{ transform: `translateX(${xOffset}px)` }}
    >
      {/* Floating "START" / "CONTINUE" bubble for current skill */}
      {skill.is_current && !isOpen && (
        <div className="absolute -top-12 z-20 animate-bounce">
          <div className="relative rounded-2xl border-2 border-brand-shadow bg-surface px-4 py-1.5 text-xs font-black uppercase tracking-wider text-brand shadow-lg">
            {isInProgress ? "Continue" : "Start"}
            {/* Downward pointing triangle pointer */}
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 border-x-8 border-t-8 border-x-transparent border-t-brand-shadow" />
            <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 border-x-7 border-t-7 border-x-transparent border-t-surface" />
          </div>
        </div>
      )}

      {/* Outer container for SVG ring and button */}
      <div className="relative flex items-center justify-center">
        {/* SVG Circular Progress Ring around active/in-progress node */}
        {isInProgress && (
          <svg
            className="pointer-events-none absolute -inset-3 h-28 w-28 -rotate-90"
            viewBox="0 0 100 100"
          >
            {/* Background track */}
            <circle
              cx="50"
              cy="50"
              r={ringRadius}
              className="stroke-line"
              strokeWidth="6"
              fill="transparent"
            />
            {/* Progress filled arc */}
            <circle
              cx="50"
              cy="50"
              r={ringRadius}
              className="stroke-gold transition-all duration-500 ease-out"
              strokeWidth="6"
              strokeDasharray={ringCircumference}
              strokeDashoffset={ringDashoffset}
              strokeLinecap="round"
              fill="transparent"
            />
          </svg>
        )}

        {/* Circular 3D Node Button */}
        <button
          type="button"
          disabled={isLocked}
          onClick={() => setIsOpen((prev) => !prev)}
          className={`group relative flex h-22 w-22 items-center justify-center rounded-full transition-transform active:translate-y-2 ${
            isLocked
              ? "cursor-not-allowed border-b-8 border-[#c5c5c5] bg-locked text-locked-ink"
              : isCompleted
              ? "border-b-8 border-gold-shadow bg-gold text-white hover:brightness-105 active:border-b-0 shadow-lg shadow-gold/20"
              : "border-b-8 border-brand-shadow bg-brand text-white hover:brightness-105 active:border-b-0 shadow-lg shadow-brand/25"
          }`}
        >
          {/* Subtle top gloss highlight */}
          <span className="absolute inset-x-3 top-2 h-4 rounded-full bg-white/20 pointer-events-none" />

          {/* Inner Icon / Visual */}
          {isLocked ? (
            <LockIcon className="h-9 w-9 fill-locked-ink" />
          ) : isCompleted ? (
            <CheckIcon className="h-9 w-9 stroke-white stroke-[3.5]" />
          ) : (
            <StarIcon className="h-9 w-9 fill-white" />
          )}

          {/* Progress badge on in-progress nodes */}
          {isInProgress && (
            <span className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface bg-brand-shadow text-[11px] font-black text-white shadow-xs">
              {skill.progress.completed}
            </span>
          )}
        </button>
      </div>

      {/* Skill Title underneath */}
      <span
        className={`mt-2 text-center text-xs font-black tracking-wide max-w-[110px] truncate ${
          isLocked ? "text-locked-ink" : "text-ink"
        }`}
      >
        {skill.title}
      </span>

      {/* Popover dialog when clicked */}
      {isOpen && (
        <div
          ref={popoverRef}
          className="absolute top-24 z-40 w-72 max-w-[calc(100vw-32px)] rounded-2xl border-2 border-line bg-surface p-4 shadow-2xl"
          style={{ transform: `translateX(${-xOffset}px)` }}
        >
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-base font-black text-ink">{skill.title}</h3>
              <p className="mt-0.5 text-xs font-semibold text-ink-soft">
                {skill.description}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-ink-soft hover:text-ink font-black text-sm p-1"
            >
              ✕
            </button>
          </div>

          {/* Skill Progress info */}
          <div className="mt-3 flex items-center justify-between border-t border-line pt-2 text-xs font-bold text-ink-soft">
            <span>Lessons</span>
            <span>
              {skill.progress.completed} / {skill.progress.total}
            </span>
          </div>

          {/* List of lessons */}
          <div className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
            {skill.lessons.map((lesson) => {
              const lessonIsLocked = lesson.state === "locked";
              const lessonIsCompleted = lesson.state === "completed";

              if (lessonIsLocked) {
                return (
                  <div
                    key={lesson.id}
                    className="flex items-center justify-between rounded-xl bg-canvas p-2.5 text-xs font-bold text-locked-ink cursor-not-allowed"
                  >
                    <span>
                      {lesson.position}. {lesson.title}
                    </span>
                    <LockIcon className="h-3.5 w-3.5 fill-locked-ink" />
                  </div>
                );
              }

              return (
                <Link
                  key={lesson.id}
                  href={`/lesson/${lesson.id}`}
                  className={`flex items-center justify-between rounded-xl p-2.5 text-xs font-extrabold transition ${
                    lessonIsCompleted
                      ? "bg-gold/10 text-gold-shadow hover:bg-gold/20"
                      : "bg-brand-light/60 text-brand-shadow hover:bg-brand-light"
                  }`}
                >
                  <span>
                    {lesson.position}. {lesson.title}
                  </span>
                  <span>
                    {lessonIsCompleted ? (
                      <span className="flex items-center gap-1 text-[11px] text-brand">
                        Done ✓
                      </span>
                    ) : (
                      <span className="rounded-lg bg-brand px-2 py-0.5 text-[10px] text-white">
                        Start
                      </span>
                    )}
                  </span>
                </Link>
              );
            })}
          </div>

          {/* Big CTA Button */}
          {skill.next_lesson_id ? (
            <Link
              href={`/lesson/${skill.next_lesson_id}`}
              className="mt-4 flex w-full items-center justify-center rounded-xl border-b-4 border-brand-shadow bg-brand py-2.5 text-xs font-black uppercase tracking-wider text-white transition hover:brightness-105 active:translate-y-1 active:border-b-0"
            >
              {isInProgress ? "Continue Lesson" : "Start Lesson"} (+10 XP)
            </Link>
          ) : isCompleted && skill.lessons.length > 0 ? (
            <Link
              href={`/lesson/${skill.lessons[0].id}`}
              className="mt-4 flex w-full items-center justify-center rounded-xl border-b-4 border-gold-shadow bg-gold py-2.5 text-xs font-black uppercase tracking-wider text-white transition hover:brightness-105 active:translate-y-1 active:border-b-0"
            >
              Practice Skill (+0 XP)
            </Link>
          ) : null}
        </div>
      )}
    </div>
  );
}
