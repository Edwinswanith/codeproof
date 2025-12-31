"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Sidebar } from "./sidebar";
import { Header } from "./header";

interface DashboardLayoutProps {
  children: React.ReactNode;
  headerTitle?: string;
  headerDescription?: string;
  headerActions?: React.ReactNode;
  className?: string;
}

export function DashboardLayout({
  children,
  headerTitle,
  headerDescription,
  headerActions,
  className,
}: DashboardLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar collapsed={sidebarCollapsed} onCollapse={setSidebarCollapsed} />

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header
          title={headerTitle}
          description={headerDescription}
          actions={headerActions}
        />

        {/* Page content */}
        <main className={cn("flex-1 overflow-y-auto", className)}>
          {/* Background pattern */}
          <div className="fixed inset-0 bg-grid pointer-events-none opacity-50" />

          {/* Content */}
          <div className="relative">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

// Simple container for page content
interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div className={cn("p-6 space-y-6", className)}>
      {children}
    </div>
  );
}

// Grid layout for cards
interface CardGridProps {
  children: React.ReactNode;
  columns?: 1 | 2 | 3 | 4;
  className?: string;
}

export function CardGrid({ children, columns = 3, className }: CardGridProps) {
  const colClasses = {
    1: "grid-cols-1",
    2: "grid-cols-1 md:grid-cols-2",
    3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
    4: "grid-cols-1 md:grid-cols-2 lg:grid-cols-4",
  };

  return (
    <div className={cn("grid gap-4", colClasses[columns], className)}>
      {children}
    </div>
  );
}
