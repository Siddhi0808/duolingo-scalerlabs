"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  GearIcon,
  LearnIcon,
  TrophyIcon,
  UserIcon,
} from "@/components/common/Icons";

const navItems = [
  { label: "Learn", href: "/", icon: LearnIcon },
  { label: "Leaderboard", href: "/leaderboard", icon: TrophyIcon },
  { label: "Profile", href: "/profile", icon: UserIcon },
  { label: "Settings", href: "/settings", icon: GearIcon },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-center justify-around border-t border-line bg-surface px-2 lg:hidden">
      {navItems.map((item) => {
        const isActive =
          pathname === item.href ||
          (item.href === "/" && pathname === "/");
        const Icon = item.icon;

        return (
          <Link
            key={item.label}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={`flex h-12 w-16 items-center justify-center rounded-2xl border-2 transition ${
              isActive
                ? "border-sky-shadow/30 bg-sky-light/50 text-sky"
                : "border-transparent text-ink-soft hover:bg-canvas"
            }`}
          >
            <Icon className={`h-7 w-7 ${isActive ? "fill-sky" : "fill-ink-soft"}`} />
            <span className="sr-only">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
