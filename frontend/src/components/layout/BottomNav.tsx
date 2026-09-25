"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LearnIcon,
  TrophyIcon,
  UserIcon,
} from "@/components/common/Icons";

const navItems = [
  { label: "Learn", href: "/", icon: LearnIcon },
  { label: "Leaderboard", href: "/leaderboard", icon: TrophyIcon },
  { label: "Profile", href: "/profile", icon: UserIcon },
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
            className={`flex flex-col items-center justify-center rounded-xl p-2 transition ${
              isActive ? "text-sky" : "text-ink-soft hover:text-ink"
            }`}
          >
            <Icon className={`h-6 w-6 ${isActive ? "fill-sky" : "fill-ink-soft"}`} />
            <span className="sr-only">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
