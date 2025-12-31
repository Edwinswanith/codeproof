"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  FolderGit2,
  MessageSquareText,
  GitPullRequest,
  Map,
  Settings,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Zap,
  Terminal,
  FlaskConical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SimpleTooltip } from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: string | number;
}

const mainNavItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Repositories", href: "/repositories", icon: FolderGit2 },
  { label: "Ask", href: "/ask", icon: MessageSquareText },
  { label: "PR Reviews", href: "/pr-reviews", icon: GitPullRequest },
  { label: "System Map", href: "/system-map", icon: Map },
  { label: "Test Mode", href: "/test", icon: FlaskConical },
];

const bottomNavItems: NavItem[] = [
  { label: "Usage", href: "/usage", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

interface SidebarProps {
  collapsed?: boolean;
  onCollapse?: (collapsed: boolean) => void;
}

export function Sidebar({ collapsed = false, onCollapse }: SidebarProps) {
  const pathname = usePathname();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 240 }}
      transition={{ duration: 0.2, ease: "easeInOut" }}
      className="relative h-screen flex flex-col bg-card border-r border-border"
    >
      {/* Logo */}
      <div className="h-16 flex items-center justify-center px-4 border-b border-border">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="relative">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <Terminal className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-success animate-pulse" />
          </div>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="flex flex-col"
            >
              <span className="text-sm font-bold tracking-tight">CodeProof</span>
              <span className="text-2xs text-muted-foreground">Laravel Intelligence</span>
            </motion.div>
          )}
        </Link>
      </div>

      {/* Status indicator */}
      {!collapsed && (
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-success/5 border border-success/20">
            <Zap className="h-3.5 w-3.5 text-success" />
            <span className="text-xs text-success font-medium">System Online</span>
          </div>
        </div>
      )}

      {/* Main navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {mainNavItems.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
          const NavIcon = item.icon;

          const navButton = (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="activeIndicator"
                  className="absolute left-0 w-1 h-6 bg-primary rounded-r-full"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}

              <NavIcon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />

              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex-1"
                >
                  {item.label}
                </motion.span>
              )}

              {!collapsed && item.badge && (
                <span className="px-1.5 py-0.5 text-xs bg-primary/10 text-primary rounded-full">
                  {item.badge}
                </span>
              )}

              {/* Hover glow effect */}
              <div className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent rounded-lg" />
              </div>
            </Link>
          );

          return collapsed ? (
            <SimpleTooltip key={item.href} content={item.label} side="right">
              {navButton}
            </SimpleTooltip>
          ) : (
            navButton
          );
        })}
      </nav>

      <Separator />

      {/* Bottom navigation */}
      <div className="px-3 py-4 space-y-1">
        {bottomNavItems.map((item) => {
          const isActive = pathname === item.href;
          const NavIcon = item.icon;

          const navButton = (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <NavIcon className="h-5 w-5 shrink-0" />
              {!collapsed && <span className="flex-1">{item.label}</span>}
            </Link>
          );

          return collapsed ? (
            <SimpleTooltip key={item.href} content={item.label} side="right">
              {navButton}
            </SimpleTooltip>
          ) : (
            navButton
          );
        })}
      </div>

      {/* Collapse button */}
      <div className="p-3 border-t border-border">
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          className={cn("w-full", collapsed && "justify-center")}
          onClick={() => onCollapse?.(!collapsed)}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4 mr-2" />
              Collapse
            </>
          )}
        </Button>
      </div>
    </motion.aside>
  );
}
