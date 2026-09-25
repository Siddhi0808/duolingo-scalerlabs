"use client";

import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { TopHeader } from "./TopHeader";
import { BottomNav } from "./BottomNav";
import type { MeResponse } from "@/lib/api/types";

interface AppShellProps {
  children: ReactNode;
  me: MeResponse | undefined;
  isLoading?: boolean;
}

export function AppShell({ children, me, isLoading }: AppShellProps) {
  return (
    <div className="min-h-screen bg-surface">
      {/* Desktop Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex flex-col lg:pl-64">
        {/* Top Header */}
        <TopHeader me={me} isLoading={isLoading} />

        {/* Page Content with bottom padding for mobile navigation */}
        <div className="flex-1 pb-20 lg:pb-12">
          {children}
        </div>

        {/* Mobile Bottom Navigation */}
        <BottomNav />
      </div>
    </div>
  );
}
