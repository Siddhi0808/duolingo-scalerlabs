"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  GearIcon,
  LearnIcon,
  TrophyIcon,
  UserIcon,
} from "@/components/common/Icons";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { label: "Learn", href: "/", icon: LearnIcon },
  { label: "Leaderboard", href: "/leaderboard", icon: TrophyIcon },
  { label: "Profile", href: "/profile", icon: UserIcon },
  { label: "Settings", href: "/settings", icon: GearIcon },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-line bg-surface p-4 lg:flex z-30">
      {/* Brand logo */}
      <div className="px-4 py-6">
        <Link href="/" className="inline-block">
          <span className="text-3xl font-black tracking-tight text-brand lowercase">
            lingo
          </span>
        </Link>
      </div>

      {/* Nav items */}
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href === "/" && pathname === "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.label}
              href={item.href}
              className={`flex items-center gap-4 rounded-2xl px-4 py-3.5 text-sm font-extrabold uppercase tracking-wider transition-all duration-100 ${
                isActive
                  ? "border-2 border-sky-shadow/30 bg-sky-light/50 text-sky"
                  : "border-2 border-transparent text-ink-soft hover:bg-canvas active:translate-y-0.5"
              }`}
            >
              <Icon className={`h-7 w-7 ${isActive ? "fill-sky" : "fill-ink-soft"}`} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer / version info */}
      <div className="p-4 text-xs font-bold text-locked-ink">
        <span>Lingo Web · Spanish</span>
      </div>
    </aside>
  );
}
